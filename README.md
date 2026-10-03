# 🪄 AI Prompt Studio (`ai_prompts_database`)

> Hệ sinh thái quản lý, tùy biến và sinh câu lệnh Prompt AI đa năng (Storyboard, Chân dung KOC, Video quảng cáo, Content) với **FastAPI**, **SQLite**, giao diện **Web SPA** và giao diện dòng lệnh **Headless-First CLI (`aff-prompt`)**.

---

## 🌟 Tính năng nổi bật

1. **Giao diện Dòng lệnh Độc lập (Headless-First CLI - `aff-prompt`):**
   - Vận hành 100% độc lập qua SQLite, **không yêu cầu** bật máy chủ Web.
   - Hỗ trợ cờ `--json` xuất dữ liệu sạch ra `stdout`, nhật ký và thông báo lỗi ghi sang `stderr`.
   - Cấu hình chuẩn UTF-8 chống lỗi hiển thị trên Windows PowerShell và CMD. Mã thoát chuẩn: `0` (thành công), `1` (thất bại).
2. **Giao diện Web SPA Trực quan:**
   - Tìm kiếm, lọc theo thẻ tag, tinh chỉnh tham số prompt trực tiếp theo thời gian thực.
   - Thư viện nhân vật KOC AI, xem trước và lưu trữ ảnh mẫu cục bộ / S3 Backblaze.
3. **Tài liệu API Tự động (OpenAPI Reference):**
   - Đầy đủ bộ tài liệu trực quan tại `/docs/api`: Swagger UI (`/docs/api/swagger`), ReDoc (`/docs/api/redoc`) và OpenAPI JSON (`/docs/api/openapi.json`).
   - Bộ tệp tĩnh xuất sẵn tại thư mục `docs/api/` (`index.html`, `swagger.html`, `redoc.html`, `openapi.json`).
   - Mô hình dữ liệu Pydantic v2 chi tiết kèm mô tả trường và ví dụ mẫu.
4. **Tích hợp Windows Một chạm:**
   - Shim launcher `bin/aff-prompt.cmd` tự động tìm Python `.venv` nội bộ.
   - Script PowerShell đăng ký công cụ vào User `PATH` không cần quyền Administrator.

---

## 📂 Cấu trúc thư mục dự án

```text
ai_prompts_database/
│
├── app/                           # Mã nguồn Backend
│   ├── api/
│   │   ├── routes.py              # REST API Router endpoints
│   │   └── schemas.py             # Pydantic v2 Models & OpenAPI Schemas
│   ├── db/
│   │   ├── database.py            # Kết nối & Khởi tạo SQLite
│   │   └── repository.py          # Xử lý truy vấn dữ liệu Prompt, Images & Tags
│   ├── services/                  # Dịch vụ nghiệp vụ (AI, KOC, S3, Parser)
│   ├── config.py                  # Cấu hình tập trung & biến môi trường
│   └── main.py                    # Khởi tạo ứng dụng FastAPI & OpenAPI Metadata
│
├── public/                        # Tài nguyên Web tĩnh & Giao diện SPA
│   ├── index.html                 # Giao diện HTML SPA
│   ├── js/                        # JavaScript frontend (app.js)
│   ├── css/                       # CSS stylesheet
│   ├── favicon.ico                # App icon & Web favicon
│   └── favicon.png                # PNG icon
│
├── bin/                           # Shim launchers toàn hệ thống
│   ├── aff-prompt.cmd             # Windows CMD/PowerShell launcher
│   └── aff-prompt                 # Shell / Git Bash launcher
│
├── data/                          # Lưu trữ dữ liệu
│   ├── prompts.db                 # SQLite Database chính
│   └── images/                    # Thư mục lưu trữ hình ảnh tải về
│
├── docs/                          # Tài liệu kỹ thuật
│   ├── api_reference.md           # Đặc tả chi tiết danh mục REST API
│   └── api/                       # Bộ tài liệu API tĩnh (Swagger, ReDoc, OpenAPI JSON)
│       ├── index.html             # API Docs Hub
│       ├── swagger.html           # Standalone Swagger UI
│       ├── redoc.html             # Standalone ReDoc
│       └── openapi.json           # Tệp đặc tả OpenAPI 3.x schema
│
├── scripts/                       # Scripts tiện ích & Quản trị Windows
│   ├── register_windows.ps1       # Tự động thêm bin vào User PATH & tạo Shortcut
│   └── unregister_windows.ps1     # Gỡ bỏ bin khỏi User PATH và xóa Shortcut
│
├── tests/                         # Bộ kiểm thử tự động (pytest)
│   ├── test_s3_features.py        # Kiểm thử tích hợp S3 và KOC service
│   ├── test_cli_headless.py       # Kiểm thử CLI Headless
│   └── test_api_docs.py           # Kiểm thử OpenAPI & Docs endpoint
│
├── cli.py                         # Điểm vào chính của dòng lệnh CLI Headless
├── run.py                         # Script khởi động Web Server Uvicorn
├── requirements.txt               # Thư viện phụ thuộc
├── CHANGELOG.md                   # Nhật ký thay đổi phiên bản
└── README.md                      # Tài liệu hướng dẫn sử dụng
```

---

## 🚀 Cài đặt & Đăng ký Windows

### Bước 1: Cài đặt thư viện Python
Khuyến nghị sử dụng Python 3.10 trở lên:
```bash
pip install -r requirements.txt
```

### Bước 2: Đăng ký lệnh `aff-prompt` toàn hệ thống (Windows)
Chạy script PowerShell (không cần quyền Admin):
```powershell
powershell -ExecutionPolicy Bypass -File scripts\register_windows.ps1
```
*Script sẽ tự động thêm thư mục `bin/` vào User `PATH` và tạo Shortcut trên Desktop.*

Để gỡ cài đặt khỏi PATH:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\unregister_windows.ps1
```

---

## 💻 Hướng dẫn sử dụng Dòng lệnh CLI (`aff-prompt`)

Sau khi đăng ký (hoặc chạy trực tiếp `python cli.py`), bạn có thể gọi `aff-prompt` ở bất kỳ thư mục nào:

### 1. Bảng tra cứu lệnh chính

| Lệnh | Ý nghĩa | Ví dụ |
| :--- | :--- | :--- |
| `aff-prompt list` | Liệt kê danh sách prompts | `aff-prompt list --limit 10 --category image` |
| `aff-prompt get` | Xem chi tiết 1 prompt | `aff-prompt get prompt_1 --json` |
| `aff-prompt add` | Thêm prompt mới | `aff-prompt add --content "Prompt..." --title "Tiêu đề"` |
| `aff-prompt update` | Cập nhật thông tin prompt | `aff-prompt update prompt_1 --title "Tiêu đề mới"` |
| `aff-prompt delete` | Xóa prompt khỏi database | `aff-prompt delete prompt_99 --force` |
| `aff-prompt tags` | Quản lý danh mục thẻ tags | `aff-prompt tags list --json` |
| `aff-prompt stats` | Xem thống kê tổng quan DB | `aff-prompt stats --json` |
| `aff-prompt export` | Xuất prompts ra file JSON | `aff-prompt export -o backup.json --category image` |
| `aff-prompt serve` | Khởi chạy máy chủ Web UI | `aff-prompt serve --port 8000` |

### 2. Ví dụ sử dụng CLI Headless & Pipe JSON

**Tra cứu và xuất JSON sạch:**
```bash
# Lấy thống kê dạng JSON
aff-prompt stats --json

# Lấy 5 prompt chân dung dạng JSON
aff-prompt list --tag portrait --limit 5 --json

# Lấy mã prompt thuần để dán vào công cụ khác
aff-prompt get prompt_1 --raw
```

**Thêm prompt từ tệp hoặc qua pipe:**
```bash
# Thêm từ tham số trực tiếp
aff-prompt add --content "A cinematic photo of Vietnamese woman in studio..." --title "KOC Studio #1" --category image

# Thêm từ tệp văn bản
aff-prompt add -f my_prompt.txt --title "Prompt từ tệp" --category video
```

---

## 🌐 Giao diện Web & Tài liệu API

### Khởi động Web Server
```bash
# Bằng lệnh toàn hệ thống
aff-prompt serve

# Hoặc bằng Python trực tiếp
python run.py
```
Máy chủ sẽ mở tại `http://127.0.0.1:8000` (hoặc cổng ngẫu nhiên nếu bị chiếm dụng).

### Tài liệu API Trực quan
Khi Web Server đang chạy, truy cập:
- **API Documentation Hub:** `http://127.0.0.1:8000/docs/api`
- **Swagger UI:** `http://127.0.0.1:8000/docs/api/swagger` (hoặc `/docs`)
- **ReDoc:** `http://127.0.0.1:8000/docs/api/redoc` (hoặc `/redoc`)
- **OpenAPI Schema:** `http://127.0.0.1:8000/docs/api/openapi.json` (hoặc `/openapi.json`)

Xem đặc tả chi tiết danh mục API tại: [docs/api_reference.md](docs/api_reference.md).
Xem bộ tài liệu API tĩnh tại: [docs/api/index.html](docs/api/index.html).

---

## 🧪 Kiểm thử tự động (Test Suite)

Chạy toàn bộ bài test:
```bash
pytest
```
Chạy riêng các bài test chức năng CLI và API Docs:
```bash
pytest tests/test_cli_headless.py tests/test_api_docs.py
```

---

## 📄 Bản quyền & Tác giả
- Tác giả: Phương Dev
- Dự án: AI Prompt Studio (`ai_prompts_database`)
