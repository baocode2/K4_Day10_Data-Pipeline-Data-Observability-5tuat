# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Thành viên Nhóm 5 (Role 4) |
| MSSV | 2A202601040 |
| Khóa/Lớp | K4 |
| Tên nhóm | Nhóm 5 người |
| Vai trò chính | Vai trò 4: RAG & Agent Owner (Phụ trách Vector Index & Agent) |
| Repository | baocode2/K4_Day10_Data-Pipeline-Data-Observability-5tuat |
| Ngày hoàn thành | 2026-08-06 |

---

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Gemini Embedding Adapter | `src/retrieval/embeddings.py` (`GeminiEmbeddings`) | Text list, `GOOGLE_API_KEY` | Float embedding vectors | Hoàn thành |
| Local Embedding Index (ChromaDB) | `src/retrieval/index.py` (`LocalEmbeddingIndex`, `build`, `load`, `search`, `lookup`) | Cleaned DataFrame (`papers_clean.csv`, `corrupted`, `repaired`) | Collection ChromaDB (`papers-baseline`, `papers-corrupted`, `papers-repaired`), `papers_embeddings.json` | Hoàn thành |
| RAG Agent & Tools Integration | `src/retrieval/agent.py` (`build_agent`, `semantic_search_papers`, `lookup_paper`, `run_agent_question`) | `Settings`, `LocalEmbeddingIndex` | CompiledStateGraph Agent, trả lời Factual dựa trên Tool Result | Hoàn thành |
| QA Engine Helper | `src/retrieval/qa.py` (`answer_question`) | Question, `Settings`, `LocalEmbeddingIndex` | `AnswerResult` (Answer, retrieved contexts, doc_ids) | Hoàn thành |
| Smoke Test CP2 & Demo CP3/CP5 | `script/smoke_test_rag_cp2.py`, `script/demo_cp3_rag.py`, `script/demo_cp5_rag.py` | Manifests & Clean DataFrames | Verification reports (`report/role4_cp2_rag_validation.md`, `role4_cp5_rag_validation.md`) | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Thống nhất Input Contract dữ liệu sạch | Role 3 (Cleaning Owner) | Xác định 9 trường dữ liệu bắt buộc (`paper_id`, `text_for_embedding`, `summary`, `authors_joined`,...) |
| Hỗ trợ tích hợp Evaluation Testset | Role 5 (Evaluation Owner) | Đảm bảo `ground_truth_doc_ids` sử dụng `paper_id` chuẩn để tính `retrieval_hit_rate` |
| Sửa lỗi Encoding stdout trên Windows | Toàn nhóm (Script execution) | Thêm `sys.stdout.reconfigure(encoding="utf-8")` tránh crash `UnicodeEncodeError` |

---

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Định nghĩa Contract Handoff CP0 | `report/role4_cp0_rag_handoff.md` | Bản mô tả input/output contract cho RAG | Đọc file handoff report |
| Xây dựng Baseline Vector Index (CP2) | `data/embeddings/papers_embeddings.json`, collection `papers-baseline` | 24 documents được index thành công vào ChromaDB | Chạy `script/smoke_test_rag_cp2.py` (5/5 PASS) |
| Demo Retrieval & RAG Agent (CP3) | `script/demo_cp3_rag.py` | Demo Semantic Search, Lookup và Agent Factual QA | Chạy `script/demo_cp3_rag.py` |
| Build Corrupted Vector Index (CP5) | `data/embeddings/papers_embeddings_corrupted.json`, collection `papers-corrupted` | 24 documents bị lỗi (blank summary, noise, truncated title) được index riêng | Chạy `script/demo_cp5_rag.py` |

**Nêu một output cụ thể mà phần việc của bạn tạo ra:**
Artifact [`data/embeddings/papers_embeddings.json`](file:///d:/VIN.AI/VIN_Labs/K4_Day10_Data-Pipeline-Data-Observability-5tuat/data/embeddings/papers_embeddings.json) chứa manifest chi tiết 24 tài liệu học thuật được tạo vector embedding với Gemini Embeddings (`gemini-embedding-001`) và lưu trữ trong collection ChromaDB persistent `papers-baseline`.

---

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết
Xây dựng thành phần Retrieval (Tìm kiếm ngữ nghĩa & Exact lookup) và Agent cho hệ thống RAG. Yêu cầu đảm bảo Agent chỉ trả lời dựa trên dữ liệu thật đã index từ Crossref qua các tool call, đồng thời tách biệt 3 trạng thái index (baseline, corrupted, repaired) để đo lường chính xác tác động của lỗi dữ liệu.

### Cách triển khai
1. **Embedding Adapter:** Xây dựng `GeminiEmbeddings` trong `src/retrieval/embeddings.py` kế thừa từ `langchain_core.embeddings.Embeddings` để gọi API Google Generative AI Embeddings.
2. **Indexing & ChromaDB Management:**
   - Hàm `LocalEmbeddingIndex.build()` kiểm tra dữ liệu qua `validate_index_dataframe()`, nạp text từ cột `text_for_embedding`, tính embedding và ghi vào collection ChromaDB persistent (`data/chroma/`).
   - Tên collection được tự động phân tách theo tham số (`papers-baseline`, `papers-corrupted`, `papers-repaired`).
3. **Agent Tools Integration:**
   - Định nghĩa 2 `@tool` LangChain: `semantic_search_papers` (Cosine similarity search) và `lookup_paper` (Tìm kiếm chính xác theo `paper_id` hoặc `title`).
   - Sử dụng `create_react_agent` từ `langgraph.prebuilt` kết hợp LLM (`gemini-2.0-flash`) và system prompt ép buộc Agent phải tra cứu tool trước khi trả lời.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | DataFrame cleaned từ `data/clean/papers_clean.csv` (có `paper_id`, `text_for_embedding`, `summary`,...) |
| Output | Collection ChromaDB trong `data/chroma/` và file manifest JSON trong `data/embeddings/` |
| Module phụ thuộc | Role 3 (`src/ingestion/cleaning.py`), `core.config.Settings` |
| Module sử dụng output | Role 5 (`src/evaluation/metrics.py` để chấm điểm evaluation) |
| Điều kiện lỗi cần xử lý | Blocker khi `paper_id` rỗng/duplicate; xử lý fallback khi `summary` bị blank hoặc title bị truncated do corruption |

### Cách xác minh

```bash
python script/smoke_test_rag_cp2.py
python script/demo_cp3_rag.py
python script/demo_cp5_rag.py
```

- **Kết quả mong đợi:** 100% tests PASS; Agent trả lời đúng tác giả và nội dung bài báo; Baseline và Corrupted collections nằm ở 2 path/collection tên riêng biệt.
- **Kết quả thực tế:** Tất cả 5/5 smoke tests PASS; Agent trả lời đúng 100% tên tác giả bài báo SafeRAG qua tool retrieval.
- **Artifact/log:** [`report/role4_cp2_rag_validation.md`](file:///d:/VIN.AI/VIN_Labs/K4_Day10_Data-Pipeline-Data-Observability-5tuat/report/role4_cp2_rag_validation.md), [`report/role4_cp5_rag_validation.md`](file:///d:/VIN.AI/VIN_Labs/K4_Day10_Data-Pipeline-Data-Observability-5tuat/report/role4_cp5_rag_validation.md).

---

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Lựa chọn quy cách lưu trữ Vector Collection cho 3 trạng thái dữ liệu (Baseline, Corrupted, Repaired).
- **Các phương án đã cân nhắc:**
  1. *Phương án A:* Dùng chung 1 collection ChromaDB duy nhất và ghi đè (delete & recreate) mỗi khi chuyển phase.
  2. *Phương án B:* Tạo 3 collection riêng biệt (`papers-baseline`, `papers-corrupted`, `papers-repaired`) cùng nằm trong thư mục Chroma persistent `data/chroma/`, xuất 3 file manifest JSON tương ứng.
- **Phương án đã chọn:** Phương án B.
- **Lý do:** Đảm bảo nguyên tắc bảo toàn dữ liệu baseline (reproducibility và auditability). Giúp có thể chạy so sánh song song giữa 3 collection bất kỳ lúc nào mà không sợ bị biến đổi (mutate) dữ liệu gốc.
- **Bằng chứng quyết định phù hợp:** Trong `script/demo_cp5_rag.py`, script load thành công cả 2 collection `papers-baseline` (24 docs) và `papers-corrupted` (24 docs) để so sánh trực tiếp kết quả retrieval cùng một thời điểm.

---

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:**
  ```text
  chromadb.errors.InternalError: failed to create whole tree
  UnicodeEncodeError: 'charmap' codec can't encode character '\U0001f4d6'
  ValueError: Clean dataframe has invalid RAG fields: summary (3 blank)
  ```
- **Lệnh hoặc bước tái hiện:** Running `script/build_cp5_corrupted.py` trên Windows console.
- **Nguyên nhân gốc:**
  1. SQLite DB file lock khi nhiều process Python gọi `chromadb.PersistentClient` đồng thời.
  2. Terminal Windows mặc định dùng encoding `cp1252` không in được Unicode emoji.
  3. Hàm `validate_index_dataframe()` ép buộc `summary` không được rỗng, khiến pipeline bị dừng khi index dữ liệu cố ý corrupt (blank summary scenario).
- **Cách xử lý:**
  1. Chạy các script thử nghiệm tuần tự thay vì song song, bổ sung `try...except` với `get_or_create_collection`.
  2. Thêm `sys.stdout.reconfigure(encoding="utf-8")` ở đầu các script.
  3. Cập nhật `validate_index_dataframe()` chỉ bắt buộc 2 trường cốt lõi là `paper_id` và `text_for_embedding`, cho phép metadata summary/title rỗng để phục vụ đo lường dữ liệu lỗi.
- **Cách xác minh sau khi sửa:** Chạy `python script/build_cp5_corrupted.py` và `python script/demo_cp5_rag.py` trả về exit code 0.
- **Điều học được:** Khi xây dựng data validation gates cho RAG, cần phân biệt rõ giữa "Identity/Embedding contract" (bắt buộc) và "Metadata fields" (có thể bị khuyết do chất lượng dữ liệu nguồn).

---

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. **Luồng dữ liệu từ Crossref đến Vector Index:**
   Crossref REST API ➔ Fetch raw JSON records (Role 2) ➔ Data cleaning, deduplication, tính `age_days` & sinh `text_for_embedding` (Role 3) ➔ Gemini Embeddings API chuyển `text_for_embedding` thành 768-dim float vectors (Role 4) ➔ Lưu trữ vào ChromaDB Persistent Collection & ghi manifest JSON (Role 4).

2. **Evaluation set và ground-truth document IDs:**
   Evaluation set chứa danh sách các câu hỏi test kèm `ground_truth` (câu trả lời chuẩn) và `ground_truth_doc_ids` (danh sách `paper_id` đúng). Khi RAG Agent/Index thực hiện retrieval, hệ thống sẽ đối chiếu `retrieved_doc_ids` với `ground_truth_doc_ids` để tính `retrieval_hit_rate`, và dùng LLM Judge / Token F1 so sánh `answer` với `ground_truth`.

3. **Phân biệt Quality checks và Freshness monitoring:**
   - *Data Quality Checks:* Kiểm tra tính toàn vẹn của schema, nulls, duplicates, số lượng dòng tối thiểu và định dạng dữ liệu (ví dụ: `paper_id` unique, `summary` length).
   - *Freshness Monitoring:* Giám sát tuổi của dữ liệu dựa trên ngày xuất bản (`published` và `age_days`) so với ngưỡng cấu hình (`freshness_threshold_days = 180`), đảm bảo RAG Agent không sử dụng kiến thức quá cũ.

4. **Tầm quan trọng của việc cố định 1 Test Set:**
   Phải giữ nguyên cùng 1 test set cho cả 3 trạng thái (baseline, corrupted, repaired) để làm "biến kiểm soát" (control variable). Nếu thay đổi test set giữa các lần đo, sự thay đổi về metric sẽ không thể kết luận là do chất lượng dữ liệu hay do câu hỏi dễ/khó khác nhau.

5. **Tiêu chí Repair thành công:**
   Repair thành công khi:
   - Signals về Quality & Freshness phục hồi về trạng thái `PASS` / `FRESH`.
   - Các chỉ số RAG (`retrieval_hit_rate`, `mean_token_f1`, `judge_accuracy`) quay trở lại mức ngang hoặc xấp xỉ với Baseline.

---

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.8333 | 1.0000 | Baseline đạt 100%. Khi corrupt (mất record/rỗng summary), hit rate giảm xuống 83.3%. Sau khi repair khôi phục về 100%. |
| `mean_token_f1` | 0.9575 | 0.7200 | 0.9575 | F1 token sụt giảm mạnh khi summary bị bơm noise/cắt xén, phục hồi hoàn toàn sau repair. |
| `judge_accuracy` | 1.0000 | 0.6667 | 1.0000 | LLM Judge đánh giá 1/3 câu trả lời bị sai khi RAG lấy phải dữ liệu corrupt. |
| `mean_judge_score` | 4.8333 | 3.1000 | 4.8333 | Điểm trung bình đánh giá chất lượng giảm từ 4.83 xuống 3.10 và phục hồi lại 4.83. |
| Quality checks | PASS | FAIL | PASS | Corrupted fail ở `summary_min_chars`, `title_not_null` và `freshness_threshold`. |
| Freshness status | FRESH | STALE | FRESH | Corrupted bị dời mốc ngày xuất bản lùi 10 năm gây cảnh báo STALE. |

### Kết luận từ số liệu

1. **Chuỗi ảnh hưởng 1 (Corruption):**
   [Corrupt dữ liệu: blank summary & noise] ➔ [Quality check `summary_min_chars` báo FAIL] ➔ [Retrieval trả về context kém chất lượng ➔ `judge_accuracy` giảm từ 1.00 xuống 0.66].

2. **Chuỗi ảnh hưởng 2 (Repair):**
   [Repair: Nạp lại dữ liệu chuẩn từ Raw Crossref] ➔ [Quality checks & Freshness phục hồi `PASS` & `FRESH`] ➔ [`retrieval_hit_rate` và `mean_judge_score` quay lại mốc 1.00 và 4.83].

**Corruption ảnh hưởng rõ nhất:**
Lỗi **`blank_summary`** và **`inject_summary_noise`** ảnh hưởng nặng nề nhất đến RAG Agent vì vector embedding bị lệch hướng trong không gian ngữ nghĩa, làm Agent không tìm thấy đoạn văn chứa câu trả lời hoặc bị hallucinatory theo nội dung nhiễu.

---

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất
1. **Data Pipeline Architecture:** Hiểu rõ tầm quan trọng của việc tách biệt rõ ràng các tầng raw ➔ clean ➔ embedding index để dễ dàng truy vết và phục hồi khi xảy ra lỗi.
2. **Data Observability:** Thấy được giá trị của việc đặt các quality gates và freshness checks chủ động trước khi dữ liệu được nạp vào vector store, giúp ngăn chặn câu trả lời sai trước khi tới tay end-user.
3. **Data Impact on RAG/Agent:** Chứng minh thực tế bằng con số rằng mô hình LLM mạnh đến đâu cũng sẽ trả lời sai nếu dữ liệu đầu vào (Retrieved Context) bị lỗi (nguyên lý *Garbage In, Garbage Out*).

### Nếu có thêm thời gian
Sẽ triển khai cơ chế **Automated Re-indexing Pipeline Trigger**: Tự động kích hoạt rebuild vector index và thông báo alert Slack/Email ngay khi Quality Check báo lỗi `FAIL`, thay vì phải chạy thủ công các script riêng lẻ.

---

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Thành viên Nhóm 5 (Role 4)  
**MSSV:** 2A202601040  
**Ngày xác nhận:** 2026-08-06
