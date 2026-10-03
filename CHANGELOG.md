# Changelog

Tất cả những thay đổi đáng chú ý của dự án **AI Prompt Studio** (`ai_prompts_database`) sẽ được ghi nhận trong tệp này.

Định dạng dựa trên [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
và dự án tuân thủ [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.1.0] - 2026-10-03

### Thêm mới (Added)
- **Headless-First CLI (`cli.py`):**
  - Xây dựng công cụ CLI độc lập hoàn toàn với máy chủ Web, trực tiếp kết nối SQLite Database.
  - Hỗ trợ đầy đủ cờ `--json` xuất JSON sạch ra `stdout` cho các tác vụ tự động hóa và piping.
  - Toàn bộ log tiến trình và thông báo lỗi ghi sang `stderr`.
  - Cấu hình chuẩn UTF-8 chống lỗi font `cp1252` trên Windows PowerShell và CMD.
  - Cung cấp các lệnh: `list`, `get`, `add`, `update`, `delete`, `tags`, `stats`, `export`, `serve`.
- **Đăng ký Windows Toàn Hệ Thống:**
  - Shim launcher `bin/aff-prompt.cmd` và `bin/aff-prompt` tự động trỏ vào `.venv` hoặc Python hệ thống.
  - Script `scripts/register_windows.ps1` tự động thêm `bin/` vào User `PATH` (không cần quyền Admin) và tạo Shortcut Desktop/Start Menu.
  - Script `scripts/unregister_windows.ps1` gỡ bỏ sạch sẽ khỏi User `PATH` và xóa Shortcut.
- **Tài liệu API Tự động (OpenAPI Reference):**
  - Cấu hình OpenAPI Metadata cho FastAPI (`title`, `version`, `description`, `openapi_tags`).
  - Xây dựng bộ Pydantic v2 schemas chi tiết tại `app/api/schemas.py` kèm mô tả thuộc tính và ví dụ mẫu.
  - Biên soạn tài liệu đặc tả API toàn diện tại `docs/api_reference.md`.
- **Kiểm thử tự động:**
  - Bổ sung `tests/test_cli_headless.py` kiểm thử toàn bộ lệnh CLI ở chế độ Headless.
  - Bổ sung `tests/test_api_docs.py` kiểm thử HTTP 200 tại `/docs`, `/redoc` và `/openapi.json`.

### Sửa lỗi (Fixed)
- Sửa lỗi `NameError: name 'thumb_web_url' is not defined` trong `app/services/koc_service.py:253`.
- Khôi phục tính nhất quán cho URL ảnh KOC và đường dẫn thumbnail S3.

### Thay đổi (Changed)
- Tái cấu trúc `README.md` với hướng dẫn sử dụng chi tiết cả 2 giao diện Web SPA và CLI `aff-prompt`.
- Cập nhật số phiên bản dự án lên `1.1.0`.

---

## [1.0.1] - 2026-09-20
- Bổ sung hỗ trợ ảnh KOC thumbnail tối ưu tải trang nhanh.
- Nâng cấp cơ chế tải ảnh đa luồng và lưu trữ S3 Backblaze.

## [1.0.0] - 2026-09-08
- Phát hành phiên bản đầu tiên của AI Prompt Studio với giao diện Web Dark Theme.
- Quản lý 400+ Prompt đa dạng cho Chân dung, Storyboard và Video.
