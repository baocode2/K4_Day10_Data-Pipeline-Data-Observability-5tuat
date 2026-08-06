# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Trần Đức Bảo             |
| MSSV               | 2A202601472                     |
| Khóa/Lớp         | K4              |
| Tên nhóm         | Nhóm 5 (K4_Day10_Data-Pipeline-Data-Observability)     |
| Vai trò chính    | Vai trò 1 – Điều phối pipeline (Pipeline integrator)                 |
| Repository         | https://github.com/baocode2/K4_Day10_Data-Pipeline-Data-Observability-5tuat |
| Ngày hoàn thành | 2026-08-06               |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái                                 |
| ------------------ | --------------------- | ---------------- | ----------------- | -------------------------------------------- |
| Cấu hình và path dùng chung | `src/core/config.py` (`Paths`, `Settings`, `load_settings`, `require_llm_credentials`), `src/core/utils.py` | Biến môi trường `.env`, thư mục project | Object `Settings`/`Paths` dùng xuyên suốt mọi module | Hoàn thành |
| Baseline orchestration (Pha 1) | `src/pipelines/phase1.py`, chạy qua `script/run_phase1.py` | Raw Crossref records | `data/clean/`, `data/embeddings/`, `data/eval/`, `data/results/baseline_metrics.json`, `data/quality/`, `data/reports/phase1_report.md` | Hoàn thành, đã chạy thật và xác minh artifact |
| Corruption/repair orchestration (Pha 2) | `src/pipelines/corruption_flow.py`, chạy qua `script/run_corruption_flow.py` | Baseline clean dataset + raw records | `data/clean/*_corrupted.*`, `*_repaired.*`, `data/embeddings/*_corrupted.json`/`*_repaired.json`, `data/results/corrupted_metrics.json`/`repaired_metrics.json`, `data/quality/corrupted_*`/`repaired_*`, `data/reports/corruption_report.md` | Hoàn thành, tự implement từ `NotImplementedError` và chạy thành công 11/11 bước |

Việc tự thực hiện chính trong phiên làm việc này: implement toàn bộ `src/pipelines/corruption_flow.py` (trước đó là stub `raise NotImplementedError`), debug và chạy thành công đến khi ra đủ artifact so sánh baseline/corrupted/repaired, sau đó commit và push lên `origin/main`. Phần `phase1.py`/`config.py` đã có sẵn từ trước, tôi xác minh lại (chạy thật, đối chiếu artifact) chứ không viết mới trong phiên này.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                         | Thành viên/module được hỗ trợ | Kết quả                    |
| ------------------------------------ | ------------------------------------ | ---------------------------- |
| Sửa `validate_index_dataframe()` trong `src/retrieval/index.py` (module của Vai trò 4 – RAG owner) | Vai trò 4 (RAG & agent owner) | Bỏ yêu cầu cứng `summary` không-rỗng và duplicate `paper_id` khi build index, để corrupted dataset (cố ý có blank summary/duplicate) build index được thay vì crash toàn bộ flow. Quality checks vẫn phát hiện đúng hai lỗi này riêng. |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh         |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Implement corruption/repair orchestration | `src/pipelines/corruption_flow.py` | Corrupt → rebuild index → evaluate → quality/freshness → repair từ raw → evaluate lại → comparison report | `python script/run_corruption_flow.py` chạy 11/11 bước không lỗi |
| Sửa contract tích hợp giữa corruption và RAG index | `src/retrieval/index.py` | Corrupted dataset (blank summary, duplicate paper_id) build index được | Log chạy: `3/11 Building corrupted embedding index... collection=papers-corrupted documents=24` không còn crash |
| Thêm khả năng chịu lỗi rate-limit khi gọi embedding API | `_with_rate_limit_retry()` trong `corruption_flow.py` | Pipeline tự retry khi Gemini free-tier trả `429 RESOURCE_EXHAUSTED` thay vì crash | Chạy lại pipeline, thấy log `rate limited by embedding API, retrying...` rồi tự tiếp tục |
| Xác minh và ghi lại kết quả so sánh 3 trạng thái | `data/reports/corruption_report.md`, `data/results/*_metrics.json` | Bảng so sánh baseline/corrupted/repaired với số liệu thật | Đọc trực tiếp `data/reports/corruption_report.md` |
| Commit và push toàn bộ artifact + code lên remote | Git | Commit `17d9510` lên `origin/main` | `git log --oneline`, `git push origin main` thành công (`ade409f..17d9510`) |

Output cụ thể: file `data/reports/corruption_report.md` — bảng metric so sánh baseline/corrupted/repaired do `corruption_flow.py` (tôi implement) sinh ra, cho thấy `retrieval_hit_rate` giảm từ 1.0 xuống 0.75 khi corrupt rồi phục hồi lại 1.0 sau repair.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Trước khi tôi làm, `src/pipelines/corruption_flow.py` chỉ là một hàm `main()` rỗng với `raise NotImplementedError`. Toàn bộ Pha 2 của bài lab (corrupt dữ liệu có chủ đích, đo impact lên agent, repair từ raw, so sánh 3 trạng thái) chưa chạy được, dù các module cấp thấp hơn (`ingestion/corruption.py`, `observability/quality.py`, `observability/reporting.py`) đã có sẵn logic riêng lẻ. Việc của tôi (đúng vai trò điều phối pipeline) là ghép các module đó thành một luồng chạy được end-to-end, đúng thứ tự, đúng path/collection riêng cho từng trạng thái, không ghi đè baseline.

### Cách triển khai

`main()` trong `corruption_flow.py` chạy tuần tự 11 bước:

1. Kiểm tra baseline đã tồn tại (`clean_json`, `baseline_metrics`) trước khi làm gì khác — nếu chưa có thì raise lỗi rõ ràng thay vì lỗi mơ hồ ở bước sau.
2. Load **clean dataframe của baseline từ đĩa** (không build lại từ raw với timestamp mới) — quyết định quan trọng, giải thích ở mục 5.
3. Gọi `corrupt_clean_dataframe()` có sẵn để tạo corrupted dataset + log, lưu ra path riêng (`papers_clean_corrupted.*`), không đụng file baseline.
4. Build lại embedding index cho corrupted vào collection riêng (`papers-corrupted`).
5. Evaluate corrupted trên **đúng test set cũ** (không tạo test set mới) để so sánh công bằng.
6. Chạy quality checks + freshness report riêng cho corrupted.
7. Repair: **load lại raw records từ file đã lưu** (`crossref_records.json`), không gọi lại API, rồi build lại clean dataframe từ raw gốc — đảm bảo repair là rebuild thật từ nguồn tin cậy, không phải vá thủ công dataset corrupted.
8-9. Build index + evaluate cho repaired, path/collection riêng (`papers-repaired`).
10. Quality/freshness cho repaired.
11. Đọc `baseline_metrics.json` có sẵn (không evaluate lại baseline, tránh rủi ro ghi đè) rồi gọi `generate_corruption_report()` để in bảng so sánh 3 trạng thái.

### Input, output và contract

| Thành phần                   | Mô tả                                     |
| ------------------------------ | ------------------------------------------- |
| Input                          | `data/clean/papers_clean.json` (baseline), `data/results/baseline_metrics.json`, `data/raw/crossref_records.json`, `data/eval/test_set.json` |
| Output                         | `papers_clean_corrupted.*`, `papers_clean_repaired.*`, `papers_embeddings_corrupted.json`, `papers_embeddings_repaired.json`, `corrupted_metrics.json`, `repaired_metrics.json`, `corruption_log.json`, `corruption_report.md` |
| Module phụ thuộc             | `ingestion.corruption`, `ingestion.cleaning`, `ingestion.crossref`, `retrieval.index`, `evaluation.metrics`, `observability.quality`, `observability.reporting` |
| Module sử dụng output        | `report/group_report.md` (mục 9-12) trích số liệu từ đây để viết kết luận nhân quả |
| Điều kiện lỗi cần xử lý | Thiếu baseline artifact → raise rõ ràng; `save_clean_dataframe()` yêu cầu `DataFrame.attrs['cleaning_report']`; embedding API trả 429 khi vượt quota free-tier |

### Cách xác minh

```bash
$env:PYTHONPATH = "src"
python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** chạy hết 11/11 bước, in ra `retrieval_hit_rate`/`mean_token_f1` cho cả corrupted và repaired, kết thúc bằng dòng "Corruption/repair flow complete."
- **Kết quả thực tế:** chạy thành công, log cuối cùng: `11/11 Writing comparison report... report: .../data/reports/corruption_report.md` rồi `Corruption/repair flow complete.`
- **Artifact/log:** `data/reports/corruption_report.md`, `data/results/corrupted_metrics.json`, `data/results/repaired_metrics.json` (không chứa secret — đã kiểm tra bằng regex tìm API key trước khi commit).

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Khi build corrupted dataset để evaluate, cần chọn: (a) build lại clean dataframe từ raw records với `run_date = now()` tại thời điểm chạy corruption flow, hay (b) load đúng clean dataframe baseline đã lưu trên đĩa rồi mới corrupt nó.
- **Các phương án đã cân nhắc:**
  1. Rebuild từ raw với `run_date` mới — đơn giản, tái dùng `build_clean_dataframe()` sẵn có.
  2. Load lại đúng file `papers_clean.json` mà baseline đã lưu, giữ nguyên `age_days`/`text_for_embedding` như lúc evaluate baseline.
- **Phương án đã chọn:** Phương án 2.
- **Lý do:** Nếu dùng phương án 1, `age_days` của corrupted dataset sẽ được tính lại theo thời điểm chạy corruption flow (có thể cách baseline vài giờ/vài ngày), làm freshness/quality signal bị lệch vì thời gian trôi qua chứ không phải vì corruption — gây nhiễu khi so sánh nhân quả. Phương án 2 đảm bảo baseline và corrupted xuất phát từ **cùng một điểm dữ liệu**, nên mọi khác biệt đo được sau đó chỉ đến từ chính hành động corrupt.
- **Bằng chứng quyết định phù hợp:** `corrupted_freshness_report.json` báo `stale_rows = 3` đúng bằng số record bị `stale_published_date` (lùi 10 năm) — không có record nào khác bị tính stale "oan" do trôi thời gian giữa hai lần chạy.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:**
  ```
  ValueError: Clean dataframe has invalid RAG fields: summary (3 blank).
  ```
  (crash tại bước "3/11 Building corrupted embedding index...")
- **Lệnh hoặc bước tái hiện:** `python script/run_corruption_flow.py` ngay sau khi `corrupt_clean_dataframe()` tạo 3 record có `summary = ""` theo kịch bản `blank_summary`.
- **Nguyên nhân gốc:** Contract mismatch giữa hai module do hai người phụ trách khác nhau. `src/ingestion/corruption.py` (Vai trò 3) cố ý làm rỗng `summary` của 3 record để test quality dimension "Completeness". `src/retrieval/index.py::validate_index_dataframe()` (Vai trò 4) lại coi `summary` là field bắt buộc không được rỗng để build RAG index — hợp lý cho dữ liệu sạch, nhưng vô tình chặn cứng luôn cả kịch bản corruption có chủ đích, khiến không thể đánh giá được impact lên retrieval.
- **Cách xử lý:** Không sửa `ingestion/corruption.py` (kịch bản corruption đúng ý đồ) và không vá tay JSON kết quả. Thay vào đó sửa `validate_index_dataframe()`: bỏ `summary` khỏi danh sách field bắt buộc không-rỗng, chỉ giữ `paper_id`, `title`, `text_for_embedding` (đây mới là nội dung thực sự được đưa vào embedding — `text_for_embedding` vẫn không rỗng dù `summary` rỗng vì còn có Title/Authors). `summary` rỗng vẫn bị `observability/quality.py::_check_summary` bắt fail riêng, nên tín hiệu chất lượng vẫn đúng.
- **Cách xác minh sau khi sửa:** Chạy lại `python script/run_corruption_flow.py`, bước 3/11 build thành công (`collection=papers-corrupted documents=24`), bước 5/11 quality check vẫn báo `overall_pass=False` — đúng, vì check `summary_min_chars` vẫn fail như kỳ vọng.
- **Điều học được:** Khi nhiều người viết contract riêng cho từng module, một validation "an toàn" ở module downstream (RAG index) có thể vô tình vô hiệu hóa mục tiêu của module upstream (corruption testing). Vai trò điều phối cần chạy thử end-to-end sớm để bắt được loại xung đột này, thay vì để mỗi module tự pass unit test riêng rồi mới phát hiện lúc tích hợp.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. **Crossref → vector index:** `crossref.py` gọi Crossref REST API, lưu raw response + raw records đã parse (`paper_id` = slug ổn định từ DOI) vào `data/raw/`. `cleaning.py` chuẩn hóa raw records thành `clean_df` (loại record thiếu field bắt buộc, dedupe theo `paper_id`, tính `age_days`, ghép `text_for_embedding`). `retrieval/index.py` nhận `clean_df`, validate contract, gọi Gemini embeddings rồi nạp vào một collection ChromaDB riêng (baseline/corrupted/repaired dùng ba collection khác nhau).
2. **Evaluation set và ground-truth doc IDs:** `evaluation/testset.py` sinh câu hỏi từ chính `clean_df` (4 loại: summary/authors/date/categories), mỗi câu hỏi gắn `ground_truth_doc_ids` = `paper_id` của record nguồn. Khi evaluate, hệ thống so `retrieved_doc_ids` (từ ChromaDB search) với `ground_truth_doc_ids` để tính `retrieval_hit_rate`, và so answer của agent với `ground_truth` để tính `token_f1`/judge score.
3. **Quality checks vs freshness monitoring:** Quality checks (`run_data_quality_checks`) đo tính đúng đắn cấu trúc dữ liệu tại một thời điểm (row count, `paper_id` unique, title/summary không rỗng, `age_days` hợp lệ) — trả lời "dữ liệu có sạch không". Freshness (`build_freshness_report`) chỉ nhìn vào `published`/`age_days` để trả lời "dữ liệu có còn mới so với ngưỡng (180 ngày) không" — hai khái niệm khác nhau: một record có thể "sạch" (đủ field, đúng schema) nhưng vẫn "stale" (quá cũ).
4. **Vì sao dùng cùng test set cho cả 3 trạng thái:** Nếu đổi test set giữa các lần đánh giá, bất kỳ thay đổi metric nào cũng không thể quy chắc chắn cho corruption hay repair — có thể chỉ vì câu hỏi khác nhau độ khó khác nhau. Giữ nguyên `test_set.json` là điều kiện bắt buộc để phép so sánh baseline/corrupted/repaired có ý nghĩa nhân quả.
5. **Repair được coi là thành công dựa trên:** `repaired_metrics.json` phải quay lại (xấp xỉ) đúng giá trị `baseline_metrics.json`, và `repaired_quality.json`/`repaired_freshness_report.json` phải PASS/`is_fresh=true` — tức là cả metric agent lẫn tín hiệu chất lượng dữ liệu đều phục hồi, không chỉ một trong hai.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` |   1.0000 |    0.7500 |   1.0000 | Giảm 25 điểm % vì `drop_latest_records` xóa đúng record đang là `ground_truth_doc_ids` của một câu hỏi trong test set; repair phục hồi 100%. |
| `mean_token_f1`      |   0.8219 |    0.7736 |   0.8219 | Giảm nhẹ do blank/noisy summary làm answer lệch nội dung; phục hồi hoàn toàn sau repair. |
| `judge_accuracy`     |   0.7500 |    0.7500 |   0.7500 | Không đổi — corruption trong lô này chưa đủ mạnh để lật phán quyết đúng/sai của LLM judge trên các câu hỏi hiện có. |
| `mean_judge_score`   |   4.2500 |    4.0833 |   4.2500 | Giảm nhẹ, phục hồi hoàn toàn về đúng baseline sau repair. |
| Quality checks         |     PASS |      FAIL |     PASS | Fail chủ yếu do `summary_min_chars` (blank summary) và `paper_id_unique` (duplicate rows). |
| Freshness status       |     PASS (0 stale) |      FAIL (3 stale) |     PASS (0 stale) | 3 record bị `stale_published_date` lùi 10 năm, vượt ngưỡng freshness 180 ngày. |

### Kết luận từ số liệu

1. `drop_latest_records` + `stale_published_date` (corruption) → `paper_id_unique`/`freshness_threshold` fail trong `data/quality/corrupted_quality.json` → `retrieval_hit_rate` giảm từ 1.0 xuống 0.75 trong `data/results/corrupted_metrics.json` — vì record bị xóa nằm trong `ground_truth_doc_ids` của test set, agent mất tài liệu nguồn để trả lời đúng.
2. Repair (rebuild từ `data/raw/crossref_records.json`) → quality/freshness phục hồi hoàn toàn PASS/Fresh trong `data/quality/repaired_quality.json` và `repaired_freshness_report.json` → `retrieval_hit_rate`/`mean_token_f1` quay lại đúng giá trị baseline trong `data/results/repaired_metrics.json` — vì repaired dataset được build lại từ raw gốc, không kế thừa lỗi từ corrupted.

Corruption ảnh hưởng rõ nhất là `drop_latest_records`, vì đây là loại duy nhất **xóa hẳn** một record đang được test set tham chiếu trực tiếp, trong khi các corruption khác (blank/noise summary, truncate title, stale date, duplicate) chỉ làm suy giảm chất lượng nội dung/metadata chứ không xóa hẳn tài liệu nguồn — nên ảnh hưởng lên `retrieval_hit_rate` yếu hơn nhiều.

Kết quả khác kỳ vọng: `judge_accuracy` giữ nguyên 0.75 ở cả 3 trạng thái dù `retrieval_hit_rate` và `mean_token_f1` đã thay đổi rõ. Giả thuyết: với top-k=4 và 12 câu hỏi, một số câu vẫn được LLM trả lời "đủ đúng" từ context còn sót lại (hoặc từ kiến thức nền của model) dù retrieval bị suy giảm, nên ngưỡng chấm "correct" của judge (score ≥ 3) chưa đủ nhạy để bắt được khác biệt này. Đã kiểm tra bằng cách đọc trực tiếp `corrupted_answers.json`/`repaired_answers.json`, không chỉnh sửa số liệu để "ép" kết quả trông đẹp hơn.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Một pipeline được ghép từ nhiều module "đúng riêng lẻ" vẫn có thể gãy khi tích hợp — validation ở `retrieval/index.py` đúng cho baseline nhưng sai cho corrupted; chỉ chạy thử end-to-end mới lộ ra.
2. Freshness và data quality là hai tín hiệu độc lập, đo hai thứ khác nhau (đúng cấu trúc vs còn mới) — cả hai cần được kiểm tra riêng để chẩn đoán đúng nguyên nhân khi agent trả lời sai.
3. Không phải mọi metric đều nhạy với data corruption như nhau (`judge_accuracy` không đổi trong khi `retrieval_hit_rate` đổi rõ) — kết luận "corruption có ảnh hưởng" phải dựa trên từng metric cụ thể có bằng chứng, không khái quát hóa cho tất cả.

### Nếu có thêm thời gian

Sẽ mở rộng `_with_rate_limit_retry()` (hiện chỉ có trong `corruption_flow.py`) thành helper dùng chung cho cả `phase1.py`, vì baseline pipeline gọi cùng Gemini embeddings API và có thể gặp đúng lỗi 429 khi chạy nhiều lần liên tiếp trong lúc phát triển — đo cải thiện bằng cách chạy `run_phase1.py` liên tiếp 2 lần trong 1 phút và xác nhận không còn crash vì rate limit.

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Trần Đức Bảo
**Ngày xác nhận:** 2026-08-06
