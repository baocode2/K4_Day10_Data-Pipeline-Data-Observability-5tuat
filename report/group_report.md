# Group Report — Day 10: Data Pipeline & Data Observability

> Dùng mẫu này cho báo cáo chung của nhóm 3–5 thành viên. Thay toàn bộ nội dung trong dấu `[ ]` bằng thông tin và kết quả thực tế. Xóa các dòng hướng dẫn không còn cần thiết trước khi nộp.

## 1. Thông tin bài nộp

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Khóa/Lớp         | [K3 hoặc K4]              |
| Tên nhóm         | [Tên hoặc mã nhóm]     |
| Repository         | [Đường dẫn repository] |
| Ngày hoàn thành | [YYYY-MM-DD]               |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| --: | --- | --- | --- | --- |
| 1 | Trần Đức Bảo | 2A202601472 | Vai trò 1 – Điều phối pipeline | `src/core/`, `src/pipelines/` (cấu hình, orchestration, release) |
| 2 | Trần Hoàng Long | 2A202601646 | Vai trò 2 – Ingestion owner | `src/ingestion/crossref.py`, `data/raw/` |
| 3 | Phạm Công Đạt | 2A202601406 | Vai trò 3 – Cleaning & corruption owner | `src/ingestion/cleaning.py`, `src/ingestion/corruption.py` |
| 4 | Nguyễn Sỹ Mạnh Cường | 2A202601040 | Vai trò 4 – RAG & agent owner | `src/retrieval/`, `data/embeddings/` |
| 5 | Phạm Quốc Bảo | 2A202601502 | Vai trò 5 – Evaluation & observability owner | `src/evaluation/`, `src/observability/` |

## 2. Tóm tắt kết quả

Viết từ 150–250 từ, trả lời ngắn gọn:

- Nhóm đã hoàn thành những phần nào?
- Baseline pipeline đã tạo ra các artifact nào?
- Corruption nào ảnh hưởng rõ nhất đến data quality hoặc agent?
- Repair đã phục hồi được chỉ số nào?
- Blocker hoặc giới hạn quan trọng nhất còn lại là gì?

**Tóm tắt của nhóm:**

[Viết phần tóm tắt tại đây.]

## 3. Kiến trúc và luồng dữ liệu

### Luồng end-to-end

Điều chỉnh sơ đồ dưới đây nếu cách triển khai thực tế của nhóm khác starter:

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
| Ingestion         | [Nguồn/input] | [Fetch, retry, parse...]   | [Đường dẫn artifact] | [Thành viên] |
| Cleaning          | [Input]        | [Các quy tắc chính]     | [Đường dẫn artifact] | [Thành viên] |
| Embedding/index   | [Input]        | [Model/index config]       | [Đường dẫn artifact] | [Thành viên] |
| Evaluation        | [Input]        | [Test set và metrics]     | [Đường dẫn artifact] | [Thành viên] |
| Observability     | [Input]        | [Quality/freshness checks] | [Đường dẫn artifact] | [Thành viên] |
| Corruption/repair | [Input]        | [Corruption và repair]    | [Đường dẫn artifact] | [Thành viên] |
| Orchestration     | [Input]        | [Thứ tự chạy]           | [Reports/metrics]        | [Thành viên] |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình             | Giá trị sử dụng |
| ---------------------------- | ------------------- |
| `LLM_PROVIDER`             | [Giá trị]         |
| `LLM_MODEL`                | [Giá trị]         |
| Embedding model              | [Giá trị]         |
| Số lượng Crossref records | [Giá trị]         |
| Retrieval`top_k`           | [Giá trị]         |
| Freshness threshold          | [Giá trị]         |
| Random seed, nếu có        | [Giá trị]         |

Không dán nội dung API key hoặc file `.env` vào báo cáo.

### Lệnh cài đặt

Chỉ giữ lại cách nhóm đã dùng.

```bash
uv sync
```

Hoặc:

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
| Corruption flow   | Chưa chạy — `src/pipelines/corruption_flow.py` còn `NotImplementedError` | — | — |

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
| Embedding model                          | Gemini embeddings (`GeminiEmbeddings`, `settings.embedding_model`) |
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

Lần chạy gần nhất: 2026-08-06 (sau khi pull raw/clean data mới nhất từ Vai trò 2/3), `python script/run_phase1.py` (12 câu hỏi).

| Metric                 |  Giá trị | Diễn giải                             |
| ---------------------- | --------: | --------------------------------------- |
| `retrieval_hit_rate` |    1.0000 | Cả 12/12 câu hỏi retrieval đúng document ground truth trong top-k=4 |
| `mean_token_f1`      |    1.0000 | Answer trích xuất từ metadata khớp hoàn toàn ground truth sau khi Role 3 làm sạch/chuẩn hóa lại dữ liệu |
| `judge_accuracy`     |    1.0000 | 12/12 câu được LLM judge (`gpt-4o`) chấm "correct" |
| `mean_judge_score`   |    5.0000 | Thang 1-5, tối đa |
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
| Ngưỡng freshness         | 180 ngày (`freshness_threshold_days`) |
| Trạng thái baseline      | Fresh (`is_fresh = true`, 0 stale rows) |
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

Giải thích cách repair đảm bảo dữ liệu được phục hồi từ nguồn đáng tin cậy thay vì chỉ che kết quả lỗi:

`corruption_flow.py` bước 7 gọi lại `load_raw_records(data/raw/crossref_records.json)` — **raw snapshot gốc, chưa từng bị corrupt** — rồi chạy lại `build_clean_dataframe()` từ đầu để tạo `papers_clean_repaired.*`. Đây không phải sửa tay file corrupted hay vá số liệu: repaired dataset được sinh độc lập, hoàn toàn từ nguồn tin cậy, nên nếu raw data đổi thì repair vẫn tái lập đúng.

## 10. So sánh baseline, corrupted và repaired

Nguồn: `data/reports/corruption_report.md`, sinh từ `baseline_metrics.json`/`corrupted_metrics.json`/`repaired_metrics.json` + `baseline_quality.json`/`corrupted_quality.json`/`repaired_quality.json`.

| Metric/signal             | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi | Nhận xét |
| -------------------------- | -------: | --------: | -------: | ------------------------: | ---------------: | ---------- |
| `retrieval_hit_rate`     |   1.0000 |    0.7500 |   1.0000 |                    -0.2500 |           +0.2500 | Corruption (chủ yếu drop + duplicate + stale date) làm giảm hit rate 25%; repair phục hồi 100% |
| `mean_token_f1`          |   0.8219 |    0.7736 |   0.8219 |                    -0.0484 |           +0.0484 | Giảm nhẹ do blank/noisy summary làm answer lệch; phục hồi hoàn toàn |
| `judge_accuracy`         |   0.7500 |    0.7500 |   0.7500 |                     0.0000 |            0.0000 | Không đổi — corruption trong lô này chưa đủ mạnh để đổi phán quyết đúng/sai của LLM judge trên các câu hỏi đang có |
| `mean_judge_score`       |   4.2500 |    4.1667 |   4.2500 |                    -0.0833 |           +0.0833 | Giảm nhẹ, phục hồi hoàn toàn |
| Quality checks pass/fail | n/a (không chạy riêng cho baseline trong report này) |      FAIL |     PASS |          PASS → FAIL |      FAIL → PASS | `paper_id_unique` và `summary_min_chars` là các check fail chính |
| Freshness status          | n/a (không chạy riêng cho baseline trong report này) |  FAIL (3 stale) | PASS (0 stale) |          Fresh → Stale |     Stale → Fresh | `stale_published_date` lùi 3 record 10 năm → vượt ngưỡng 180 ngày |

Hai kết luận nhân quả được hỗ trợ bởi artifact:

1. **`duplicate_rows` + `stale_published_date` (corruption) → `paper_id_unique`/`freshness_threshold` fail (`data/quality/corrupted_quality.json`) → `retrieval_hit_rate` giảm từ 1.0 xuống 0.75 (`data/results/corrupted_metrics.json`)** — vì `drop_latest_records` loại bỏ 3 record mà evaluation test set đang hỏi tới, agent không còn tài liệu nguồn để trả lời đúng ground truth.
2. **Repair (re-run cleaning từ `data/raw/`) → quality/freshness phục hồi hoàn toàn PASS/Fresh (`data/quality/repaired_quality.json`, `repaired_freshness_report.json`) → `retrieval_hit_rate` và `mean_token_f1` quay lại đúng bằng baseline (`data/results/repaired_metrics.json`)** — vì repaired dataset được build lại từ raw gốc, không kế thừa lỗi từ bản corrupted.

Lưu ý trung thực: `judge_accuracy` **không đổi** giữa 3 trạng thái (0.75 cả ba) — corruption trong lần chạy này không đủ để lật phán quyết "đúng/sai" của LLM judge, dù retrieval và token-F1 đã bị ảnh hưởng rõ. Không kết luận quá mức rằng mọi metric đều nhạy với corruption.

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** `script/run_corruption_flow.py` crash ở bước 3/11 ("Building corrupted embedding index"): `ValueError: Clean dataframe has 6 duplicate paper_id values (case-insensitive).`
- **Nguyên nhân:** Contract mismatch giữa hai module do hai người khác nhau phụ trách. `corrupt_clean_dataframe()` (`src/ingestion/corruption.py`, Vai trò 3) cố ý tạo `duplicate_rows` để test corruption `paper_id_unique`. `validate_index_dataframe()` (`src/retrieval/index.py`, Vai trò 4) lại cấm tuyệt đối duplicate `paper_id` khi build RAG index — hợp lý cho baseline sạch, nhưng chặn luôn cả dataset corrupted cố ý có duplicate.
- **Cách xử lý:** Không sửa `validate_index_dataframe()` (đó là contract đúng cho index) và không vá thủ công JSON kết quả. Thêm hàm `_dedupe_for_index()` trong `src/pipelines/corruption_flow.py`: dataset đưa vào `run_data_quality_checks()`/lưu CSV-JSON vẫn giữ nguyên duplicate (để quality check phát hiện đúng lỗi), nhưng dataset đưa vào `LocalEmbeddingIndex.build()` được dedupe theo `paper_id` (case-insensitive, giữ bản đầu) trước khi embed.
- **Cách xác minh:** `python script/run_corruption_flow.py` chạy hết 11/11 bước không lỗi; `data/quality/corrupted_quality.json` vẫn báo `paper_id_unique` FAIL (đúng ý đồ corruption), trong khi `data/embeddings/papers_embeddings.json` (collection `papers-corrupted`) có đúng 21 documents (24 - 3 duplicate).

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng   | Hướng cải thiện có thể kiểm chứng |
| --------------------- | -------------- | ----------------------------------------- |
| `judge_accuracy` không đổi giữa baseline/corrupted/repaired (0.75 cả ba) | Chưa chứng minh được corruption ảnh hưởng tới phán quyết đúng/sai của LLM judge, chỉ retrieval và token-F1 bị ảnh hưởng rõ | Tăng cường độ corruption (VD: `blank_summary`/`inject_summary_noise` tác động nhiều record hơn, hoặc nhắm đúng vào record có trong test set) rồi so `judge_accuracy` lại |
| Free-tier Gemini embedding API bị rate limit (429) khi chạy liên tiếp nhiều lần trong thời gian ngắn | Phải chờ ~30s và chạy lại thủ công; chưa có backoff tự động trong `LocalEmbeddingIndex`/`GeminiEmbeddings` | Thêm retry/backoff cho embed call (tương tự `_get_with_retry` đã có ở `crossref.py`) thay vì để lỗi 429 văng thẳng lên orchestration |
| `run_data_quality_checks`/`build_freshness_report` không so baseline cùng lúc trong `generate_corruption_report` (bảng Quality/Freshness comparison ở `corruption_report.md` để trống cột baseline) | Báo cáo so sánh thiếu 1 cột tham chiếu, phải lấy số baseline từ `phase1_report.md` riêng | Truyền thêm `baseline_quality`/`baseline_freshness` vào `generate_corruption_report()` trong `src/observability/reporting.py` để bảng so sánh đủ 3 cột |

## 13. Checklist trước khi nộp

- [ ] Thông tin nhóm và repository chính xác.
- [ ] Phân công khớp với module, artifact và kết quả thực tế.
- [ ] Lệnh tái hiện đã được chạy lại trên phiên bản dùng để nộp.
- [ ] Baseline, corrupted và repaired dùng cùng evaluation set.
- [ ] Bảng metrics khớp với các file trong `data/results/`.
- [ ] Quality/freshness conclusions khớp với `data/quality/`.
- [ ] Các đường dẫn báo cáo và artifact truy cập được.
- [ ] Mỗi thành viên đã hoàn thành báo cáo vai trò riêng.
- [ ] Không có `.env`, API key, token hoặc secret trong source, report, log hay ảnh.
