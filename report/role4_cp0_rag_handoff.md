# Role 4 — CP0 RAG & Agent Handoff

> **Checkpoint 0 · 00:00–00:30**
> Vai trò: RAG & Agent Owner — không build collection ở CP0, chỉ chốt contract và chuẩn bị để build ở CP2.

---

## Tóm tắt đầu ra CP0

| # | Đầu ra | Trạng thái sau CP0 |
|---|--------|--------------------|
| 1 | Input contract từ Role 3 (cleaning) | ✅ Đã chốt |
| 2 | Output contract (manifest path + collection name) | ✅ Đã chốt |
| 3 | Kỹ thuật đã quyết định (model, store, distance) | ✅ Đã chốt |
| 4 | Smoke test plan dùng ở CP2 | ✅ Đã chuẩn bị |

---

## 1. Input Contract — dữ liệu Role 3 phải bàn giao trước CP2

Role 4 chỉ nhận dữ liệu từ `data/clean/papers_clean.csv` (hoặc `.json`).
Mỗi row **bắt buộc** có đủ các trường sau:

| Trường | Kiểu | Quy tắc | Dùng trong RAG |
|--------|------|---------|----------------|
| `paper_id` | `str` | Không rỗng, duy nhất (case-insensitive) | Document identity, exact lookup |
| `title` | `str` | Không rỗng | Exact lookup theo title, metadata |
| `summary` | `str` | Không rỗng | Trả lời câu hỏi factual |
| `text_for_embedding` | `str` | Không rỗng, có nhãn `Title / Authors / Categories / Summary` | Nội dung đưa vào MiniLM + ChromaDB |
| `published` | `str` | ISO date (`YYYY-MM-DD`) | Metadata, câu hỏi ngày xuất bản |
| `authors_joined` | `str` | Không rỗng | Metadata, câu hỏi tác giả |
| `categories_joined` | `str` | Không rỗng hoặc `"N/A"` | Metadata, câu hỏi chủ đề |
| `abs_url` | `str` | Có thể rỗng | Lineage metadata |
| `pdf_url` | `str` | Có thể rỗng | Lineage metadata |

**Định dạng `text_for_embedding` kỳ vọng:**

```
Title: <title>
Authors: <authors_joined>
Categories: <categories_joined>
Summary: <summary>
```

> ⚠️ **Blocker cho Role 4:** Nếu `paper_id` có duplicate, hoặc `text_for_embedding` rỗng, Role 4 **không thể build collection**. Phải báo Role 3 fix trước khi sang CP2.

---

## 2. Output Contract — Role 4 bàn giao gì

### 2.1 Baseline (build tại CP2)

| Item | Path |
|------|------|
| Embedding manifest | `data/embeddings/papers_embeddings.json` |
| ChromaDB collection | `papers-baseline` |
| ChromaDB persist dir | `data/chroma/` |

### 2.2 Corrupted (build tại CP5)

| Item | Path |
|------|------|
| Embedding manifest | `data/embeddings/papers_embeddings_corrupted.json` |
| ChromaDB collection | `papers-corrupted` |

### 2.3 Repaired (build tại CP6)

| Item | Path |
|------|------|
| Embedding manifest | `data/embeddings/papers_embeddings_repaired.json` |
| ChromaDB collection | `papers-repaired` |

> Ba collection dùng chung `data/chroma/` nhưng **tên khác nhau** — không bao giờ `delete_collection("papers-baseline")` sau CP2.

### 2.4 Cấu trúc manifest JSON (mỗi file phải có)

```json
{
  "backend": "chroma",
  "embedding_model": "gemini-embedding-001",
  "persist_path": "data/chroma",
  "collection_name": "papers-baseline",
  "documents": [
    {
      "record_id": "<paper_id>::0",
      "paper_id": "<paper_id>",
      "title": "...",
      "content": "<text_for_embedding>",
      "metadata": {
        "paper_id": "...",
        "title": "...",
        "published": "YYYY-MM-DD",
        "authors_joined": "...",
        "categories_joined": "...",
        "summary": "...",
        "abs_url": "...",
        "pdf_url": "..."
      }
    }
  ]
}
```

---

## 3. Quyết định kỹ thuật (đã chốt, không thay đổi giữa 3 trạng thái)

| Tham số | Giá trị |
|---------|---------|
| Embedding model | `gemini-embedding-001` |
| Vector store | ChromaDB persistent |
| Distance metric | Cosine (`hnsw.space = cosine`) |
| Score công thức | `score = max(0.0, 1.0 - distance)` |
| `top_k` mặc định | `4` (lấy từ `settings.top_k`) |
| Semantic retrieval | `LocalEmbeddingIndex.search(query, top_k)` |
| Exact retrieval | `LocalEmbeddingIndex.lookup(paper_id_or_title)` |
| Agent tool call | Agent **phải gọi tool** trước khi trả lời factual |
| Agent out-of-corpus | Nếu corpus không hỗ trợ, agent nói rõ: `"I don't know from the indexed corpus."` |

---

## 4. Smoke Test Plan — chạy ngay sau khi build `papers-baseline` (CP2)

Lấy `paper_id` và `title` **thật** từ `data/clean/papers_clean.csv` trước khi chạy.

### Test 1 — Semantic Search trả đủ fields

```python
results = index.search("retrieval augmented generation", top_k=3)
assert len(results) >= 1
assert all(r.paper_id and r.title and r.score >= 0 and r.content for r in results)
```

**Pass:** Trả ít nhất 1 result có `paper_id`, `title`, `score`, `content` và `metadata` đầy đủ.

---

### Test 2 — Exact Lookup theo `paper_id` và `title` ra cùng document

```python
doc_by_id    = index.lookup("<paper_id thật>")
doc_by_title = index.lookup("<title thật>")
assert doc_by_id is not None
assert doc_by_title is not None
assert doc_by_id["paper_id"] == doc_by_title["paper_id"]
```

**Pass:** Cả hai tra cứu trả về cùng document.

---

### Test 3 — `answer_question` trả lời factual từ metadata

```python
from retrieval.qa import answer_question
result = answer_question("Who authored '<title thật>'?", settings, index)
assert result.answer != ""
assert len(result.retrieved_doc_ids) >= 1
```

**Pass:** `result.answer` chứa tên tác giả lấy từ `metadata["authors_joined"]`, không bịa.

---

### Test 4 — Agent dùng tool, không khẳng định ngoài corpus

```python
from retrieval.agent import build_agent, run_agent_question
agent = build_agent(settings, index)
answer = run_agent_question(agent, "What are the main topics of '<title thật>'?")
assert answer != ""
# Kiểm tra thủ công: câu trả lời phải từ nội dung paper, không hallucinate
```

**Pass:** Agent gọi `semantic_search_papers` hoặc `lookup_paper` trước khi trả lời.

---

## 5. Các blocker cần báo nhóm ngay tại CP0

| Blocker | Ai chịu trách nhiệm fix |
|---------|------------------------|
| `paper_id` duplicate trong cleaned data | Role 3 |
| `text_for_embedding` rỗng hoặc thiếu nhãn | Role 3 |
| `published` không đúng format ISO | Role 3 |
| Không có `GOOGLE_API_KEY` (hoặc provider khác) trong `.env` | Tất cả / Lead |
| `sentence-transformers` chưa cài | Chạy `uv sync` hoặc `pip install -e .` |

---

## 6. Mapping code → config (tham khảo nhanh)

| Config field | Giá trị mặc định | Nguồn |
|---|---|---|
| `settings.embedding_model` | `"gemini-embedding-001"` | `src/core/config.py` L122 |
| `settings.baseline_collection_name` | `"papers-baseline"` | `src/core/config.py` L123 |
| `settings.corrupted_collection_name` | `"papers-corrupted"` | `src/core/config.py` L124 |
| `settings.repaired_collection_name` | `"papers-repaired"` | `src/core/config.py` L125 |
| `settings.top_k` | `4` | `src/core/config.py` L130 |
| `settings.paths.chroma_dir` | `data/chroma/` | `src/core/config.py` L87 |
| `settings.paths.embeddings_json` | `data/embeddings/papers_embeddings.json` | `src/core/config.py` L88 |

---

## 7. Script smoke test sẵn sàng chạy ở CP2

File: `script/smoke_test_rag_cp2.py`

```bash
# Chạy ngay sau khi papers-baseline được build tại CP2
uv run python script/smoke_test_rag_cp2.py
```

Script gồm 5 test tự động:

| Test | Kiểm tra | Pass khi |
|------|----------|----------|
| **T0** | Manifest file tồn tại | `data/embeddings/papers_embeddings.json` có mặt |
| **T1** | Semantic search | Trả ≥ 1 result có `paper_id`, `title`, `score ∈ [0,1]`, `content` |
| **T2a** | Exact lookup by `paper_id` | Document được tìm thấy chính xác |
| **T2b** | Exact lookup by `title` | Cùng document với lookup by `paper_id` |
| **T3** | `answer_question` | Answer không rỗng, lấy từ metadata |
| **T4** | `build_agent` khởi tạo | Agent object tạo thành công (không gọi LLM) |

> Để test agent thực tế (gọi LLM), uncomment phần `invoke` trong Test 4 — chú ý tốn quota.

---

## 8. Checklist hoàn thành CP0

Tích khi xong, bàn giao cho nhóm trước khi hết 00:30.

- [x] Đọc và hiểu `LocalEmbeddingIndex` (index.py)
- [x] Đọc và hiểu `MiniLMEmbeddings` (embeddings.py)
- [x] Đọc và hiểu `build_agent`, `run_agent_question` (agent.py)
- [x] Đọc và hiểu `answer_question`, `AnswerResult` (qa.py)
- [x] Đọc và hiểu `build_llm` và provider mapping (llm.py)
- [x] Chốt input contract với Role 3 (9 trường, quy tắc paper_id unique)
- [x] Chốt output contract (3 manifest path × 3 collection name)
- [x] Chốt quyết định kỹ thuật (MiniLM, ChromaDB cosine, top_k=4)
- [x] Chuẩn bị smoke test plan (`script/smoke_test_rag_cp2.py`)
- [ ] Báo Role 3 nếu có blocker (paper_id duplicate, text_for_embedding rỗng)
- [ ] Xác nhận `.env` có API key của provider đang dùng

