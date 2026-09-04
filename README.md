# 🪄 AI Prompt Studio - Quản lý & Tùy biến Prompt AI

Dự án Python hoàn chỉnh phục vụ việc quản lý, tìm kiếm, tùy biến tham số theo thời gian thực và quản trị bộ sưu tập hàng trăm Prompt AI (Storyboard, Chân dung, Video KOC,...) với Backend **FastAPI** và Cơ sở dữ liệu **SQLite**.

---

## 📂 Cấu trúc thư mục dự án

```text
phan_tich_1/
│
├── app/                           # Ứng dụng Backend Web & Giao diện
│   ├── api/
│   │   └── routes.py              # REST API (/api/prompts, /api/stats, /api/export)
│   ├── db/
│   │   ├── database.py            # Kết nối & Khởi tạo SQLite
│   │   └── repository.py          # Xử lý truy vấn dữ liệu Prompt & Images
│   ├── static/                    # Frontend static assets
│   │   └── js/
│   │       └── app.js             # Logic điều khiển UI, tương tác REST API
│   ├── templates/
│   │   └── index.html             # Giao diện người dùng (Dark Theme, Tailwind CSS)
│   ├── config.py                  # Cấu hình hệ thống & đường dẫn
│   └── main.py                    # Khởi tạo FastAPI application
│
├── data/                          # Dữ liệu & Cơ sở dữ liệu
│   ├── prompts.db                 # SQLite Database chính
│   ├── cleaned_prompts.json       # Tệp JSON đã làm sạch (backup)
│   ├── raw/                       # Dữ liệu Facebook posts gốc
│   └── images/                    # Thư mục lưu trữ ảnh đã tải về máy
│
├── scripts/                       # Các công cụ script chạy độc lập
│   ├── download_images.py         # Script tải toàn bộ ảnh (đa luồng, có resume)
│   ├── migrate_json_to_sqlite.py  # Script import JSON sang SQLite
│   ├── process_prompts.py         # Script làm sạch và bóc tách dữ liệu
│   └── inspect_dataset.py         # Script kiểm tra dataset
│
├── run.py                         # 🚀 File khởi động Web Server: python run.py
├── requirements.txt               # Danh sách thư viện cần thiết
└── README.md                      # Tài liệu hướng dẫn sử dụng
```

---

## 🚀 1. Hướng dẫn cài đặt & Khởi động Web Server

### Bước 1: Cài đặt thư viện (nếu chưa cài)
```bash
pip install -r requirements.txt
```

### Bước 2: Khởi động Web Server
Chỉ cần chạy lệnh:
```bash
python run.py
```
> Trình duyệt sẽ **tự động mở** tại địa chỉ: `http://127.0.0.1:8000`.

**Tùy chọn nâng cao khi chạy server:**
```bash
# Đổi cổng (port)
python run.py --port 8080

# Chế độ phát triển (Auto reload khi sửa code)
python run.py --reload

# Không tự động mở trình duyệt
python run.py --no-browser
```

---

## 🖼️ 2. Hướng dẫn chạy script tải toàn bộ ảnh (Chạy thủ công)

Bạn có thể chạy script `download_images.py` bất cứ khi nào bạn muốn để tải toàn bộ ảnh từ URL về thư mục `data/images/`:

```bash
python scripts/download_images.py
```

### Các tính năng của Script tải ảnh:
- **Tải đa luồng (Multi-threading)**: Mặc định chạy 10 luồng song song giúp tải nhanh chóng.
- **Tính năng Resume**: Tự động bỏ qua các ảnh đã có trên máy và các ảnh đã tải trước đó.
- **Thanh tiến trình trực quan (`tqdm`)**: Hiển thị tốc độ tải, số lượng ảnh hoàn thành.
- **Cập nhật SQLite**: Tự động gán đường dẫn ảnh local vào database. Giao diện Web sẽ tự động ưu tiên load ảnh từ máy thay vì load qua mạng.

**Tùy chọn khi tải ảnh:**
```bash
# Tăng số luồng tải đồng thời lên 15 luồng:
python scripts/download_images.py --workers 15

# Tải thử nghiệm 10 ảnh:
python scripts/download_images.py --limit 10

# Tăng thời gian chờ (timeout) cho mạng chậm:
python scripts/download_images.py --timeout 30

# Bắt buộc tải lại cả những ảnh đã có:
python scripts/download_images.py --force
```

---

## 🛠️ 3. Các Script quản lý dữ liệu khác (Khi cần)

- **Import/Khởi tạo lại cơ sở dữ liệu SQLite từ JSON**:
  ```bash
  python scripts/migrate_json_to_sqlite.py
  ```
- **Làm sạch dữ liệu từ tệp raw**:
  ```bash
  python scripts/process_prompts.py
  ```
- **Kiểm tra phân loại dataset**:
  ```bash
  python scripts/inspect_dataset.py
  ```

---

## ✨ Tính năng nổi bật trên Web App

1. **Giao diện hiện đại Dark Theme**: Tối ưu cho mắt, responsive trên mọi kích thước màn hình.
2. **Bộ lọc & Tìm kiếm tức thì**: Lọc theo các chủ đề chuyên sâu: *Storyboard (12 ô)*, *Chân dung / Góc xinh*, *Video KOC*, *Có ảnh mẫu*,...
3. **Form bóc tách tham số 2 chiều (Dynamic Form)**: Tùy biến trực tiếp các thông số (ánh sáng, phong cách, ống kính, nhân vật, trang phục,...) -> Câu lệnh prompt tự động cập nhật ngay lập tức.
4. **Lưu thay đổi vào SQLite**: Nút *Lưu thay đổi* giúp lưu vĩnh viễn các tùy biến của bạn vào database.
5. **Image Slider & Lightbox Phóng to**: Xem gallery ảnh mẫu độ phân giải cao, hỗ trợ xem full màn hình.
6. **Thêm mới câu lệnh thông minh**: Hỗ trợ thêm Prompt mới chỉ với 2 trường (Link ảnh/video kết quả mẫu & Nội dung Prompt). Hệ thống tự động nhận diện JSON để bóc tách thành Dynamic Form hoặc lưu dạng Text thông thường.
7. **Sao chép 1 chạm**: Sao chép câu lệnh chỉ với 1 click vào bộ nhớ tạm.
