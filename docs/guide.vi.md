# Tài liệu dự án CareSync

Kiến trúc và hướng dẫn triển khai end to end

CareSync tập hợp mã điều phối Azure Data Factory và notebook Databricks trong **một repository**. Tài liệu giải thích luồng dữ liệu, 5 pipeline, mô hình Gold, cách cấu hình CI/CD và cách chuyển từ hai repo sang cấu trúc chung.

Đích xử lý là ba bảng phân tích trên nền dữ liệu bệnh nhân, bệnh viện, bảo hiểm và xét nghiệm. Luồng chính đi từ PostgreSQL và CSV qua Landing, Bronze, Silver đến Gold, sau đó gửi yêu cầu thông báo qua Logic Apps.

![Kiến trúc tổng thể của CareSync](images/architecture.png)

Bắt đầu từ README ở thư mục gốc. Khi triển khai, dùng docs/deployment.md; khi chuyển repo, dùng docs/migration.md. Các hình pipeline mô tả logic trong JSON, không phải ảnh chụp giao diện Azure.

## 01 Luồng dữ liệu end to end

ADF giữ vai trò điều phối. Databricks xử lý dữ liệu; Azure SQL quyết định bảng nào được nạp và lưu trạng thái của từng lần chạy. Hai hệ thống nguồn được xử lý song song trước khi tổng hợp Gold.

| Tầng | Vị trí | Cách xử lý |
| --- | --- | --- |
| Source | PostgreSQL và container source | Bảng quan hệ và các file CSV |
| Landing | Container landing | Lưu batch theo hệ thống nguồn, bảng và timestamp |
| Bronze | adb_healthy.bronze | Append dữ liệu batch và bổ sung thông tin nạp |
| Silver | adb_healthy.silver | FULL, APPEND hoặc MERGE theo metadata |
| Gold | adb_healthy.gold | Xây lại ba bảng phân tích bằng Spark SQL |

1. Trigger gọi PL_MASTER. Lịch đang được cấu hình mỗi 8 giờ theo múi giờ UTC+7; tên DAILY không có nghĩa là mỗi ngày một lần.
2. Master gọi hai nhánh neon_postgres và adls_csv. Mỗi nhánh đọc danh sách bảng đang hoạt động từ ctrl.table_config.
3. Inner pipeline đọc metadata và watermark, copy dữ liệu vào Landing rồi gọi lần lượt hai notebook Bronze và Silver.
4. Khi cả hai nhánh nguồn thành công, pipeline Gold chọn notebook theo gold_table_name và chạy các bảng độc lập song song.
5. Pipeline thông báo đọc audit theo Run ID của master, lấy callback URL từ Key Vault rồi POST nội dung sang Logic Apps.

### Theo dõi xuyên suốt

Master truyền RunId của chính nó vào các pipeline con qua adf_run_id. Giá trị này liên kết các bản ghi SOURCE_TO_SILVER và SILVER_TO_GOLD trong ctrl.audit_log, giúp tra cứu một lượt xử lý từ đầu đến cuối.

Trigger trong bản bàn giao ở trạng thái Stopped. Chỉ bật sau khi đã kiểm tra nguồn, quyền truy cập, metadata và một lượt chạy thủ công.

## 02 Pipeline điều phối tổng thể

**PL_MASTER** không nhận tham số đầu vào. Pipeline tạo hai nhánh xử lý nguồn độc lập và đợi cả hai thành công trước khi gọi Gold.

![PL_MASTER và điều kiện phụ thuộc giữa các nhánh](images/01-pl-master.png)

| Activity | Pipeline được gọi | Điều kiện chạy |
| --- | --- | --- |
| Source to Silver Postgres | PL_SOURCE_TO_SILVER_MAIN | Bắt đầu trực tiếp |
| Source to Silver ADLS CSV | PL_SOURCE_TO_SILVER_MAIN | Bắt đầu trực tiếp |
| Silver to Gold | PL_SILVER_TO_GOLD | Cả hai nhánh nguồn Succeeded |
| Send_Email | PL_SEND_EMAIL | Nhánh Gold Succeeded |

Cả hai nhánh cùng nhận adf_run_id là Run ID của master, nhưng source_system khác nhau. Các ExecutePipeline đều đợi pipeline con hoàn tất.

Email hiện nằm trên nhánh thành công. Nếu nguồn hoặc Gold thất bại, pipeline thông báo có thể bị bỏ qua; không dùng cấu hình này như một cơ chế bảo đảm gửi email khi lỗi.

## 03 Pipeline xử lý theo hệ thống nguồn

**PL_SOURCE_TO_SILVER_MAIN** nhận source_system và adf_run_id. Đây là lớp điều phối theo danh sách bảng, giúp tái sử dụng cùng một logic cho PostgreSQL và CSV.

![Vòng lặp song song theo các bảng nguồn đang hoạt động](images/02-pl-source-to-silver-main.png)

1. Lookup đọc table_id có is_active = 1, stage = SOURCE_TO_SILVER và đúng source_system.
2. Với mỗi bảng, ghi một audit row có trạng thái IN_PROGRESS trước khi gọi inner pipeline.
3. Gọi PL_SOURCE_TO_SILVER_INNER, truyền table_id và adf_run_id, đồng thời chờ kết quả.
4. Nếu inner thất bại, ghi FAILED và dùng Fail activity để phản ánh lỗi. Trạng thái thành công được cập nhật bên trong inner.

ForEach được cấu hình không tuần tự. Cần chọn mức song song phù hợp với tài nguyên Databricks và Azure SQL, đồng thời tránh hai lượt master cùng xử lý một bảng và cùng cập nhật watermark.

## 04 Pipeline xử lý từng bảng

**PL_SOURCE_TO_SILVER_INNER** nhận table_id và adf_run_id. Pipeline xử lý một batch từ nguồn đến Silver; timestamp tạo đầu lượt được dùng làm tên thư mục Landing và bộ lọc trong notebook.

![Hai nhánh copy hội tụ trước khi chạy Bronze và Silver](images/03-pl-source-to-silver-inner.png)

PostgreSQL ghi Parquet; CSV được copy theo file. Với tải không FULL, pipeline đọc watermark trước khi copy và cập nhật watermark sau khi Silver thành công. Cập nhật audit thành công và watermark là hai thao tác độc lập.

## 05 Pipeline tổng hợp Gold

**PL_SILVER_TO_GOLD** nhận adf_run_id, đọc metadata stage SILVER_TO_GOLD và chạy từng Gold notebook trong một vòng lặp song song.

![Gold notebook được chọn theo metadata](images/04-pl-silver-to-gold.png)

| gold_table_name | Notebook |
| --- | --- |
| patient_360 | Gold/NB_patient_360 |
| hospital_daily_summary | Gold/NB_hospital_daily_summary |
| lab_test_trends | Gold/NB_lab_test_trends |

Đường dẫn notebook được ghép từ databricks_notebook_root và tên mô hình. Mỗi notebook trả row count qua dbutils.notebook.exit; pipeline lưu giá trị này vào records_written.

Ba mô hình dùng CREATE OR REPLACE TABLE nên xây lại toàn bộ bảng Gold mỗi lần chạy. Đây không phải tải Gold tăng dần.

## 06 Pipeline thông báo

**PL_SEND_EMAIL** nhận adf_run_id. Pipeline tạo tiêu đề và nội dung từ các audit row của cùng một lượt master, sau đó gọi Logic Apps.

![Tạo nội dung email và lấy callback URL từ Key Vault lúc chạy](images/05-pl-send-email.png)

Bản gộp bổ sung Get Logic App URL dùng managed identity của ADF. Secure Output được bật khi đọc secret; HTTP POST dùng Secure Input và Secure Output. Callback URL được lưu trong secret logic-app-callback-url.

Hợp đồng HTTP giữ nguyên các trường subject, email_receipients, body_header, body_footer và status_table. Workflow Logic Apps nhận HTTP, tạo bảng HTML và gọi email connector; cấu hình sender và connector được thực hiện trong môi trường Azure.

## 07 Mô hình dữ liệu và chiến lược nạp

| Mô hình Gold | Độ chi tiết | Nội dung chính |
| --- | --- | --- |
| patient_360 | Một dòng mỗi bệnh nhân | Thông tin bệnh nhân, bệnh viện, bảo hiểm và tổng hợp xét nghiệm |
| hospital_daily_summary | Bệnh viện và ngày có xét nghiệm | Sản lượng, số bệnh nhân, bác sĩ và số kết quả bất thường hoặc nghiêm trọng |
| lab_test_trends | Tên xét nghiệm và tháng | Số lượng, tỷ lệ bất thường và thay đổi so với tháng có dữ liệu trước đó |

### Chiến lược tại Silver

- **FULL:** ghi đè bảng đích bằng batch đang được xử lý.
- **APPEND:** thêm toàn bộ batch; chạy lại có thể tạo bản ghi trùng.
- **MERGE:** upsert theo merge_keys; giữ insert_timestamp cũ khi cập nhật bản ghi đã tồn tại. Khóa phải có trong dữ liệu và dữ liệu nguồn cần duy nhất theo khóa.

### Các điều kiện dữ liệu cần giữ

Tên bảng nguồn, Bronze và Silver cần bằng nhau trong cách dựng đường dẫn hiện tại. Catalog được dùng cố định là adb_healthy. Volume được viết là landing_volumne để tương thích notebook hiện có.

Gold cần các bảng Silver patients, hospitals, insurance_providers, lab_results và calendar. Lấy tên cột cụ thể từ docs/deployment.md và SQL của notebook; notebook Silver chủ yếu áp dụng chiến lược ghi và cột audit, chưa phải bộ làm sạch dữ liệu tổng quát.

Các Gold notebook khử trùng lab_result_id theo update_timestamp giảm dần. Nếu thời gian bằng nhau thì chưa có tiêu chí phụ để chọn bản ghi. Các bảng chiều được join phải duy nhất theo khóa để giữ đúng độ chi tiết.

LAG tại bảng ngày so sánh với ngày có dữ liệu trước đó; tại bảng tháng so sánh với tháng có dữ liệu trước đó. Các kỳ bị thiếu không được tự điền. Workbook STTM gốc được giữ tại docs/data-model/sttm_silver_to_gold.xlsx.

## 08 Thiết lập môi trường

Chuẩn bị các tài nguyên trước khi chạy: ADF, ADLS Gen2, Azure SQL, Key Vault, Databricks hỗ trợ Unity Catalog, nguồn PostgreSQL và Logic Apps có email connector.

| Thành phần | Cấu hình quan trọng |
| --- | --- |
| Storage và Unity Catalog | Container source, landing; external location; volume adb_healthy.landing.landing_volumne |
| ADF | Managed identity, quyền đọc secrets, quyền storage, kết nối SQL và PostgreSQL |
| Databricks | Cluster hoạt động; quyền chạy notebook và truy cập catalog, schemas, volume |
| Azure SQL | ctrl.table_config, ctrl.watermark, ctrl.audit_log và metadata đúng nguồn |
| Key Vault | postgres-passwords, medata-db-passworld, azure-databrick-token, logic-app-callback-url |

1. Sao chép config/environment.example.json thành config/environment.local.json và điền đủ các giá trị của môi trường.
2. Chạy configure_environment.py để cập nhật linked services và factory globals, rồi chạy validate_repo.py.
3. Giữ metadata đang dùng nếu triển khai hiện hữu. Với cài mới, rà soát SQL khởi tạo và seed ví dụ; seed được để is_active = 0 cho đến khi xác minh xong nguồn.
4. Tạo external location và Landing volume đúng container, import notebook, chạy setup/Calendar_Dimension_Build một lần.
5. Tạo Logic Apps theo docs/logic-apps.md, lưu callback URL vào Key Vault và cấp quyền cho managed identity của ADF.
6. Kết nối ADF với repo chung, kiểm tra linked services, Validate All, Publish All rồi chạy PL_MASTER thủ công.

```text
python tools/configure_environment.py --config config/environment.local.json
python tools/validate_repo.py
```

File cấu hình cục bộ không chứa mật khẩu, token hoặc callback URL. Các secret được lưu riêng; script không tự tạo hay thay đổi tài nguyên trên Azure.

## 09 Gộp repo và cấu hình CI CD

Tên repo đề xuất là caresync-e2e. Đặt toàn bộ thư mục đã gộp làm gốc repo mới; không đặt hai thư mục repo cũ lồng vào nhau.

| Mã nguồn | Thư mục mới |
| --- | --- |
| ADF pipelines, datasets và linked services | adf/ |
| Notebook Bronze, Silver và Gold | databricks/notebooks/ |
| Calendar Dimension Build | databricks/notebooks/setup/ |
| STTM, sơ đồ và hướng dẫn | docs/ |
| Notebook thử, test pipeline và SQL ngoài luồng | archive/ |

| Cấu hình | Giá trị cần đồng bộ |
| --- | --- |
| ADF Git root | /adf |
| Collaboration và publish branch | main và adf_publish |
| ADF databricks_notebook_root | /Shared/caresync/databricks |
| GitHub DATABRICKS_WORKSPACE_ROOT | Cùng giá trị với root notebook của ADF |

CI kiểm tra cấu trúc và hợp đồng giữa pipeline với notebook. Workflow deploy Databricks import thư mục notebook khi có thay đổi phù hợp trên main, hoặc khi chạy thủ công. Khai báo DATABRICKS_HOST và DATABRICKS_WORKSPACE_ROOT dạng variable, DATABRICKS_TOKEN dạng secret trong GitHub environment dev.

ADF vẫn dùng Git authoring và Publish All. Commit lên main chưa làm thay đổi factory đang chạy. Bản này chưa bổ sung quy trình tự động triển khai ARM giữa nhiều môi trường ADF.

ZIP là bản working tree gộp, không gộp lịch sử commit. Hai repo GitHub gốc chưa bị thay đổi. Nếu cần giữ cả hai lịch sử, thực hiện thêm bước migration Git trước khi chốt repo mới.

Xem docs/migration.md để lấy lệnh tạo repo, trình tự đổi kết nối và cách tránh chạy đồng thời lịch cũ với lịch mới.

## 10 Kiểm tra và vận hành

Sau khi cấu hình xong, chạy PL_MASTER thủ công và lưu Run ID. Xác nhận đúng số bảng mong đợi thay vì chỉ kiểm tra không có lỗi.

| Hạng mục | Tiêu chí kiểm tra |
| --- | --- |
| Metadata | Đủ bảng nguồn và Gold đang hoạt động; không để toàn bộ seed ở trạng thái tắt |
| Luồng xử lý | Hai nhánh nguồn xong trước Gold; Gold xong trước thông báo |
| Landing và Silver | Thư mục timestamp đúng; số dòng phù hợp với batch đầu vào đã biết |
| Gold | Ba bảng tồn tại và không trùng khóa theo độ chi tiết đã định |
| Audit | Đủ dòng theo Run ID; mỗi bảng có trạng thái kết thúc phù hợp |
| Watermark | Chỉ cập nhật cho các bảng tăng dần dự kiến và đã xử lý đúng batch |
| Logic Apps | HTTP và email action thành công; người nhận nhận đúng thông báo |

### Các file hỗ trợ kiểm tra

- sql/control/03_check_execution.sql: tra audit và watermark; thay Run ID bằng giá trị thực tế.
- sql/databricks/02_gold_quality_checks.sql: kiểm tra grain của Gold và trùng lab_result_id ở Silver.
- docs/operations.md: quy trình rà soát lỗi, chạy lại và rollback phần mã nguồn.

### Khi cần chạy lại

Kiểm tra dữ liệu đã ghi, watermark và audit trước khi chạy lại. Pipeline thất bại không có nghĩa là chưa ghi dữ liệu. Bronze dùng append nên replay có thể tạo trùng; Silver APPEND cũng có cùng rủi ro. FULL có thể ghi đè dữ liệu; MERGE vẫn cần khóa đúng và dữ liệu nguồn không trùng.

Rollback notebook bằng commit cũ chỉ khôi phục mã. Nó không tự khôi phục bảng Delta, watermark hoặc nội dung control database. Cần xử lý phần dữ liệu theo một bước phục hồi riêng.

## 11 Giới hạn và cách hoàn thiện

| Vấn đề | Hiện trạng và hướng xử lý |
| --- | --- |
| Email khi lỗi | Email chỉ được gọi sau Gold thành công. Bổ sung nhánh kết thúc phù hợp và kiểm thử giữ đúng trạng thái thất bại của master. |
| Watermark | Đang tăng theo SYSUTCDATETIME sau xử lý; có thể bỏ sót dữ liệu phát sinh trong lúc chạy. Nên chụp upper bound trước extraction, nạp trong cửa sổ cố định rồi mới tăng watermark. |
| Batch rỗng | Landing có thể exit bằng thông báo nhưng Silver vẫn tiếp tục. Cần nhánh no-data rõ ràng để tránh FULL ghi đè bằng dữ liệu rỗng. |
| Replay và audit | Chưa có bảo đảm exactly-once hay giao dịch chung giữa Delta, audit và watermark. Cần đối soát khi lỗi một phần. |
| Kiểm tra dữ liệu | Chưa có framework schema enforcement, masking hay chất lượng dữ liệu tổng quát. Gold có các giả định về khóa duy nhất và kiểu dữ liệu. |

### Những thay đổi của bản gộp

Notebook path chuyển sang một global root; lookup nguồn có thêm stage filter; callback URL chuyển vào Key Vault; CSV FULL không dùng watermark rỗng; trigger chuyển Stopped; notebook outputs được xóa. Các workflow GitHub, SQL mẫu, sơ đồ và hướng dẫn là phần được bổ sung.

URL Logic Apps cũ có chữ ký gọi trực tiếp. Cần tạo lại chữ ký trước khi dùng lại endpoint. Việc bỏ URL khỏi bản repo mới không vô hiệu URL cũ hoặc xóa nội dung đã có trong lịch sử repo cũ.

### Giới hạn của kiểm tra cục bộ

Kiểm tra đã chuẩn bị ở mức cấu trúc file, tham chiếu ADF, đồ thị phụ thuộc, widgets và cú pháp Python. Việc xác nhận Spark SQL, quyền Azure, dữ liệu nguồn và email thực tế thuộc lượt smoke test trong môi trường triển khai.

## 12 Tìm file và bổ sung ảnh thật

| Nhu cầu | Đọc hoặc mở file |
| --- | --- |
| Giới thiệu GitHub | README.md |
| Triển khai theo từng bước | docs/deployment.md |
| Mô tả tham số và activity | docs/pipelines.md |
| Chuyển từ hai repo sang một | docs/migration.md |
| Cấu hình thông báo | docs/logic-apps.md |
| Chạy thử, xử lý lỗi và rollback | docs/operations.md |
| Hình pipeline và sơ đồ có thể sửa | docs/images/ và docs/diagrams/ |
| Hướng dẫn thêm screenshot ADF | docs/screenshots/README.md |

Sơ đồ trong tài liệu dùng để giải thích luồng xử lý của JSON. Khi thêm ảnh chụp ADF thật, lưu đúng các tên dưới đây và dùng đoạn Markdown đã chuẩn bị trong hướng dẫn screenshot.

| Pipeline | Tên ảnh chụp đề xuất |
| --- | --- |
| PL_MASTER | 01-pl-master-adf.png |
| PL_SOURCE_TO_SILVER_MAIN | 02-pl-source-to-silver-main-adf.png |
| PL_SOURCE_TO_SILVER_INNER | 03-pl-source-to-silver-inner-adf.png |
| PL_SILVER_TO_GOLD | 04-pl-silver-to-gold-adf.png |
| PL_SEND_EMAIL | 05-pl-send-email-adf.png |

Chụp toàn bộ canvas ở mức zoom đọc được nhãn activity. Với ForEach và Switch, có thể bổ sung ảnh phần bên trong. Để thể hiện kết quả chạy, dùng thêm ảnh Monitor của lượt chạy thực tế và mô tả đúng thời điểm, trạng thái và số liệu của lượt đó.

### Tài liệu kỹ thuật tham khảo

- [Microsoft Learn về ADF source control và publishing](https://learn.microsoft.com/en-us/azure/data-factory/source-control)
- [Microsoft Learn về Databricks workspace CLI](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/cli/reference/workspace-commands)
- [Databricks setup cli cho GitHub Actions](https://github.com/databricks/setup-cli)
- [Microsoft Learn về Key Vault secrets trong pipeline](https://learn.microsoft.com/en-us/azure/data-factory/how-to-use-azure-key-vault-secrets-pipeline-activities)
