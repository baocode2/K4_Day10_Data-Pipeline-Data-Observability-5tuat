# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Phạm Quốc Bảo            |
| MSSV               | 2A202601502                |
| Khóa/Lớp         | K4                         |
| Tên nhóm         | 5tuat                      |
| Vai trò chính    | Role 5 – Evaluation & Observability owner |
| Repository         | github.com-vinai:baocode2/K4_Day10_Data-Pipeline-Data-Observability-5tuat |
| Ngày hoàn thành | 2026-08-06                 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái                                 |
| ------------------ | --------------------- | ---------------- | ----------------- | -------------------------------------------- |
| Evaluation set builder | `src/evaluation/testset.py` (`build_test_set`) | `papers_clean.csv` (24 rows, 9 cột metadata) | `data/eval/test_set.json` (12 câu, 3/loại, 4 loại: summary/authors/date/categories) | Hoàn thành |
| Data quality checks | `src/observability/quality.py` (`run_data_quality_checks`) | Clean dataframe (baseline/corrupted/repaired) | `data/quality/{name}_quality.json` (7 check: row_count, paper_id_unique, title_not_null, summary_min_chars, text_for_embedding_not_empty, age_days_valid, freshness_threshold) | Hoàn thành |
| Freshness report | `src/observability/quality.py` (`build_freshness_report`) | Clean dataframe với `published`, `age_days` | `data/quality/{name}_freshness_report.json` (latest_published, oldest_published, stale_rows, is_fresh) | Hoàn thành |
| Phase 1 report | `src/observability/reporting.py` (`generate_phase1_report`) | source_summary, metrics, quality, freshness | `data/reports/phase1_report.md` | Hoàn thành |
| Corruption comparison report | `src/observability/reporting.py` (`generate_corruption_report`) | baseline/corrupted/repaired metrics + quality + freshness | `data/reports/corruption_report.md` (bảng 3 stage + delta) | Hoàn thành |
| Signal-change helper | `src/observability/signals.py` (`build_signal_change`, `write_signal_change`) | corruption_log + 3 quality + 3 metrics | `data/results/signal_change.json` (map event → check fail + metric delta + unchanged_signals) | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                         | Thành viên/module được hỗ trợ | Kết quả                    |
| ------------------------------------ | ------------------------------------ | ---------------------------- |
| Fix `src/retrieval/agent.py` import | Role 4 (RAG) | Thay `langchain.agents.create_agent` (không có trong langchain 0.3.30) bằng `langgraph.prebuilt.create_react_agent` + `state_modifier` thay cho `system_prompt`/`name`. Pipeline chạy được. |
| Wire `corruption_flow.py` truyền baseline_quality/baseline_freshness | Role 1 (lead) | `generate_corruption_report` thêm 2 optional param; `corruption_flow.py` đọc từ `data/quality/baseline_*.json` trước khi gọi. Report hiện baseline PASS, corrupted FAIL, repaired PASS thay vì `n/a`. |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh         |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Sinh test set 12 câu, 4 loại, 12 paper_id unique | `data/eval/test_set.json` | 12 sample, mỗi loại 3 câu, `ground_truth_doc_ids` ∈ 24 rows clean | `python -c "import json; json.load(open('data/eval/test_set.json'))"` → 12 item |
| Chạy quality checks 3 stage | `data/quality/baseline_quality.json`, `corrupted_quality.json`, `repaired_quality.json` | overall_pass: True/False/True; 7 check/artifact | Mở file, quan sát `overall_pass` |
| Chạy freshness report 3 stage | `data/quality/freshness_report.json`, `corrupted_freshness_report.json`, `repaired_freshness_report.json` | is_fresh/stale_rows/publication | Observe `is_fresh = true/false/true` |
| Sinh report markdown | `data/reports/phase1_report.md`, `data/reports/corruption_report.md` | Markdown có bảng metrics + quality + freshness 3 stage | Mở file, render bảng |
| Sinh signal-change file | `data/results/signal_change.json` | Map 6 corruption event → check fail + delta metric | Mở file, đọc `corruption_to_quality`, `metric_change`, `unchanged_signals` |

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Bài lab yêu cầu chứng minh rằng chất lượng dữ liệu ảnh hưởng trực tiếp đến chất lượng RAG agent. Role 5 đảm bảo có 3 thứ có thể kiểm chứng: (i) test set cố định dùng lại được cho cả 3 stage, (ii) hàm quality/freshness phát hiện defect có chủ đích, (iii) report so sánh 3 stage bằng số liệu thật kèm bằng chứng từ source.

### Cách triển khai

**Test set builder** chọn min(12, len(df)) row đầu rồi chia 4 slice rời nhau, mỗi slice 3 row cho một `question_type`. Mỗi câu hỏi theo format keyword mà `qa.py:answer_question` route — ví dụ `"Who authored '<title>'?"` match nhánh `authors_joined`, `"When was '<title>' published?"` match nhánh `published`. Bằng cách giữ question format deterministic, retrieval + extraction tách bạch khỏi LLM generation, metric `token_f1` đo trực tiếp.

**Quality checks** là 7 predicate rẻ: row count, paper_id unique, title/summary non-empty, `text_for_embedding` non-empty, `age_days` valid, `freshness_threshold`. Mỗi check trả `{name, status, observed, expected, message}` thay vì raise — để `run_data_quality_checks` aggregate thành `overall_pass` boolean. Trước khi index được build, các check này đã chỉ ra row xấu.

**Signal-change** map `corruption_log["events"]` (6 event do role 3 sinh) sang check có thể fail. Với mỗi event type, biết trước các check liên quan: `drop_latest_records` ảnh hưởng `freshness_threshold`, `blank_summary` ảnh hưởng `summary_min_chars` + `text_for_embedding_not_empty`, `duplicate_rows` ảnh hưởng `paper_id_unique`. So sánh `expected_signal_checks` với `observed_failing_checks` từ quality cho từng event → có bằng chứng rằng một corruption event thực sự kích hoạt check fail.

**Three-stage comparison report** in ra bảng baseline vs corrupted vs repaired với `Δ (Corrupt-Base)` và `Δ (Repair-Corrupt)`. Metric `judge_accuracy` không đổi qua 3 stage → được liệt kê vào `unchanged_signals` để không kết luận quá mức.

### Input, output và contract

| Thành phần                   | Mô tả                                     |
| ------------------------------ | ------------------------------------------- |
| Input                          | Clean dataframe với 9 cột chuẩn (paper_id, title, summary, authors_joined, categories_joined, published, age_days, text_for_embedding, ...); test set JSON là list dict 5-key |
| Output                         | 7 quality check payloads + freshness payload + 2 markdown report + 1 signal-change JSON |
| Module phụ thuộc             | `core.config.Settings`, `core.utils.write_json/read_json/first_sentence`, `evaluation.metrics.evaluate_pipeline` (chỉ đọc) |
| Module sử dụng output        | `pipelines/phase1.main` (gọi `generate_phase1_report`), `pipelines/corruption_flow.main` (gọi `run_data_quality_checks`, `build_freshness_report`, `generate_corruption_report`) |
| Điều kiện lỗi cần xử lý | `build_test_set` raise `ValueError` khi `len(df) < 12` hoặc `ground_truth` rỗng; `run_data_quality_checks` dùng `isna().any()` + `str.strip().eq("")` để chịu được NaN |

### Cách xác minh

```bash
cd "C:\Users\Lil'Pao0\Documents\Vin_AI\K4_Day10_Data-Pipeline-Data-Observability-5tuat"
python -c "import sys; sys.path.insert(0, 'src'); from pipelines.phase1 import main; main()"
python -c "import sys; sys.path.insert(0, 'src'); from pipelines.corruption_flow import main; main()"
```

- **Kết quả mong đợi:** Phase1 in 9 bước, baseline_metrics xuất hiện; corruption_flow in 11 bước, comparison report xuất hiện với 3 stage.
- **Kết quả thực tế:** `retrieval_hit_rate=1.0 / 0.75 / 1.0`, `mean_token_f1=0.822 / 0.774 / 0.822`, `quality=PASS/FAIL/PASS`, `is_fresh=true/false/true`.
- **Artifact/log:** `data/reports/phase1_report.md`, `data/reports/corruption_report.md`, `data/results/signal_change.json`, `data/quality/{baseline,corrupted,repaired}_quality.json`, `data/quality/{baseline,corrupted,repaired}_freshness_report.json`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Test set ban đầu `df.head(PER_TYPE)` lấy 3 row đầu → 12 câu nhưng `ground_truth_doc_ids` chỉ unique 3. `ground_truth` cho `summary` là `first_sentence(summary)` — bằng chính câu `qa.py` extract, làm `token_f1=1.0` cho mọi câu summary. Metrics bão hoà, không phản ánh retrieval quality.
- **Các phương án đã cân nhắc:**
  1. Giữ `head(PER_TYPE)`, đổi ground_truth paraphrase qua LLM.
  2. Giữ 3 paper, tăng `top_k` để buộc retrieval khó.
  3. Lấy `PER_TYPE * len(QUESTION_TYPES) = 12` row khác nhau, ground_truth `summary` dùng full cleaned summary.
- **Phương án đã chọn:** 3.
- **Lý do:** Mỗi câu ứng với 1 paper_id riêng → retrieval diversity. `qa.py` trả first_sentence còn `ground_truth` full summary → `token_f1` thấp hơn 1.0 ở câu summary, đo được agent behavior thực. Không cần thêm LLM call, không tốn chi phí.
- **Bằng chứng quyết định phù hợp:** Sau fix, `mean_token_f1` đổi `1.0 → 0.822`, summary token_f1 = 0.311, các loại khác = 1.0. `corrupted → repaired` delta phục hồi đúng 0.05.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `ImportError: cannot import name 'create_agent' from 'langchain.agents' (path\to\langchain\agents\__init__.py)`
- **Lệnh hoặc bước tái hiện:** Bất kỳ lệnh nào import `retrieval.agent` → `index.py` → `embeddings.py` → fail tại `from langchain.agents import create_agent`.
- **Nguyên nhân gốc:** `pyproject.toml` lock `langchain>=1.0.0` nhưng pip resolve về `langchain==0.3.30` (vì `langchain-openai 0.3.35` lock `langchain-core<1.0`). `langchain.agents.create_agent` chỉ xuất hiện từ `langchain 1.x`. Đây là phiên bản sai, không phải do code mình viết.
- **Cách xử lý:** Trong `src/retrieval/agent.py` đổi `from langchain.agents import create_agent` → `from langgraph.prebuilt import create_react_agent`. Đổi `tool` import từ `langchain.tools` → `langchain_core.tools`. Đổi params `model=`, `tools=`, `system_prompt=`, `name=` → `model=`, `tools=`, `state_modifier=` (langgraph ReAct API).
- **Cách xác minh sau khi sửa:** `python -c "from pipelines.phase1 import main; main()"` chạy đủ 9 bước, `pipeline complete` không raise. `data/results/baseline_metrics.json` xuất hiện đúng schema.
- **Điều học được:** Khi `pyproject.toml` khóa version range mà downstream package lock ngược về bản cũ, cần check `pip show` chứ không tin lockfile. `langchain 1.x` khác khá nhiều so với `0.3.x` — API `create_agent` chỉ có ở 1.x, ngược lại `create_react_agent` ổn định cả 2 phiên bản.

## 7. Hiểu biết về luồng end-to-end

1. Crossref REST API (`src/ingestion/crossref.py`) gọi `fetch_source_records`, raw response lưu `data/raw/crossref_response.json`, parse thành `list[PaperRecord]` lưu `data/raw/crossref_records.json`. `cleaning.build_clean_dataframe` chuẩn hoá 9 cột gồm `text_for_embedding`, dedupe theo `paper_id`, sort theo `published` desc. Save CSV/JSON. `LocalEmbeddingIndex.build(df)` encode `text_for_embedding` bằng Gemini embedding, nạp vào Chroma collection `papers-baseline` trong `data/chroma/`. Manifest ghi `data/embeddings/papers_embeddings.json`.
2. `build_test_set(df)` chọn 12 row khác nhau, sinh 12 câu với keyword routing. `ground_truth_doc_ids = [paper_id]` để metric `retrieval_hit` so với `result.retrieved_doc_ids` (top-k của index). `evaluate_pipeline` gọi `answer_question` cho mỗi câu, đo `retrieval_hit` (top-k có chứa ground_truth paper_id), `token_f1` (ground_truth vs predicted answer), `judge_score` (LLM-as-judge score 1-5).
3. Quality checks là predicate trên dataframe (row count, null, unique, freshness threshold). Freshness là subset — chỉ xét `age_days > threshold_days`, không phụ thuộc vào nội dung. Quality phát hiện defect cấu trúc, freshness phát hiện staleness theo thời gian.
4. Test set cố định đảm bảo baseline/corrupted/repaired cùng đo trên cùng tập câu hỏi — bất kỳ delta metric nào đều do dữ liệu đổi, không phải do câu hỏi khác.
5. Repair thành công khi (i) `overall_pass = true` ở quality check, (ii) `is_fresh = true`, (iii) metric retrieval_hit/mean_token_f1 quay về giá trị baseline ± tolerance. Trong bài này repaired = baseline chính xác (raw source không đổi).

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` | 1.0000 | 0.7500 | 1.0000 | Drop 25% khi corrupt do duplicate_rows + blank_summary + inject_noise + truncate_title phá vỡ exact lookup; phục hồi 100% khi rebuild từ raw. |
| `mean_token_f1`      | 0.8219 | 0.7736 | 0.8219 | Drop nhẹ 5.9% vì blank_summary + inject_noise trên câu summary làm `first_sentence` extract trả metadata rỗng/nhiễu. Phục hồi exact. |
| `judge_accuracy`     | 0.7500 | 0.7500 | 0.7500 | Không đổi qua 3 stage (liệt kê trong `unchanged_signals`). Judge LLM đánh giá causal, không phụ thuộc retrieval nhỏ. |
| `mean_judge_score`   | 4.2500 | 4.0833 | 4.2500 | Drop 0.17 điểm do 1-2 câu summary có answer rỗng → judge chấm 1 thay vì 5. |
| Quality checks         | PASS | FAIL | PASS | 3 check fail ở corrupted: `summary_min_chars`, `text_for_embedding_not_empty`, `paper_id_unique`, `freshness_threshold`. |
| Freshness status       | is_fresh (stale_rows=0) | stale (stale_rows=3) | is_fresh (stale_rows=0) | `stale_published_date` corruption shift published date 10 năm → 3 row vượt threshold 180 ngày. |

### Kết luận từ số liệu

1. [Corruption: `duplicate_rows` ×3 + `blank_summary` ×3 + `inject_summary_noise` ×3 + `truncate_title` ×3 + `stale_published_date` ×3 + `drop_latest_records` ×3] → [Quality check fail: `paper_id_unique`, `summary_min_chars`, `text_for_embedding_not_empty`, `freshness_threshold`, `age_days_valid`] → [Retrieval_hit_rate 1.0→0.75 (-25%), mean_token_f1 0.822→0.774 (-5.9%), mean_judge_score 4.25→4.08 (-0.17)].

2. [Repair: `load_raw_records` → `build_clean_dataframe` → rebuild index từ raw] → [Quality check pass, is_fresh true, stale_rows=0] → [Retrieval_hit_rate phục hồi 1.0, mean_token_f1 phục hồi 0.822, mean_judge_score phục hồi 4.25].

Corruption ảnh hưởng rõ nhất: `truncate_title` + `blank_summary` — chúng phá vỡ exact lookup trong `qa.py:lookup`. Trong 12 câu test, 3 câu hỏi dùng quoted title trong question để trigger exact lookup. Khi title bị truncate còn 12 chars, hoặc `text_for_embedding` rỗng do blank summary, lookup miss → fallback search cho ra paper khác → retrieval_hit giảm. `drop_latest_records` drop 3 paper mới nhất, một trong số đó nằm trong test set → `ground_truth_doc_ids` có paper_id không tồn tại trong index → judge chấm sai 0.

Kết quả khác kỳ vọng: `judge_accuracy` không đổi qua 3 stage. Kỳ vọng ban đầu là judge LLM sẽ thấy answer rỗng/sai rõ ràng ở corrupted → judge_accuracy giảm. Thực tế judge chỉ giảm 0.17 điểm trên 1 câu, không đủ để kéo `correct` boolean xuống dưới ngưỡng. Lý do có thể là judge LLM lenient — chấp nhận answer partial credit ngay cả khi retrieval miss. Cần check reasoning trong `baseline_answers.json` để xác nhận.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Test set diversity quan trọng hơn test set size. 12 câu trên 12 paper đa dạng cho metric variance hơn 24 câu trên 3 paper giống nhau.
2. Data quality phải được aggregate thành boolean để dễ pipeline OR — guard `validate_index_dataframe` chỉ chặn structure invariants, không chặn content quality. Quality check tách bạch cho phép index chạy trên partial data, observe nằm ở layer ngoài.
3. RAG agent metric có thể không phản ánh retrieval ngay lập tức. judge_accuracy ổn định trong khi retrieval_hit_rate giảm 25% → cần đo retrieval độc lập (precision, recall, MRR) thay vì chỉ dựa vào end-to-end judge.

### Nếu có thêm thời gian

Thêm retrieval metrics độc lập (precision@k, recall@k, MRR) cho `evaluate_pipeline` summary. Hiện tại chỉ `retrieval_hit_rate` (1 nếu top-k có chứa ground_truth paper_id, 0 nếu không) — quá binary. Precision@k đo bao nhiêu retrieved_doc_ids khớp ground_truth, MRR đo vị trí match. Cách đo: thêm `precision_at_k = len(intersection) / k`, `reciprocal_rank = 1/rank_of_first_match`, ghi vào summary. Cải thiện sẽ giúp báo cáo impact rõ hơn khi corruption chỉ ảnh hưởng thứ hạng retrieval chứ không phải có/không.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Phạm Quốc Bảo
**Ngày xác nhận:** 2026-08-06
