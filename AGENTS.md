# Quy Tắc Phát Triển Dự Án AI Prompts Database

## 1. Quản lý tệp tạm (Scratch) và tệp kiểm thử (Tests)
- **Tệp tạm (Temporary / Scratch):** Mọi script nháp, file dump tạm thời, JSON test nhanh BẮT BUỘC đặt trong thư mục `scratch/`.
- **Tệp kiểm thử (Tests):** Mọi script test đơn vị, test tích hợp, test frontend/backend BẮT BUỘC đặt trong thư mục `tests/`.
- **Tuyệt đối cấm:** Tạo file `.py`, `.js`, `.json`, `.txt`, `.tmp` thử nghiệm rải rác ở thư mục gốc hoặc các thư mục mã nguồn (`app/`, `data/`).

## 2. Tiêu chuẩn kiến trúc & Dịch vụ
- Cấu hình mô hình đọc tập trung qua `app.config.get_ai_config()`, `get_video_models()`, `get_image_models()`.
- Các service tạo ảnh (`image_generator.py`) và tạo video (`video_generator.py`) xử lý độc lập, nhất quán cơ chế fallback và lưu trữ media qua `IMAGES_DIR` / S3.
