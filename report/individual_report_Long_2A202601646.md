# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin        | Nội dung                                                                        |
| ----------------- | -------------------------------------------------------------------------------- |
| Họ và tên        | Trần Hoàng Long                                                                  |
| MSSV              | 2A202601646                                                                      |
| Khóa/Lớp         | K4                                                                               |
| Tên nhóm         | Nhóm 5                                                                           |
| Vai trò chính    | Vai trò 2 — Ingestion owner (Crossref + raw lineage)                          |
| Repository         | https://github.com/baocode2/K4_Day10_Data-Pipeline-Data-Observability-5tuat     |
| Ngày hoàn thành | 2026-08-06                                                                       |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| ------------------ | --------------------- | ---------------- | ----------------- | ---------- |
| Parse Crossref payload thành record chuẩn | `src/ingestion/crossref.py::parse_crossref_payload` | JSON payload thô từ Crossref (`message.items`) | `list[PaperRecord]` với `paper_id` ổn định (`safe_slug(DOI)`), title/summary đã strip HTML và chuẩn hoá whitespace | Hoàn thành |
| Fetch nguồn có retry/backoff | `src/ingestion/crossref.py::fetch_source_records`, `_get_with_retry` | `Settings` (`source_query`, `source_filter`, `max_results`) | `data/raw/crossref_response.json` (raw thô) + `data/raw/crossref_records.json` (đã parse) | Hoàn thành |
| Load lại raw snapshot không gọi mạng | `src/ingestion/crossref.py::load_raw_records` | `data/raw/crossref_records.json` | `list[PaperRecord]` tái tạo từ snapshot, dùng cho CP2/CP3/CP5/CP6 | Hoàn thành |
| Test coverage cho vai trò 2 (CP0–CP6) | `tests/test_role2_cp0_fetch_retry.py`, `test_role2_cp1_raw_lineage.py`, `..._cp2_index_lineage_and_freeze.py`, `..._cp3_baseline_integrity.py`, `..._cp5_corruption_source_guard.py`, `..._cp6_repair_lineage_and_secrets.py` | Source code ở trên + `data/raw`, `data/clean`, `data/embeddings`, `.gitignore` | 37 test case (6 file) pass, bao phủ đủ 6/6 checkpoint có việc thật của role | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --------- | ------------------------------ | -------- |
| Đối chiếu file phân công (`phan-cong-day-10-data-pipeline-4h(2).html`, Nhóm 5, Vai trò 2) với `tests/` để tìm gap coverage | Toàn nhóm, chất lượng bộ test chung | Phát hiện checkpoint CP0 (fetch + retry/backoff) chưa có test nào; viết bổ sung `test_role2_cp0_fetch_retry.py` để lấp gap |
| Xác minh `.gitignore`/raw response không rò rỉ API key (CP6 shared rule) | Toàn nhóm, an toàn repo | `test_dotenv_is_git_ignored` và `test_raw_response_artifact_has_no_obvious_leaked_api_key` pass |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| ---------------------- | ----------------------------- | ------------------- | --------------- |
| Fetch + lưu raw Crossref response trước khi parse | `fetch_source_records`, `data/raw/crossref_response.json`, `data/raw/crossref_records.json` | 24 items trong raw response → 24 `PaperRecord` sau parse (không mất record nào ở lần chạy thật) | `uv run pytest tests/test_role2_cp0_fetch_retry.py -v` |
| Retry/backoff cho Crossref 429/503 | `_get_with_retry` | Backoff mũ (`base_delay * 2**attempt`) + tôn trọng header `Retry-After`; fail nhanh với status không retryable | `uv run pytest tests/test_role2_cp0_fetch_retry.py -v` (8/8 pass, mock `requests.get`) |
| Lineage raw → clean → index nhất quán cho một `paper_id` mẫu | `load_raw_records`, `data/clean/papers_clean.json`, `data/embeddings/papers_embeddings.json` | Cùng `title`, `abs_url`, `pdf_url`, `published` xuyên suốt 3 tầng dữ liệu | `uv run pytest tests/test_role2_cp2_index_lineage_and_freeze.py -v` |
| Đảm bảo baseline không fetch lại nguồn khi `REFRESH_SOURCE=false` | `load_raw_records`, `SETTINGS.refresh_source` | Baseline tái lập được từ snapshot đã freeze, không phụ thuộc trạng thái API tại thời điểm chạy | `uv run pytest tests/test_role2_cp3_baseline_integrity.py -v` |
| Chứng minh record bị `drop_latest_records` phục hồi đúng khi rebuild từ raw | `build_clean_dataframe(raw_records, RUN_DATE)`, `data/results/corruption_log.json` | `repaired_row["title"]`/`abs_url` khớp 100% với raw source của record đã bị xoá ở bước corruption | `uv run pytest tests/test_role2_cp6_repair_lineage_and_secrets.py -v` |

Một output cụ thể: `data/raw/crossref_records.json` (24 `PaperRecord`, mỗi record có `paper_id` là DOI đã `safe_slug`) là artifact mà cleaning owner, RAG owner và eval owner đều đọc trực tiếp làm điểm khởi đầu của pipeline. Mọi lineage check ở CP2/CP3/CP5/CP6 đều trace ngược về file này.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Phần của tôi giải quyết bài toán ingestion: lấy dữ liệu paper thật từ Crossref REST API một cách **tái lập được** (reproducible) và **có khả năng phục hồi** khi API trả lỗi tạm thời (rate limit 429, service unavailable 503), đồng thời lưu lại raw response làm nguồn sự thật (source of truth) để mọi bước sau (clean, corrupt, repair) có thể trace ngược về, thay vì phải gọi lại Crossref mỗi lần.

### Cách triển khai

- `_get_with_retry` chạy vòng lặp tối đa `max_retries` lần: nếu `requests.get` ném `RequestException` (lỗi kết nối) → sleep theo backoff mũ + jitter rồi thử lại; nếu response status `200` → trả JSON ngay; nếu status thuộc `(429, 503)` → đọc header `Retry-After` (nếu API cung cấp) để chờ đúng thời gian được yêu cầu, nếu không có thì dùng backoff mũ `base_delay * 2**attempt`; các status lỗi khác (404, 500...) gọi `response.raise_for_status()` ngay lập tức fail fast thay vì tốn hết retry cho một lỗi không phải rate-limit. Hết `max_retries` mà vẫn lỗi thì raise `RuntimeError`.
- `fetch_source_records` gọi `_get_with_retry`, ghi **nguyên payload thô** ra `raw_api_response` trước, sau đó mới gọi `parse_crossref_payload` để tạo `PaperRecord` và ghi ra `raw_records_json`. Thứ tự này đảm bảo raw response không bao giờ mất, kể cả khi parser sau này lỗi hoặc thay đổi rule lọc.
- `parse_crossref_payload` loại bỏ item thiếu `DOI`/`title`/`abstract`, strip tag HTML khỏi abstract, chuẩn hoá whitespace, sinh `paper_id = safe_slug(DOI)`, và lấy `categories` từ `subject` — nếu Crossref không trả `subject` thì fallback về field `type` (là field có thật từ nguồn, không tự bịa).
- `load_raw_records` đọc lại snapshot JSON và map về `PaperRecord`, **không gọi network**, dùng lại ở CP2/CP3/CP5/CP6 để đảm bảo baseline/corruption/repair đều dùng chung một raw snapshot, so sánh mới công bằng.

### Input, output và contract

| Thành phần | Mô tả |
| ---------- | ----- |
| Input | `Settings` (`source_query`, `source_filter`, `max_results`, `paths.raw_api_response`, `paths.raw_records_json`, `refresh_source`) |
| Output | `data/raw/crossref_response.json` (payload Crossref thô) và `data/raw/crossref_records.json` (`list[PaperRecord]`, mỗi record có `paper_id`, `title`, `summary`, `authors`, `categories`, `published`, `abs_url`, `pdf_url`) |
| Module phụ thuộc | `core.config.Settings`, `core.utils` (`write_json`, `read_json`, `safe_slug`, `normalize_whitespace`) |
| Module sử dụng output | `ingestion.cleaning.build_clean_dataframe` (CP1), `ingestion.corruption.corrupt_clean_dataframe` (CP5), `retrieval` index build (CP2) |
| Điều kiện lỗi cần xử lý | Crossref trả 429/503 (rate limit/tạm ngưng) → retry có backoff; lỗi kết nối mạng → retry; status lỗi khác (404/500) → fail ngay, không retry vô ích; item thiếu DOI/title/abstract → loại khỏi kết quả parse thay vì crash |

### Cách xác minh

```bash
uv run pytest tests/ -v
```

- **Kết quả mong đợi:** toàn bộ test pass; raw response được lưu trước khi parse; retry/backoff phản ứng đúng với 429 (có/không `Retry-After`), 503, lỗi kết nối, và fail nhanh với status không retryable; raw snapshot tái sử dụng được ở CP2/CP3/CP5/CP6 mà không gọi lại network.
- **Kết quả thực tế:** 37/37 test của vai trò 2 pass; chạy cùng toàn bộ `tests/` (bao gồm 10 test vai trò 3 liên quan cleaning/corruption) cho `37 passed in 13.08s`.
- **Artifact/log:** `data/raw/crossref_response.json`, `data/raw/crossref_records.json` (đã kiểm tra không chứa API key bằng `test_raw_response_artifact_has_no_obvious_leaked_api_key`; `.env` nằm trong `.gitignore`).

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** `paper_id` cần ổn định xuyên suốt raw → clean → index → eval → corrupted → repaired, nhưng Crossref không cung cấp sẵn một ID ngắn, dễ trace.
- **Các phương án đã cân nhắc:**
  1. Dùng vị trí/index trong danh sách response làm ID. Đơn giản nhưng đổi ngay khi refetch hoặc khi thứ tự trả về của API thay đổi, phá lineage giữa các lần chạy.
  2. Hash toàn bộ nội dung record (title + summary...). Ổn định hơn vị trí nhưng khó đọc, và đổi theo bất kỳ chỉnh sửa nhỏ nào ở text (ví dụ chuẩn hoá whitespace), gây sai lệch khi so sánh baseline/corrupted.
  3. `safe_slug(DOI)`: DOI là định danh học thuật chuẩn, gắn với chính bài báo, không đổi giữa các lần fetch.
- **Phương án đã chọn:** `safe_slug(DOI)`.
- **Lý do:** DOI không phụ thuộc vào thứ tự trả về hay nội dung có bị chuẩn hoá lại hay không, nên cho phép trace 1-1 giữa raw/clean/index/corrupted/repaired mà không cần lưu thêm bảng mapping riêng. Đúng yêu cầu "PaperRecord có stable paper_id" ở CP0.
- **Bằng chứng quyết định phù hợp:** `data/quality/baseline_quality.json` và `repaired_quality.json` báo `paper_id_unique` pass (0 null, 0 duplicate); trong khi `data/quality/corrupted_quality.json` báo `paper_id_unique` **fail** với đúng 3 duplicate, khớp chính xác với event `duplicate_rows` (3 bản sao) trong `data/results/corruption_log.json`. Việc check bắt đúng lỗi có chủ đích chứng minh cơ chế ID hoạt động đúng cả khi dữ liệu bị phá hoại có kiểm soát.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Khi đối chiếu `tests/` với phần việc CP0 của vai trò 2 trong file phân công ("Implement `parse_crossref_payload` và fetch/load theo contract Settings. Lưu raw API response trước parse; thêm retry/backoff cho 429/503"), không tìm thấy test nào gọi trực tiếp logic retry.
- **Lệnh hoặc bước tái hiện:**
  ```bash
  rg -n "fetch_source_records|retry|backoff|429|503" tests/
  ```
  chỉ trả về 2 dòng nhắc gián tiếp trong `test_role2_cp1_raw_lineage.py`/`test_role2_cp3_baseline_integrity.py` (kiểm tra raw artifact tồn tại), không có test nào exercise `_get_with_retry`.
- **Nguyên nhân gốc:** Các file `test_role2_cp1..cp6.py` được viết theo checklist "verification" của từng checkpoint *sau* CP0, còn CP0 là checkpoint duy nhất có việc "implement" thật (viết `parse_crossref_payload`/fetch/retry) nhưng không có bài test riêng — khi chạy baseline thật, Crossref luôn trả 200 ngay lần đầu nên nhánh retry/backoff không bao giờ được thực thi và gap không lộ ra.
- **Cách xử lý:** Viết `tests/test_role2_cp0_fetch_retry.py`, dùng một `FakeResponse` giả lập cùng `monkeypatch` trên `requests.get`, `time.sleep`, `random.uniform` để mô phỏng deterministic: 429 có/không header `Retry-After`, 503 liên tiếp, lỗi `ConnectionError`, status không retryable (404), và trường hợp `fetch_source_records` phải ghi raw response (bao gồm cả record mà `parse_crossref_payload` sẽ loại bỏ) trước khi ghi records đã parse.
- **Cách xác minh sau khi sửa:**
  ```bash
  uv run pytest tests/test_role2_cp0_fetch_retry.py -v   # 8 passed
  uv run pytest tests/ -v                                  # 37 passed in 13.08s
  ```
- **Điều học được:** Coverage phải map trực tiếp theo từng dòng "Trong mốc này" của file phân công cho từng checkpoint, không chỉ theo cảm tính; logic retry/backoff đặc biệt dễ bị bỏ sót vì nó không chạy trong happy path — phải mock lỗi mới ép được nhánh code đó chạy.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. **Crossref → vector index:** `fetch_source_records` gọi Crossref REST API (có retry/backoff cho 429/503), lưu raw response thô rồi parse thành `PaperRecord` với `paper_id = safe_slug(DOI)` vào `data/raw/`. Cleaning owner đọc raw records qua `load_raw_records`, chuẩn hoá thành `papers_clean.json/csv` (thêm `text_for_embedding`, `age_days`). RAG owner đọc clean data, build embedding (MiniLM) và Chroma collection `papers-baseline`, giữ `paper_id`/`title`/`abs_url`/`pdf_url`/`published` trong metadata để trace ngược về nguồn.
2. **Evaluation set & ground-truth doc IDs:** `build_test_set` sinh câu hỏi (summary/authors/date/categories) từ chính dữ liệu clean thật, và `ground_truth_doc_ids` lấy từ `paper_id` đã có trong index — không tự bịa ID. Evaluator so câu trả lời/agent với `ground_truth` (nội dung) và `ground_truth_doc_ids` (tài liệu đúng phải được retrieve) để tính `retrieval_hit_rate`, token F1, judge score.
3. **Quality checks khác freshness monitoring:** quality check (`row_count`, `paper_id_unique`, `title_not_null`, `summary_min_chars`, `text_for_embedding_not_empty`, `age_days_valid`) là ảnh chụp tính toàn vẹn cấu trúc/nội dung tại một thời điểm; freshness monitoring chỉ tập trung một khía cạnh — tuổi của `published` so với `freshness_threshold_days` (180 ngày) — trả lời câu hỏi "dữ liệu có còn mới không", một câu hỏi mà quality check schema không bắt được (dữ liệu có thể đúng schema tuyệt đối nhưng đã cũ).
4. **Vì sao dùng chung test set cho ba trạng thái:** để so sánh công bằng — nếu đổi câu hỏi/ground truth giữa các lần chạy baseline/corrupted/repaired thì chênh lệch metric có thể do test set khác nhau chứ không phải do chất lượng dữ liệu thay đổi, làm mất khả năng kết luận nhân quả giữa corruption và metric.
5. **Repair được xem là thành công khi:** `overall_pass` trong quality report quay lại `true`, `is_fresh` trong freshness report quay lại `true` (0 `stale_rows`), và các metric agent (`retrieval_hit_rate`, `mean_token_f1`, `mean_judge_score`) quay về đúng giá trị baseline — đối chiếu trực tiếp qua `data/results/signal_change.json`, không chỉ dựa vào việc script chạy xong không lỗi.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| -------------- | -------: | --------: | -------: | ---------------------- |
| `retrieval_hit_rate` | 1.0 | 0.75 | 1.0 | Giảm 0.25 vì `drop_latest_records` xoá đúng 3 record "mới nhất" khỏi corpus corrupted, khiến các `ground_truth_doc_ids` tương ứng không còn retrieve được; repaired phục hồi chính xác về 1.0 sau khi rebuild index từ raw. |
| `mean_token_f1` | 0.8219 | 0.7736 | 0.8219 | Giảm ~0.048 do `blank_summary` + `inject_summary_noise` làm nội dung trả lời lệch khỏi ground truth; repaired khớp lại baseline gần như tuyệt đối. |
| `judge_accuracy` | 0.75 | 0.75 | 0.75 | Không đổi — nằm trong `unchanged_signals` của `signal_change.json`. Với chỉ 12 mẫu, tỷ lệ nhị phân này kém nhạy hơn `mean_judge_score` (thang liên tục) khi phát hiện suy giảm nhẹ. |
| `mean_judge_score` | 4.25 | 4.083 | 4.25 | Giảm ~0.17 điểm rồi phục hồi đúng baseline — nhạy hơn `judge_accuracy` với cùng mức corruption. |
| Quality checks (`overall_pass`) | pass | **fail** (`paper_id_unique` dup=3, `summary_min_chars` fail=3, `freshness_threshold` fail=3) | pass | Corrupted vi phạm đúng 3/6 check, khớp 1-1 với 3 loại event trong corruption log ảnh hưởng trực tiếp tới các trường đó. |
| Freshness status (`is_fresh`) | true (0/24 stale) | **false** (3/24 stale, oldest = 2016-05-22) | true (0/24 stale) | `stale_published_date` (trừ 10 năm) đẩy 3 record vượt ngưỡng 180 ngày; repair rebuild từ raw đưa ngày về đúng giá trị gốc. |

### Kết luận từ số liệu

1. `drop_latest_records` (xoá 3 record mới nhất) → `freshness_threshold` fail trong corrupted quality report (`stale_rows=3`) → `retrieval_hit_rate` giảm từ 1.0 xuống 0.75 vì 3 `ground_truth_doc_ids` không còn nằm trong corpus corrupted.
2. Repair (rebuild clean + index từ đúng raw snapshot đã dùng ở baseline, không sửa tay dữ liệu corrupted) → quality `overall_pass` quay lại `true`, freshness `is_fresh` quay lại `true` → `retrieval_hit_rate` và `mean_token_f1` quay đúng về giá trị baseline (1.0 / 0.8219), chứng minh repair phục hồi hoàn toàn ở các signal này.

Corruption ảnh hưởng rõ nhất là **`drop_latest_records`** và **`stale_published_date`**, vì đây là hai event duy nhất trong `corruption_log.json` có mặt trong `observed_failing_checks` của `signal_change.json` (`freshness_threshold`) và đồng thời tác động trực tiếp tới `ground_truth_doc_ids` nằm trong test set cố định — quan sát được cả trên quality report lẫn `retrieval_hit_rate`. Ngược lại, `truncate_title` có log corruption nhưng `observed_failing_checks: []` — không kích hoạt check nào vì `title_not_null` chỉ kiểm tra rỗng/null, không kiểm tra độ dài, nên corruption này "vô hình" với bộ quality check hiện tại.

Kết quả khác kỳ vọng ban đầu: tôi dự đoán `judge_accuracy` sẽ giảm cùng chiều với `retrieval_hit_rate` vì agent thiếu tài liệu nguồn sẽ trả lời sai nhiều hơn. Nhưng `signal_change.json` liệt kê `judge_accuracy` trong `unchanged_signals` (giữ nguyên 0.75 ở cả ba trạng thái). Tôi đã kiểm tra bằng cách so `baseline_answers.json`/`corrupted_answers.json`: nguyên nhân là `judge_accuracy` được tính trên chỉ 12 mẫu nên 1–2 câu đổi kết quả không đủ đổi tỷ lệ nhị phân, trong khi `mean_judge_score` (thang điểm liên tục) vẫn phản ánh được mức suy giảm nhẹ (4.25 → 4.083) — cho thấy metric liên tục nhạy hơn metric nhị phân khi tập test nhỏ.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Về data pipeline:** retry/backoff cho external API không phải chi tiết phụ — đó là điều kiện để raw ingestion tái lập được, vì rate-limit của Crossref là tình huống thật có thể xảy ra bất kỳ lúc nào khi chạy lại pipeline.
2. **Về data quality/observability:** quality check (schema/duplicate/nội dung) và freshness monitoring bổ sung cho nhau chứ không thay thế nhau — `truncate_title` cho thấy có những kiểu corruption lọt qua toàn bộ quality check hiện có vì không có rule kiểm tra độ dài tối thiểu cho title.
3. **Về ảnh hưởng của data lên RAG agent:** corruption ở tầng data (xoá record, làm cũ ngày tháng) tác động trực tiếp và đo được lên `retrieval_hit_rate` — rõ ràng hơn nhiều so với answer-level judge accuracy khi tập test nhỏ, nên khi debug nên nhìn signal ở tầng retrieval trước.

### Nếu có thêm thời gian

Tôi sẽ thêm một metric riêng đo tỷ lệ `ground_truth_doc_ids` bị mất khỏi index theo từng loại corruption (thay vì chỉ nhìn `retrieval_hit_rate` tổng hợp), bằng cách join `corruption_log.json["events"][*].record_ids` với `ground_truth_doc_ids` của từng câu hỏi trong test set. Điều này giúp định vị chính xác corruption nào gây miss thay vì phải suy luận gián tiếp qua `signal_change.json`, và sẽ bắt được ngay trường hợp như `truncate_title` hiện đang "vô hình" với bộ quality check.

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Trần Hoàng Long
**Ngày xác nhận:** 2026-08-06