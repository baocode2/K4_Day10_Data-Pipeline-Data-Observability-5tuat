# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Khóa/Lớp         | K4              |
| Tên nhóm         | Nhóm 5tuat (5 thành viên)     |
| Repository         | https://github.com/baocode2/K4_Day10_Data-Pipeline-Data-Observability-5tuat |
| Ngày hoàn thành | 2026-08-06               |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| --: | --- | --- | --- | --- |
| 1 | Trần Đức Bảo | 2A202601472 | Vai trò 1 – Điều phối pipeline | `src/core/`, `src/pipelines/` (cấu hình, orchestration, release) |
| 2 | Trần Hoàng Long | 2A202601646 | Vai trò 2 – Ingestion owner | `src/ingestion/crossref.py`, `data/raw/` |
| 3 | Phạm Công Đạt | 2A202601406 | Vai trò 3 – Cleaning & corruption owner | `src/ingestion/cleaning.py`, `src/ingestion/corruption.py` |
| 4 | Nguyễn Sỹ Mạnh Cường | 2A202601040 | Vai trò 4 – RAG & agent owner | `src/retrieval/`, `data/embeddings/` |
| 5 | Phạm Quốc Bảo | 2A202601502 | Vai trò 5 – Evaluation & observability owner | `src/evaluation/`, `src/observability/` |

## 2. Tóm tắt kết quả

**Tóm tắt của nhóm:**

Nhóm đã hoàn thành cả hai pha của bài lab end-to-end: baseline pipeline (ingestion Crossref → cleaning → embedding/ChromaDB → evaluation → quality/freshness → report) và corruption/repair flow (corrupt có kiểm soát → re-index → re-evaluate → repair từ raw → comparison report). Baseline tạo đủ artifact theo checklist: `data/raw/`, `data/clean/`, `data/embeddings/`, `data/eval/test_set.json`, `data/results/baseline_metrics.json`, `data/quality/`, `data/reports/phase1_report.md`. Trong 6 loại corruption (drop latest, blank summary, inject noise, truncate title, stale date, duplicate rows), `drop_latest_records` ảnh hưởng rõ nhất vì xóa đúng một record đang là `ground_truth_doc_ids` trong test set, kéo `retrieval_hit_rate` từ 1.0 xuống 0.75; `duplicate_rows` và `stale_published_date` làm quality/freshness chuyển từ PASS sang FAIL. Repair (rebuild lại từ đúng raw snapshot, không vá tay dữ liệu corrupted) phục hồi 100% `retrieval_hit_rate`, `mean_token_f1`, `mean_judge_score` và cả quality/freshness về đúng baseline. Blocker lớn nhất đã xử lý là contract mismatch giữa `ingestion/corruption.py` (cố ý tạo duplicate `paper_id`) và `retrieval/index.py` (cấm duplicate khi build index) — xử lý bằng cách dedupe riêng cho view đưa vào index, giữ nguyên duplicate trong artifact để quality gate vẫn phát hiện đúng lỗi. Giới hạn còn lại: `judge_accuracy` không đổi giữa 3 trạng thái (metric nhị phân trên 12 mẫu kém nhạy hơn `mean_judge_score`), và `truncate_title` hiện "vô hình" với bộ quality check vì chưa có rule kiểm tra độ dài tối thiểu cho `title`.

## 3. Kiến trúc và luồng dữ liệu

### Luồng end-to-end

```text
Crossref API
    -> raw response/raw records
    -> cleaning và data modeling
    -> embedding + ChromaDB index
    -> evaluation baseline
    -> quality/freshness reports
    -> corruption
    -> re-index và re-evaluate
    -> repair từ dữ liệu nguồn
    -> comparison report
```

### Trách nhiệm của từng khối

| Khối             | Input          | Xử lý chính             | Output/artifact          | Owner          |
| ----------------- | -------------- | -------------------------- | ------------------------ | -------------- |
| Ingestion         | Crossref REST API (`https://api.crossref.org/works`) | Fetch có retry/backoff (429/503), parse payload thành `PaperRecord` với `paper_id = safe_slug(DOI)` | `data/raw/crossref_response.json`, `data/raw/crossref_records.json` | Trần Hoàng Long (2A202601646) — Vai trò 2 |
| Cleaning          | `list[PaperRecord]` từ raw | Loại record thiếu field/summary quá ngắn/date không parse được, chuẩn hóa authors/categories, tính `age_days`, `text_for_embedding`, dedupe `paper_id` | `data/clean/papers_clean.csv/json`, `cleaning_report.json` | Phạm Công Đạt (2A202601406) — Vai trò 3 |
| Embedding/index   | Clean dataframe (9 cột cốt lõi) | Validate contract, gọi Gemini embeddings (`gemini-embedding-001`), nạp ChromaDB persistent, 3 collection riêng biệt | `data/embeddings/papers_embeddings*.json`, `data/chroma/` (`papers-baseline/-corrupted/-repaired`) | Nguyễn Sỹ Mạnh Cường (2A202601040) — Vai trò 4 |
| Evaluation        | Clean dataframe + `Settings` | Sinh 12 câu hỏi (4 loại × 3), evaluate qua agent, tính `retrieval_hit_rate`/`token_f1`/judge score | `data/eval/test_set.json`, `data/results/*_metrics.json`, `*_answers.json` | Phạm Quốc Bảo (2A202601502) — Vai trò 5 |
| Observability     | Clean/corrupted/repaired dataframe | 7 quality check (row_count, paper_id_unique, title/summary/text_for_embedding, age_days_valid, freshness_threshold) + freshness report | `data/quality/*_quality.json`, `*_freshness_report.json`, `data/results/signal_change.json` | Phạm Quốc Bảo (2A202601502) — Vai trò 5 |
| Corruption/repair | Baseline clean dataframe + raw records | 6 kịch bản corruption có log kiểm toán; repair = rebuild lại từ raw, không vá tay | `data/clean/*_corrupted.*`, `*_repaired.*`, `data/results/corruption_log.json` | Phạm Công Đạt (2A202601406) — Vai trò 3 |
| Orchestration     | Toàn bộ module trên | Ghép `phase1.py` (baseline, 9 bước) và `corruption_flow.py` (corrupt→index→evaluate→quality→repair→so sánh, 11 bước); xử lý contract mismatch liên vai trò | `data/reports/phase1_report.md`, `data/reports/corruption_report.md` | Trần Đức Bảo (2A202601472) — Vai trò 1 |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình             | Giá trị sử dụng |
| ---------------------------- | ------------------- |
| `LLM_PROVIDER`             | `openai`         |
| `LLM_MODEL`                | `gpt-4o`         |
| Embedding model              | `gemini-embedding-001` (Google Generative AI Embeddings, qua `GOOGLE_API_KEY`) |
| Số lượng Crossref records | 24 (`max_results = 24`) |
| Retrieval`top_k`           | 4         |
| Freshness threshold          | 180 ngày         |
| Random seed, nếu có        | Không set seed rõ ràng; `build_llm(temperature=0.0)` để giảm variance giữa các lần chạy judge/agent |

Không dán nội dung API key hoặc file `.env` vào báo cáo.

### Lệnh cài đặt

```bash
uv sync
```

Hoặc (nếu không có `uv`, dùng `pip` trong `.venv` đã activate):

```bash
python -m pip install -e .
```

### Lệnh chạy

Baseline:

```bash
uv run python script/run_phase1.py
```

Hoặc với môi trường `pip` đã kích hoạt:

```bash
python script/run_phase1.py
```

Corruption flow:

```bash
uv run python script/run_corruption_flow.py
```

Hoặc với môi trường `pip` đã kích hoạt:

```bash
python script/run_corruption_flow.py
```

### Kết quả tái hiện

| Lệnh             | Trạng thái | Thời điểm chạy gần nhất | Bằng chứng                         |
| ----------------- | ------------ | ----------------------------- | ------------------------------------ |
| Baseline pipeline | Thành công | 2026-08-06                    | `data/reports/phase1_report.md`, `data/results/baseline_metrics.json` |
| Corruption flow   | Thành công (11/11 bước) | 2026-08-06 | `data/reports/corruption_report.md`, `data/results/corrupted_metrics.json`, `repaired_metrics.json`, `corruption_log.json`, `signal_change.json` |

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính                | Giá trị                             |
| --------------------------- | ------------------------------------- |
| Source                      | Crossref REST API (`https://api.crossref.org/works`) |
| Query/filter                | `query=agentic retrieval augmented generation large language model`, `filter=from-pub-date:<180 ngày>,has-abstract:true` |
| Thời điểm lấy dữ liệu | 2026-08-06 (snapshot trong `data/raw/`, không refetch mỗi lần chạy trừ khi `REFRESH_SOURCE=1`) |
| Số record nhận được    | 24 (`max_results = 24`)             |
| Cơ chế retry/backoff      | `_get_with_retry()` trong `src/ingestion/crossref.py`: exponential backoff + jitter, tôn trọng `Retry-After`, retry cho HTTP 429/503, tối đa 5 lần |

### Raw và clean schema

Khóa tại CP2 (2026-08-06), theo `CLEAN_COLUMNS` trong `src/ingestion/cleaning.py`. Không đổi tên/thứ tự cột này khi build test set hoặc index.

| Trường                | Kiểu dữ liệu   | Bắt buộc? | Ý nghĩa                                    | Xử lý khi thiếu/sai                              |
| ----------------------- | ---------------- | ---------- | --------------------------------------------- | ---------------------------------------------------- |
| `paper_id`            | string          | Có        | Slug ổn định từ DOI, khóa chính            | Thiếu → loại record (`missing_paper_id`)          |
| `title`               | string          | Có        | Tiêu đề bài báo                          | Thiếu → loại record (`missing_title`)             |
| `summary`             | string          | Có        | Abstract đã strip HTML/entity, tối thiểu 100 ký tự | Thiếu/quá ngắn → loại (`missing_summary`/`summary_too_short`) |
| `authors`             | list[string]    | Không     | Danh sách tác giả đã dedupe                | Rỗng nếu Crossref không có                          |
| `authors_joined`      | string          | Không     | `authors` nối bằng `, `                    | Rỗng nếu `authors` rỗng                            |
| `categories`          | list[string]    | Không     | Danh sách subject Crossref, đã dedupe      | Rỗng nếu không có                                    |
| `categories_joined`   | string          | Không     | `categories` nối bằng `, `                 | Rỗng nếu rỗng                                       |
| `primary_category`   | string          | Không     | `categories[0]` hoặc field gốc             | Rỗng nếu không có category                           |
| `published`           | date (ISO)      | Có        | Ngày công bố, đã parse UTC                | Không parse được → loại (`invalid_published`)     |
| `updated`             | date (ISO)      | Không     | Ngày cập nhật, fallback về `published`    | —                                                    |
| `age_days`            | int             | Derived   | `run_day - published`, không âm            | Tính lại mỗi lần build, không lưu cứng               |
| `summary_chars`       | int             | Derived   | `len(summary)`                              | —                                                    |
| `text_for_embedding`  | string          | Derived   | `Title: {title} \| Authors: {authors_joined} \| Summary: {summary}` | Rỗng nếu title/summary rỗng (đã bị loại từ trước) |
| `abs_url`             | string          | Không     | Link bài báo                              | Có thể rỗng                                          |
| `pdf_url`             | string          | Không     | Link PDF nếu Crossref trả về               | Có thể rỗng                                          |
| `comment`             | string          | Không     | Tên journal/container-title                | Có thể rỗng                                          |

Dedupe key: `paper_id` (case-insensitive), giữ bản ghi hợp lệ đầu tiên.

### Quy tắc cleaning

Số liệu lấy từ `data/clean/cleaning_report.json` (chạy lần gần nhất 2026-08-06, input 24 raw records):

| Quy tắc                                             | Quality dimension | Số record bị tác động | Cách xác minh                          |
| ----------------------------------------------------- | ------------------ | -------------------------: | ----------------------------------------- |
| Loại record thiếu `paper_id`                        | Completeness       |                          0 | `cleaning_report.json → rejected.missing_paper_id` |
| Loại record thiếu `title`                           | Completeness       |                          0 | `rejected.missing_title`                |
| Loại record thiếu hoặc rỗng `summary`               | Completeness       |                          0 | `rejected.missing_summary`              |
| Loại record có `summary` < 100 ký tự                | Validity           |                          0 | `rejected.summary_too_short`            |
| Loại record có `published` không parse được         | Validity           |                          0 | `rejected.invalid_published`            |
| Dedupe theo `paper_id` (case-insensitive)            | Uniqueness         |                          0 | `duplicates_removed`                     |

Lần chạy gần nhất: 24 raw records → 24 clean records (không có record nào bị loại hoặc trùng). Cần chạy lại và cập nhật bảng này nếu bộ raw data thay đổi.

Giải thích cách nhóm tạo `text_for_embedding`, document ID và `age_days`:

- `paper_id` (document ID): `safe_slug(doi)` trong `src/ingestion/crossref.py` — chuẩn hóa DOI thành slug ổn định, dùng xuyên suốt raw → clean → index → test set để tránh lệch ID giữa các bước.
- `text_for_embedding`: ghép `Title: {title} | Authors: {authors_joined} | Summary: {summary}` trong `build_text_for_embedding()`; `categories` cố ý không đưa vào nội dung embedding, chỉ giữ làm metadata.
- `age_days`: `max(0, (run_day - published_date).days)`, tính tại thời điểm build (không lưu cứng), dùng làm input cho freshness signal ở Checkpoint 1/3.

## 6. Evaluation setup

| Thành phần                             | Cấu hình thực tế          |
| ---------------------------------------- | ----------------------------- |
| Số câu hỏi                            | 12 (3 câu × 4 loại)          |
| Các`question_type`                    | `summary`, `authors`, `date`, `categories` |
| Ground-truth document ID                 | `ground_truth_doc_ids` = `paper_id` của record nguồn trong `papers_clean.csv` (không tự bịa ID) |
| Embedding model                          | Gemini embeddings (`GeminiEmbeddings`, model `gemini-embedding-001`) |
| Vector store/collection                  | ChromaDB `PersistentClient`, collection `papers-baseline` (24 documents) |
| Retrieval`top_k`                       | 4 |
| LLM provider/model                       | `openai` / `gpt-4o` (theo `.env`), judge dùng cùng LLM qua `build_llm()` |
| Test set dùng chung cho ba trạng thái | `data/eval/test_set.json` — `phase1.py` chỉ build lại khi `REFRESH_TEST_SET=1`, mặc định tái dùng file cũ |

Giải thích vì sao test set được giữ nguyên khi đánh giá baseline, corrupted và repaired:

`phase1.py` chỉ gọi `build_test_set()` khi `settings.refresh_test_set` bật hoặc file chưa tồn tại (`src/pipelines/phase1.py`, bước 4/9). Vì corruption flow (CP5) sẽ dùng lại cùng `test_set.json` này để evaluate corrupted/repaired, nên số liệu ba trạng thái so sánh được trên cùng bộ câu hỏi và cùng ground truth.

## 7. Kết quả baseline

### Artifact checklist

| Artifact                 | Đường dẫn thực tế                | Trạng thái | Ghi chú   |
| ------------------------ | -------------------------------------- | ------------ | ---------- |
| Raw response/records     | `data/raw/crossref_response.json`, `crossref_records.json` | Có | 24 records từ Crossref |
| Cleaned dataset          | `data/clean/papers_clean.csv`, `.json` | Có | 24 raw → 24 clean, 0 bị loại (`cleaning_report.json`) |
| Embedding manifest/index | `data/embeddings/papers_embeddings.json`, ChromaDB `papers-baseline` | Có | 24 documents đã index |
| Evaluation set           | `data/eval/test_set.json`            | Có | 12 câu hỏi, 4 loại, doc_id khớp index |
| Baseline metrics         | `data/results/baseline_metrics.json` | Có | Xem bảng dưới |
| Quality/freshness        | `data/quality/baseline_quality.json`, `freshness_report.json` | Có | overall_pass = true, is_fresh = true |
| Baseline report          | `data/reports/phase1_report.md`      | Có | Sinh tự động từ `generate_phase1_report()` |

### Baseline metrics

Lần chạy gần nhất: 2026-08-06, `python script/run_phase1.py` (12 câu hỏi, test set sau khi Vai trò 5 mở rộng ra 12 paper riêng biệt để tăng độ đa dạng).

| Metric                 |  Giá trị | Diễn giải                             |
| ---------------------- | --------: | --------------------------------------- |
| `retrieval_hit_rate` |    1.0000 | 12/12 câu hỏi retrieval đúng document ground truth trong top-k=4 |
| `mean_token_f1`      |    0.8219 | Không phải 1.0 vì `ground_truth` của loại câu `summary` là full summary trong khi answer chỉ trích câu đầu tiên (`first_sentence`) — đo đúng hành vi thật của agent thay vì bão hòa ở 1.0 |
| `judge_accuracy`     |    0.7500 | 9/12 câu được LLM judge (`gpt-4o`) chấm "correct" |
| `mean_judge_score`   |    4.2500 | Thang 1-5 |
| Ragas                 | Bỏ qua | `RUN_RAGAS` chưa bật (mặc định tắt vì chạy lâu) |

## 8. Data quality và freshness

### Quality checks

| Check                          | Quality dimension | Ngưỡng/kỳ vọng           | Kết quả baseline | Bằng chứng |
| ------------------------------- | ------------------ | -------------------------- | ------------------- | ------------ |
| `row_count`                   | Completeness       | ≥ 8 rows                  | PASS (24 rows)      | `data/quality/baseline_quality.json` |
| `paper_id_unique`             | Uniqueness          | 0 null, 0 duplicate        | PASS (0, 0)          | nt |
| `title_not_null`              | Completeness       | 0 missing                  | PASS                 | nt |
| `summary_min_chars`           | Validity            | ≥ 50 ký tự                | PASS                 | nt |
| `text_for_embedding_not_empty`| Validity            | 0 rỗng                    | PASS                 | nt |
| `age_days_valid`              | Validity            | ≥ 0, không NaN            | PASS                 | nt |
| `freshness_threshold`         | Freshness           | 0 record > 180 ngày        | PASS (0 stale)        | nt |

### Freshness

| Thuộc tính               | Giá trị                           |
| -------------------------- | ----------------------------------- |
| Freshness được đo tại | `data/clean/papers_clean.csv` (cột `published`/`age_days`) tại thời điểm chạy baseline |
| Timestamp mới nhất       | 2026-08-01                          |
| Timestamp cũ nhất        | 2026-02-12 (175 ngày tuổi, vẫn trong ngưỡng) |
| Ngưỡng freshness         | 180 ngày (`freshness_threshold_days`) |
| Trạng thái baseline      | Fresh (`is_fresh = true`, 0 stale rows) — `data/quality/freshness_report.json` |
| Lý do                     | Toàn bộ 24 record có `published` trong 180 ngày gần nhất do query Crossref đã lọc `from-pub-date` theo đúng ngưỡng này |

## 9. Corruption scenarios và repair

Lần chạy gần nhất: 2026-08-06, `python script/run_corruption_flow.py`, input 24 baseline records → output 24 corrupted records (21 unique sau dedupe cho index).

| Corruption            | Cách tạo                                              | Record bị tác động | Quality signal kỳ vọng                          | Tác động thực tế                                                   | Cách repair |
| ----------------------- | -------------------------------------------------------- | -------------------: | -------------------------------------------------- | ---------------------------------------------------------------------- | ------------- |
| `drop_latest_records`  | Xóa 3 record mới nhất theo `published`                 |                    3 | `row_count`, `freshness_threshold`, `age_days_valid` | Số record giảm 24→21 trước khi các corruption khác áp dụng          | Repair đọc lại 24 record gốc từ `data/raw/` |
| `blank_summary`        | Set `summary = ""` cho 3 record                        |                    3 | `summary_min_chars`, `text_for_embedding_not_empty` | Góp phần khiến `corrupted_quality.overall_pass = false`              | nt |
| `inject_summary_noise` | Thêm chuỗi rác `[CORRUPTED_NOISE] zxqv 000 !!!...` vào summary |                    3 | `summary_min_chars` (nhiễu nội dung)                | Làm nhiễu context đưa vào embedding/answer                             | nt |
| `truncate_title`       | Cắt title còn 12 ký tự                                  |                    3 | `title_not_null` (không rỗng nhưng sai lệch)        | Title mất ý nghĩa, ảnh hưởng lookup theo title                         | nt |
| `stale_published_date` | Lùi `published` 10 năm                                 |                    3 | `freshness_threshold`                               | `corrupted_freshness.is_fresh = false`, 3 stale rows                  | nt |
| `duplicate_rows`       | Nhân đôi 3 record (thêm bản copy)                        |                    3 | `paper_id_unique`                                   | `corrupted_quality.overall_pass = false`; phải dedupe riêng trước khi build index (xem mục 11) | nt |

Corruption log:

- Đường dẫn: `data/results/corruption_log.json`
- Trạng thái: Có
- Nhận xét: Log đủ 6 loại corruption, mỗi loại ghi rõ `record_ids`, `parameters`, `before_count`/`after_count` — có thể truy vết từng bản ghi bị tác động.

**Đối chiếu "kỳ vọng" với "thực tế" bằng `data/results/signal_change.json`** (map từng corruption event sang check thực sự fail, do Vai trò 5 xây dựng):

- `drop_latest_records` kỳ vọng làm fail 3 check (`row_count`, `freshness_threshold`, `age_days_valid`) nhưng **thực tế chỉ `freshness_threshold` fail** — `row_count` không đổi vì `duplicate_rows` bù lại đúng số dòng đã bị xóa (24 → 21 → 24).
- `truncate_title` **không kích hoạt bất kỳ check nào** (`observed_failing_checks: []`) — `title_not_null` hiện chỉ kiểm tra rỗng/null, không kiểm tra độ dài tối thiểu, nên corruption này đang "vô hình" với bộ quality check (xem thêm mục 12).
- `blank_summary`, `inject_summary_noise`, `stale_published_date`, `duplicate_rows` đều trip đúng check kỳ vọng của chúng.

Đây là bằng chứng cụ thể để không kết luận quá mức "mọi corruption đều bị phát hiện" — chỉ 4/6 loại thực sự bị quality gate bắt được đúng như thiết kế.

Giải thích cách repair đảm bảo dữ liệu được phục hồi từ nguồn đáng tin cậy thay vì chỉ che kết quả lỗi:

`corruption_flow.py` bước 7 gọi lại `load_raw_records(data/raw/crossref_records.json)` — **raw snapshot gốc, chưa từng bị corrupt** — rồi chạy lại `build_clean_dataframe()` từ đầu để tạo `papers_clean_repaired.*`. Đây không phải sửa tay file corrupted hay vá số liệu: repaired dataset được sinh độc lập, hoàn toàn từ nguồn tin cậy, nên nếu raw data đổi thì repair vẫn tái lập đúng.

## 10. So sánh baseline, corrupted và repaired

Nguồn: `data/reports/corruption_report.md`, sinh từ `baseline_metrics.json`/`corrupted_metrics.json`/`repaired_metrics.json` + `baseline_quality.json`/`corrupted_quality.json`/`repaired_quality.json`.

| Metric/signal             | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi | Nhận xét |
| -------------------------- | -------: | --------: | -------: | ------------------------: | ---------------: | ---------- |
| `retrieval_hit_rate`     |   1.0000 |    0.7500 |   1.0000 |                    -0.2500 |           +0.2500 | Corruption (chủ yếu `drop_latest_records`) làm giảm hit rate 25%; repair phục hồi 100% |
| `mean_token_f1`          |   0.8219 |    0.7736 |   0.8219 |                    -0.0484 |           +0.0484 | Giảm nhẹ do blank/noisy summary làm answer lệch; phục hồi hoàn toàn |
| `judge_accuracy`         |   0.7500 |    0.7500 |   0.7500 |                     0.0000 |            0.0000 | Không đổi — nằm trong `unchanged_signals` của `signal_change.json`; metric nhị phân trên 12 mẫu kém nhạy hơn `mean_judge_score` |
| `mean_judge_score`       |   4.2500 |    4.0833 |   4.2500 |                    -0.1667 |           +0.1667 | Giảm nhẹ, phục hồi hoàn toàn |
| Quality checks pass/fail | PASS | FAIL | PASS | PASS → FAIL | FAIL → PASS | `paper_id_unique` và `summary_min_chars` là các check fail chính (`data/quality/baseline_quality.json` → `corrupted_quality.json` → `repaired_quality.json`) |
| Freshness status          | PASS (0 stale) | FAIL (3 stale) | PASS (0 stale) | Fresh → Stale | Stale → Fresh | `stale_published_date` lùi 3 record 10 năm → vượt ngưỡng 180 ngày (`data/quality/freshness_report.json` → `corrupted_freshness_report.json` → `repaired_freshness_report.json`) |

Hai kết luận nhân quả được hỗ trợ bởi artifact:

1. **`drop_latest_records` (corruption) → `freshness_threshold` fail (`data/quality/corrupted_quality.json`, xác nhận qua `signal_change.json`) → `retrieval_hit_rate` giảm từ 1.0 xuống 0.75 (`data/results/corrupted_metrics.json`)** — vì record bị xóa nằm trong `ground_truth_doc_ids` của test set, agent không còn tài liệu nguồn để trả lời đúng ground truth. `duplicate_rows` (→ `paper_id_unique` fail) và `blank_summary`/`inject_summary_noise` (→ `summary_min_chars` fail) cộng thêm vào việc `corrupted_quality.overall_pass = false` nhưng không phải nguyên nhân chính của việc giảm hit rate.
2. **Repair (re-run cleaning từ `data/raw/`) → quality/freshness phục hồi hoàn toàn PASS/Fresh (`data/quality/repaired_quality.json`, `repaired_freshness_report.json`) → `retrieval_hit_rate` và `mean_token_f1` quay lại đúng bằng baseline (`data/results/repaired_metrics.json`)** — vì repaired dataset được build lại từ raw gốc, không kế thừa lỗi từ bản corrupted.

Lưu ý trung thực: `judge_accuracy` **không đổi** giữa 3 trạng thái (0.75 cả ba, xem `unchanged_signals` trong `signal_change.json`) — corruption trong lần chạy này không đủ để lật phán quyết "đúng/sai" của LLM judge, dù retrieval và token-F1 đã bị ảnh hưởng rõ. Không kết luận quá mức rằng mọi metric đều nhạy với corruption.

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** `script/run_corruption_flow.py` crash ở bước 3/11 ("Building corrupted embedding index"): `ValueError: Clean dataframe has 6 duplicate paper_id values (case-insensitive).`
- **Nguyên nhân:** Contract mismatch giữa hai module do hai người khác nhau phụ trách. `corrupt_clean_dataframe()` (`src/ingestion/corruption.py`, Vai trò 3) cố ý tạo `duplicate_rows` để test corruption `paper_id_unique`. `validate_index_dataframe()` (`src/retrieval/index.py`, Vai trò 4) lại cấm tuyệt đối duplicate `paper_id` khi build RAG index — hợp lý cho baseline sạch, nhưng chặn luôn cả dataset corrupted cố ý có duplicate.
- **Cách xử lý:** Không sửa `validate_index_dataframe()` (đó là contract đúng cho index) và không vá thủ công JSON kết quả. Thêm hàm `_dedupe_for_index()` trong `src/pipelines/corruption_flow.py`: dataset đưa vào `run_data_quality_checks()`/lưu CSV-JSON vẫn giữ nguyên duplicate (để quality check phát hiện đúng lỗi), nhưng dataset đưa vào `LocalEmbeddingIndex.build()` được dedupe theo `paper_id` (case-insensitive, giữ bản đầu) trước khi embed.
- **Cách xác minh:** `python script/run_corruption_flow.py` chạy hết 11/11 bước không lỗi; `data/quality/corrupted_quality.json` vẫn báo `paper_id_unique` FAIL (đúng ý đồ corruption), trong khi `data/embeddings/papers_embeddings.json` (collection `papers-corrupted`) có đúng 21 documents (24 - 3 duplicate).

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng   | Hướng cải thiện có thể kiểm chứng |
| --------------------- | -------------- | ----------------------------------------- |
| `judge_accuracy` không đổi giữa baseline/corrupted/repaired (0.75 cả ba, chỉ 12 mẫu) | Metric nhị phân trên tập nhỏ kém nhạy — 1-2 câu đổi kết quả chưa đủ đổi tỷ lệ; chưa chứng minh được corruption ảnh hưởng tới phán quyết đúng/sai của LLM judge | Tăng cường độ corruption (nhắm đúng nhiều record hơn trong test set) hoặc bổ sung metric liên tục (`mean_judge_score` đã nhạy hơn: 4.25 → 4.08) thay vì chỉ nhìn accuracy nhị phân |
| `truncate_title` không kích hoạt bất kỳ quality check nào (`observed_failing_checks: []` trong `signal_change.json`) | Một loại corruption có chủ đích nhưng hoàn toàn "vô hình" với observability hiện tại — không ai biết title đã bị hỏng nếu chỉ nhìn quality report | Thêm check độ dài tối thiểu cho `title` (VD: `title_min_chars`) trong `src/observability/quality.py`, tương tự `summary_min_chars` |
| Rate-limit retry (429 `RESOURCE_EXHAUSTED` từ Gemini free-tier) mới chỉ có trong `corruption_flow.py` (`_with_rate_limit_retry`), chưa áp dụng cho `phase1.py`/`GeminiEmbeddings` nói chung | Baseline pipeline vẫn có thể crash nếu chạy nhiều lần liên tiếp trong thời gian ngắn | Đưa `_with_rate_limit_retry` (hoặc tương đương) vào `retrieval/embeddings.py` để dùng chung cho mọi pipeline gọi embedding, không riêng corruption flow |

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm và repository chính xác.
- [x] Phân công khớp với module, artifact và kết quả thực tế (đối chiếu với 5 báo cáo cá nhân: `individual_01472.md`, `individual_report_Long_2A202601646.md`, `individual_2A202601406.md`, `individual_report_01040.md`, `individual_2A202601502.md`).
- [x] Lệnh tái hiện đã được chạy lại trên phiên bản dùng để nộp (baseline và corruption flow đều chạy thành công 2026-08-06).
- [x] Baseline, corrupted và repaired dùng cùng evaluation set (`data/eval/test_set.json`, không refresh giữa 3 lần evaluate).
- [x] Bảng metrics khớp với các file trong `data/results/` (baseline/corrupted/repaired metrics + `signal_change.json`).
- [x] Quality/freshness conclusions khớp với `data/quality/` (baseline/corrupted/repaired quality + freshness report).
- [x] Các đường dẫn báo cáo và artifact truy cập được.
- [x] Mỗi thành viên đã hoàn thành báo cáo vai trò riêng.
- [x] Không có `.env`, API key, token hoặc secret trong source, report, log hay ảnh (đã quét regex API key trong `report/` và `data/`, `.env` nằm trong `.gitignore`).
