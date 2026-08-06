# BÁO CÁO CÁ NHÂN — DATA PIPELINE & DATA OBSERVABILITY

## Thông tin sinh viên

- **Họ và tên:** Phạm Công Đạt
- **MSSV:** 2A202601406
- **Khóa/Lớp:** K4
- **Nhóm:** K4 Day 10
- **Vai trò:** Vai trò 3 — Cleaning & Corruption Owner
- **Repository:** https://github.com/baocode2/K4_Day10_Data-Pipeline-Data-Observability-5tuat
- **Ngày hoàn thành:** 06/08/2026

---

## 1. Tóm tắt vai trò và phạm vi phụ trách

Trong bài lab, tôi phụ trách chuẩn hóa dữ liệu bài báo từ raw schema sang clean schema, xây dựng các kịch bản làm hỏng dữ liệu có kiểm soát và xác minh khả năng sửa chữa dữ liệu. Phần việc tập trung vào ba mục tiêu chính:

1. Xây dựng dữ liệu sạch đủ điều kiện phục vụ embedding và retrieval.
2. Tạo bộ dữ liệu corrupted có thể tái lập, có log kiểm toán và không làm thay đổi baseline.
3. Xác minh repair khôi phục đúng dữ liệu baseline và giúp chất lượng pipeline trở lại trạng thái ban đầu.

Các file chính tôi phụ trách hoặc trực tiếp kiểm thử gồm:

- `src/ingestion/cleaning.py`
- `src/ingestion/corruption.py`
- `src/ingestion/cp2_validation.py`
- `src/ingestion/cp5_validation.py`
- `src/ingestion/cp6_validation.py`
- `script/validate_role3_cp2.py`
- `script/run_role3_cp5.py`
- `script/validate_role3_cp5.py`
- `script/validate_role3_cp6.py`
- `tests/test_role3_cleaning_corruption.py`

Đầu ra chính của phần việc:

- `data/raw/papers_raw.json`
- `data/clean/papers_clean.csv`
- `data/clean/papers_clean.json`
- `data/clean/cleaning_report.json`
- `data/corrupted/papers_corrupted.csv`
- `data/corrupted/papers_corrupted.json`
- `data/corrupted/corruption_log.json`
- `data/repaired/papers_repaired.csv`
- `data/repaired/papers_repaired.json`

---

## 2. Công việc đã thực hiện theo checkpoint

### CP0 — Chốt clean schema và quy tắc làm sạch

Tôi đọc target schema và thống nhất clean contract gồm 16 trường:

`paper_id`, `title`, `summary`, `authors`, `authors_joined`, `categories`, `categories_joined`, `primary_category`, `published`, `updated`, `age_days`, `summary_chars`, `text_for_embedding`, `abs_url`, `pdf_url`, `comment`.

Các quy tắc bắt buộc được xác định như sau:

- Loại bản ghi không có `paper_id` hoặc không có tiêu đề.
- Loại bản ghi có tóm tắt sau làm sạch ngắn hơn 100 ký tự.
- Loại thẻ XML/HTML và giải mã HTML entity trong `title` và `summary`.
- Chuẩn hóa tác giả và category từ cấu trúc lồng nhau về list chuỗi.
- Tạo `authors_joined` và `categories_joined` bằng cách nối các phần tử bằng dấu phẩy.
- Chuẩn hóa `published` và `updated` về `YYYY-MM-DD`.
- Tính `age_days` từ ngày xuất bản tới thời điểm chạy pipeline.
- Loại trùng `paper_id` không phân biệt hoa thường.
- Tạo `text_for_embedding` theo định dạng cố định:

```text
Title: [title] | Authors: [authors_joined] | Summary: [summary]
```

### CP1 — Triển khai quy trình raw → clean

Tôi hoàn thiện logic trong `src/ingestion/cleaning.py` để:

- Nhận dữ liệu raw dưới dạng record/dictionary.
- Làm sạch từng trường text.
- Chuẩn hóa authors/categories.
- Kiểm tra điều kiện loại bỏ bản ghi rác.
- Tính các trường dẫn xuất `age_days`, `summary_chars` và `text_for_embedding`.
- Loại trùng theo `paper_id`.
- Kiểm tra DataFrame cuối cùng đúng clean contract.
- Lưu đồng thời CSV, JSON và báo cáo làm sạch.

Kết quả trên snapshot hiện tại:

- Raw records: **24**
- Clean records: **24**
- Rejected records: **0**
- Duplicate records bị loại: **0**
- Clean schema: **đúng 16 cột**

### CP2 — Xác thực clean contract và lineage

Tôi xây dựng validator để kiểm tra dữ liệu clean có nguồn gốc hợp lệ từ raw và không vi phạm contract. Các nhóm kiểm tra gồm:

- File raw/clean tồn tại và đọc được.
- Số lượng, schema và kiểu dữ liệu hợp lệ.
- `paper_id` không rỗng và duy nhất không phân biệt hoa thường.
- `title` không rỗng.
- `summary` có ít nhất 100 ký tự.
- Không còn XML/HTML trong các trường text.
- `authors_joined`, `categories_joined` khớp với các list tương ứng.
- `summary_chars` khớp độ dài summary.
- `text_for_embedding` khớp chính xác format đã chốt.
- `published`, `updated` và `age_days` hợp lệ.
- Mỗi clean record truy ngược được về raw record theo `paper_id`.

Validator CP2 chạy thành công trên dữ liệu của project.

### CP3 — Chuẩn bị corruption có kiểm soát

Tôi thiết kế corruption theo hướng deterministic để nhiều lần chạy với cùng cấu hình cho cùng kết quả. Sáu kịch bản được sử dụng, mỗi kịch bản tác động lên 3 bản ghi:

1. `drop_latest`: loại 3 bài mới nhất.
2. `blank_summary`: làm rỗng summary của 3 bài.
3. `inject_noise`: chèn nhiễu vào nội dung.
4. `truncate_title`: cắt ngắn tiêu đề.
5. `stale_published`: lùi ngày xuất bản 10 năm.
6. `duplicate_records`: nhân bản 3 bản ghi.

Mỗi corruption được ghi vào `corruption_log.json` với loại lỗi, ID bị ảnh hưởng, tham số và thông tin trước/sau. Baseline được đọc như nguồn đầu vào và không bị ghi đè.

### CP4 — Tích hợp corruption với pipeline

Corruption flow tạo một nhánh dữ liệu riêng trong `data/corrupted/`, không sửa `data/clean/`. Sau khi thay đổi các trường nguồn, pipeline tính lại những trường dẫn xuất như `summary_chars`, `age_days` và `text_for_embedding` để artifact vẫn có cấu trúc nhất quán nhưng chứa lỗi chất lượng có chủ đích.

Một vấn đề tích hợp được phát hiện là corruption cố ý tạo duplicate trong khi index contract không cho phép `paper_id` trùng. Giải pháp là giữ nguyên duplicate trong artifact corrupted để quality gate có thể phát hiện, nhưng tạo một view đã deduplicate trước khi đưa sang index. Nhờ đó:

- Bằng chứng dữ liệu xấu không bị che giấu.
- Quality gate vẫn đánh dấu lỗi uniqueness.
- RAG pipeline vẫn có thể chạy để đo tác động của corruption.

### CP5 — Chạy và xác thực corrupted flow

CP5 được xác minh bằng validator và test tự động. Kết quả chính:

- Baseline: 24 dòng, 24 `paper_id` duy nhất.
- Corrupted: 24 dòng do drop 3 rồi thêm lại 3 duplicate.
- Corrupted chỉ còn 21 `paper_id` duy nhất.
- Quality status chuyển từ **PASS** sang **FAIL**.
- Các check bị lỗi gồm `paper_id_unique`, `summary_min_chars` và `freshness_threshold`.
- Số bản ghi stale tăng từ 0 lên 3.
- Corruption log ghi đủ 6 kịch bản và danh sách record bị tác động.
- Baseline artifact không bị thay đổi sau khi chạy corruption.

### CP6 — Repair và kiểm chứng phục hồi

Quy trình repair tái tạo dữ liệu từ raw snapshot bằng chính clean contract, thay vì chỉnh sửa trực tiếp file corrupted. Cách làm này giúp tránh sót lỗi hoặc vô tình giữ lại dữ liệu đã bị làm hỏng.

Validator CP6 kiểm tra:

- Repaired CSV/JSON tồn tại và đúng schema.
- Repaired DataFrame bằng baseline DataFrame sau khi chuẩn hóa kiểu dữ liệu và thứ tự.
- Không còn duplicate, summary rỗng/ngắn, title bị cắt hoặc published bị làm cũ.
- `summary_chars`, `age_days` và `text_for_embedding` được tái tạo đúng.
- Quality/freshness trở lại baseline.
- Retrieval và answer metrics phục hồi về giá trị baseline.

Kết quả kiểm thử cuối cùng: **38 tests passed**.

---

## 3. Quyết định kỹ thuật quan trọng

### 3.1. Giữ artifact corrupted nguyên trạng, chỉ deduplicate view dùng để index

Đây là quyết định kỹ thuật quan trọng nhất trong phần tích hợp. Nếu xóa duplicate ngay trong `papers_corrupted.csv`, quality gate sẽ không còn bằng chứng về corruption. Nếu đưa nguyên dữ liệu duplicate sang index, pipeline dừng với lỗi:

```text
ValueError: Clean dataframe has 6 duplicate paper_id values (case-insensitive).
```

Vì vậy, artifact corrupted được giữ nguyên để quan sát chất lượng, còn dữ liệu đầu vào index được deduplicate riêng. Cách tách hai mục đích này bảo đảm cả observability lẫn khả năng đánh giá RAG.

### 3.2. Repair từ raw thay vì vá dữ liệu corrupted

Tôi chọn tái chạy quy trình clean từ raw snapshot. Repair theo cách này có tính xác định, dễ kiểm chứng và loại bỏ toàn bộ sáu kiểu corruption cùng lúc. Điều kiện thành công không chỉ là “file chạy được” mà là repaired dataset phải bằng baseline.

### 3.3. Trường dẫn xuất luôn được tính từ trường nguồn

Các trường `summary_chars`, `age_days` và `text_for_embedding` không được coi là dữ liệu nguồn. Chúng luôn được tính lại sau cleaning, corruption hoặc repair. Điều này tránh tình trạng trường nguồn đã đổi nhưng metadata/embedding text còn giữ giá trị cũ.

### 3.4. So sánh baseline, corrupted và repaired trên cùng test set

Để đánh giá công bằng, cả ba lần chạy sử dụng cùng tập câu hỏi và cùng ground truth. Nhờ đó, chênh lệch metric phản ánh tác động của chất lượng dữ liệu thay vì khác biệt đầu vào đánh giá.

---

## 4. Kết quả chất lượng dữ liệu

| Giai đoạn | Số dòng | ID duy nhất | Quality | Freshness |
|---|---:|---:|---|---|
| Baseline | 24 | 24 | PASS | Fresh — 0 stale |
| Corrupted | 24 | 21 | FAIL | Stale — 3 stale |
| Repaired | 24 | 24 | PASS | Fresh — 0 stale |

Diễn biến trên chứng minh corruption đủ mạnh để quality gate phát hiện và repair phục hồi đầy đủ các tín hiệu chất lượng.

---

## 5. Tác động lên retrieval và answer quality

| Metric | Baseline | Corrupted | Repaired |
|---|---:|---:|---:|
| Retrieval hit rate | 1.0000 | 0.7500 | 1.0000 |
| Mean token F1 | 0.8219 | 0.7736 | 0.8219 |
| Judge accuracy | 0.7500 | 0.7500 | 0.7500 |
| Mean judge score | 4.2500 | 4.0833 | 4.2500 |

Chênh lệch corrupted so với baseline:

- Retrieval hit rate giảm **0.25**.
- Mean token F1 giảm khoảng **0.0484**.
- Mean judge score giảm khoảng **0.1667**.
- Judge accuracy không đổi, nhưng các metric còn lại cho thấy chất lượng retrieval và câu trả lời đã suy giảm.

Sau repair, tất cả các metric trở về đúng mức baseline. Điều này cho thấy dữ liệu xấu ảnh hưởng trực tiếp tới RAG, và quy trình repair đã khôi phục được hiệu năng ban đầu.

---

## 6. Lỗi gặp phải và cách xử lý

### Lỗi xung đột giữa corruption contract và index contract

**Hiện tượng:** Pipeline corrupted dừng trước bước index vì phát hiện `paper_id` trùng không phân biệt hoa thường.

**Nguyên nhân:** Duplicate là corruption có chủ đích để quality gate phát hiện, trong khi index yêu cầu mỗi document ID là duy nhất.

**Cách xử lý:**

1. Không sửa hoặc xóa duplicate khỏi artifact corrupted.
2. Ghi đầy đủ duplicate vào corruption log và quality report.
3. Deduplicate một bản sao DataFrame chỉ dành cho bước index.
4. Chạy lại test và kiểm tra cả quality lẫn evaluation flow.

**Kết quả:** Corrupted quality vẫn FAIL đúng dự kiến, pipeline vẫn index/evaluate được và baseline không bị thay đổi.

---

## 7. Trả lời câu hỏi end-to-end

### 7.1. Dữ liệu đi từ Crossref tới vector database như thế nào?

Crossref payload được parse thành record chuẩn và lưu thành raw snapshot. Cleaning đọc raw, làm sạch text, chuẩn hóa authors/categories, loại bản ghi không hợp lệ, tính các trường dẫn xuất và lưu clean CSV/JSON. `text_for_embedding` sau đó được embedding và lưu cùng `paper_id`/metadata trong vector database để phục vụ truy hồi.

### 7.2. Ground truth nối với tài liệu retrieval bằng cách nào?

Mỗi câu hỏi trong test set chứa danh sách `ground_truth_doc_ids`. Các ID này sử dụng cùng `paper_id` ổn định của clean data. Khi truy hồi, hệ thống so sánh ID tài liệu trả về với ground truth để tính hit rate; nội dung câu trả lời được so sánh bằng token F1 và judge metrics.

### 7.3. Quality khác freshness ở điểm nào?

Quality kiểm tra tính hợp lệ tổng quát như schema, null, độ dài summary, tính duy nhất và tính nhất quán giữa các trường. Freshness tập trung vào độ mới của dữ liệu, sử dụng `published`, `age_days` và ngưỡng stale. Một dataset có thể đúng schema nhưng vẫn không đạt freshness nếu ngày xuất bản quá cũ.

### 7.4. Vì sao phải dùng cùng test set cho ba lần chạy?

Nếu đổi câu hỏi hoặc ground truth giữa các lần chạy, không thể kết luận metric thay đổi do corruption. Cùng test set tạo điều kiện kiểm soát để so sánh baseline, corrupted và repaired một cách công bằng.

### 7.5. Làm sao chứng minh repair thành công?

Repair được coi là thành công khi đồng thời thỏa bốn điều kiện: repaired data bằng baseline, quality trở lại PASS, freshness trở lại Fresh và các retrieval/answer metrics trở về giá trị baseline. Chỉ việc tạo được file repaired chưa đủ để kết luận.

---

## 8. Kiểm thử và lệnh tái lập

Chạy toàn bộ test:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Chạy test riêng cho Role 3:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_role3_cleaning_corruption.py -v
```

Xác thực CP2:

```powershell
.\.venv\Scripts\python.exe script/validate_role3_cp2.py
```

Chạy và xác thực CP5:

```powershell
.\.venv\Scripts\python.exe script/run_role3_cp5.py
.\.venv\Scripts\python.exe script/validate_role3_cp5.py
```

Xác thực CP6:

```powershell
.\.venv\Scripts\python.exe script/validate_role3_cp6.py
```

---

## 9. Bài học rút ra

- Data cleaning cần một contract rõ ràng, có thể kiểm thử, thay vì chỉ xử lý text theo cảm tính.
- Corruption phải deterministic và auditable thì mới so sánh được nhiều lần chạy.
- Artifact dùng để quan sát chất lượng và view dùng để vận hành có thể cần tách riêng mục đích.
- Repair nên tái tạo từ nguồn tin cậy thay vì vá lần lượt từng lỗi trên dữ liệu hỏng.
- Chất lượng dữ liệu không chỉ ảnh hưởng số dòng hay schema mà còn làm giảm trực tiếp retrieval hit rate và chất lượng câu trả lời.
- Đánh giá repair phải kết hợp data equality, quality/freshness và RAG metrics.

---

## 10. Tự đánh giá mức độ hoàn thành

- [x] Hoàn thành clean schema và quy tắc null/date/duplicate/authors/categories.
- [x] Tạo đúng `authors_joined`, `categories_joined`, `age_days` và `text_for_embedding`.
- [x] Lưu clean data ở cả CSV và JSON.
- [x] Xây dựng 6 corruption scenario có log kiểm toán.
- [x] Không làm thay đổi baseline khi chạy corruption.
- [x] Xác thực corrupted quality chuyển PASS → FAIL.
- [x] Xác thực repair khôi phục dữ liệu bằng baseline.
- [x] Xác thực quality/freshness chuyển PASS → FAIL → PASS.
- [x] Xác thực retrieval và answer metrics giảm khi corrupted và phục hồi sau repair.
- [x] Test cuối cùng đạt 38/38.

**Kết luận:** Tôi đã hoàn thành đầy đủ phạm vi Vai trò 3 từ CP0 đến CP6, bao gồm cleaning, corruption, repair, validation và cung cấp bằng chứng end-to-end về tác động của chất lượng dữ liệu lên hệ thống RAG.
