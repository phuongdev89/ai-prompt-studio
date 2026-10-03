# AI Prompt Studio - API Reference Documentation

Tài liệu đặc tả toàn diện toàn bộ danh mục REST API của hệ thống **AI Prompt Studio** (FastAPI v1.1.0).

---

## 📑 Mục lục
1. [Tổng quan, Chuẩn kết nối & Mã trạng thái](#1-tổng-quan-chuẩn-kết-nối--mã-trạng-thái)
2. [Quản lý Prompt (`/api/prompts`)](#2-quản-lý-prompt-apiprompts)
3. [Quản lý Thuộc tính & Content Mẫu (`/api/prompts/{id}/...`)](#3-quản-lý-thuộc-tính--content-mẫu)
4. [Dịch vụ Trí tuệ Nhân tạo - AI Generation (`/api/prompts/{id}/...`, `/api/ai`)](#4-dịch-vụ-trí-tuệ-nhân-tạo---ai-generation)
5. [Tài nguyên Đa phương tiện, KOC & S3 Cloud Storage](#5-tài-nguyên-đa-phương-tiện-koc--s3-cloud-storage)
6. [Quản lý Thẻ Tags & Trợ lý Tìm kiếm (`/api/tags`, `/api/assistant`)](#6-quản-lý-thẻ-tags--trợ-lý-tìm-kiếm)
7. [Hệ thống, Cấu hình & Đồng bộ (`/api/config`, `/api/stats`, `/api/sync`)](#7-hệ-thống-cấu-hình--đồng-bộ)

---

## 1. Tổng quan, Chuẩn kết nối & Mã trạng thái

- **Base URL:** `http://127.0.0.1:8000/api`
- **Tài liệu trực quan tương tác:**
  - API Documentation Hub: `http://127.0.0.1:8000/docs/api`
  - Swagger UI: `http://127.0.0.1:8000/docs/api/swagger` (hoặc `/docs`)
  - ReDoc: `http://127.0.0.1:8000/docs/api/redoc` (hoặc `/redoc`)
  - OpenAPI Specification (JSON): `http://127.0.0.1:8000/docs/api/openapi.json` (hoặc `/openapi.json`)
  - Bộ tệp tài liệu tĩnh đặt tại: `docs/api/` (`index.html`, `swagger.html`, `redoc.html`, `openapi.json`)
- **Định dạng dữ liệu:** `application/json; charset=utf-8`
- **Mã phản hồi chuẩn (HTTP Status Codes):**
  - `200 OK`: Thao tác thành công.
  - `400 Bad Request`: Tham số không hợp lệ, nội dung bắt buộc bị để trống.
  - `404 Not Found`: Không tìm thấy bản ghi prompt hoặc tài nguyên yêu cầu.
  - `500 Internal Server Error`: Lỗi xử lý máy chủ hoặc lỗi kết nối dịch vụ ngoài (AI/S3).

---

## 2. Quản lý Prompt (`/api/prompts`)

### 2.1. Tra cứu danh sách Prompts
- **Endpoint:** `GET /api/prompts`
- **Query Parameters:**
  - `q` (string, tùy chọn): Từ khóa tìm kiếm (hỗ trợ tiếng Việt không dấu/có dấu).
  - `tag` (string, mặc định: `all`): Bộ lọc tag (`all`, `has_img`, `no_img`, `has_sample`, `storyboard`, `portrait`, `video`, `seo`, `live`, `json`, `text` hoặc tên tag cụ thể).
  - `category` (string, mặc định: `image`): Danh mục (`image`, `video`, `content`).
  - `limit` (integer, tùy chọn): Giới hạn số lượng bản ghi trả về.
  - `offset` (integer, mặc định: `0`): Vị trí bắt đầu truy vấn.
- **Response (200 OK):**
```json
{
  "count": 2,
  "tag": "all",
  "category": "image",
  "query": null,
  "items": [
    {
      "id": "prompt_1",
      "original_index": 0,
      "title": "Bảng phân cảnh góc máy và tạo dáng studio",
      "raw_title": "Câu lệnh KOC AI - góc xinh xinh",
      "prompt_type": "json",
      "category": "image",
      "image_count": 2,
      "sample_count": 1,
      "tags": ["KOC", "Studio", "Storyboard"],
      "created_at": "2026-09-08 12:00:00"
    }
  ]
}
```

### 2.2. Tạo mới Prompt
- **Endpoint:** `POST /api/prompts`
- **Request Body (JSON):**
```json
{
  "prompt": "A photorealistic portrait of an East Asian woman in studio...",
  "title": "Chân dung KOC AI Studio",
  "category": "image",
  "note": "Áp dụng chiến dịch xuân hè",
  "media": "https://example.com/sample.jpg",
  "requires_reference": true,
  "sample_content": "Kịch bản mẫu giới thiệu sản phẩm"
}
```
- **Response (200 OK):** Trả về bản ghi prompt vừa tạo kèm ID sinh tự động (`prompt_xxx`).

### 2.3. Xem chi tiết Prompt theo ID
- **Endpoint:** `GET /api/prompts/{prompt_id}`
- **Path Parameter:** `prompt_id` (ví dụ: `prompt_1`).
- **Response (200 OK):** Trả về toàn bộ trường dữ liệu: cấu trúc JSON bóc tách (`parsed_json`), danh sách thuộc tính tùy biến (`fields`), danh sách ảnh đính kèm (`images`), văn bản mẫu (`sample_contents`), và prompt rút gọn (`compact_prompt`).

### 2.4. Cập nhật thông tin Prompt
- **Endpoint:** `PUT /api/prompts/{prompt_id}` (hoặc `PATCH /api/prompts/{prompt_id}`)
- **Request Body:**
```json
{
  "title": "Tiêu đề mới",
  "note": "Ghi chú đã cập nhật",
  "category": "video",
  "requires_reference": false
}
```

### 2.5. Thay đổi danh mục Prompt
- **Endpoint:** `POST /api/prompts/{prompt_id}/category`
- **Request Body:** `{"category": "video"}` (chấp nhận: `image`, `video`, `content`).

### 2.6. Bật/Tắt cờ yêu cầu ảnh tham chiếu
- **Endpoint:** `POST /api/prompts/{prompt_id}/toggle-reference`
- **Response (200 OK):** `{"status": "success", "requires_reference": true}`.

### 2.7. Xóa Prompt
- **Endpoint:** `DELETE /api/prompts/{prompt_id}`
- **Response (200 OK):** `{"status": "success", "message": "Đã xóa prompt thành công"}`.

---

## 3. Quản lý Thuộc tính & Content Mẫu

### 3.1. Đánh dấu thuộc tính chính (Primary Field)
- **Endpoint:** `POST /api/prompts/{prompt_id}/fields/{field_id}/primary`
- **Request Body:** `{"is_primary": true}`

### 3.2. Gợi ý thuộc tính chính tự động bằng AI
- **Endpoint:** `POST /api/prompts/{prompt_id}/suggest-primary-fields`
- **Mô tả:** Tự động phân tích cấu trúc prompt và chọn ra 3-5 thuộc tính quan trọng nhất để đưa lên giao diện tùy biến nhanh.

### 3.3. Thêm nội dung mẫu văn bản (Sample Content)
- **Endpoint:** `POST /api/prompts/{prompt_id}/sample-contents`
- **Request Body:**
```json
{
  "title": "Kịch bản TikTok 30s",
  "content": "Nội dung kịch bản hoàn chỉnh..."
}
```

### 3.4. Xóa / Sắp xếp lại thứ tự Content Mẫu
- `DELETE /api/prompts/{prompt_id}/sample-contents/{content_id}`
- `POST /api/prompts/{prompt_id}/sample-contents/reorder` với `{"ordered_ids": [3, 1, 2]}`.

---

## 4. Dịch vụ Trí tuệ Nhân tạo - AI Generation

### 4.1. Sinh nội dung văn bản dựa trên Prompt
- **Endpoint:** `POST /api/prompts/{prompt_id}/generate-content`
- **Request Body:**
```json
{
  "prompt": "Viết kịch bản video review tai nghe chống ồn",
  "extra_instruction": "Giọng kể tự nhiên, nêu bật độ êm và pin 40h",
  "provider": "openai"
}
```

### 4.2. Rút gọn Prompt tự động (Compact Prompt)
- **Endpoint:** `POST /api/prompts/{prompt_id}/compact`
- **Request Body:** `{"force_refresh": false}`
- **Response:** `{"status": "success", "compact_prompt": "..."}`.

### 4.3. Cải tiến và tối ưu hóa Prompt (Improve Prompt)
- **Endpoint:** `POST /api/prompts/{prompt_id}/improve`
- **Request Body:**
```json
{
  "instruction": "Bổ sung hiệu ứng ánh sáng hoàng hôn golden hour và chi tiết sợi vải",
  "auto_save": false
}
```

### 4.4. Lưu phiên bản cải tiến (Overwrite hoặc Versioning)
- **Endpoint:** `POST /api/prompts/{prompt_id}/save-improved`
- **Request Body:**
```json
{
  "mode": "overwrite",
  "prompt_code": "{...}",
  "title": "Prompt Studio - Cải tiến"
}
```
*Ghi chú: Chế độ `new_version` sẽ tạo bản ghi mới kế thừa, không ghi đè bản gốc.*

### 4.5. Tạo ảnh AI (AI Image Generation)
- **Endpoint:** `POST /api/prompts/{prompt_id}/generate-image`
- **Request Body:**
```json
{
  "prompt": "Chân dung KOC nữ mỉm cười tự nhiên trong quán cà phê",
  "model": "dall-e-3",
  "size": "1024x1024",
  "quality": "hd",
  "reference_image": "data:image/jpeg;base64,..."
}
```

### 4.6. Trích xuất VisionStruct JSON từ hình ảnh
- **Endpoint:** `POST /api/prompts/{prompt_id}/extract-json-from-image`
- **Endpoint tự do:** `POST /api/prompts/extract-json-from-uploaded-image`
- **Mô tả:** Phân tích ảnh tải lên để trích xuất đầy đủ đặc điểm nhận dạng khuôn mặt, trang phục, góc máy, ánh sáng thành cấu trúc JSON chuẩn.

---

## 5. Tài nguyên Đa phương tiện, KOC & S3 Cloud Storage

### 5.1. Thư viện nhân vật KOC AI
- `GET /api/koc/list`: Danh sách nhân vật kèm số lượng ảnh và ảnh thumbnail cover.
- `GET /api/koc/images?name={koc_name}`: Danh sách toàn bộ ảnh tham chiếu của nhân vật.
- `GET /api/koc/image?path={file_path}`: Stream tệp ảnh cục bộ an toàn.
- `POST /api/koc/gallery/save`: Lưu ảnh AI đã sinh vào thư mục nhân vật KOC.

### 5.2. Quản lý ảnh đính kèm Prompt
- `POST /api/prompts/{prompt_id}/add-images`: Thêm ảnh qua URL hoặc Base64.
- `POST /api/prompts/{prompt_id}/reorder-images`: Sắp xếp lại thứ tự ưu tiên ảnh mẫu.
- `DELETE /api/prompts/{prompt_id}/images/{image_id}`: Xóa ảnh khỏi bản ghi.

### 5.3. Tích hợp S3 Cloud Storage
- `POST /api/s3/upload`: Tải tệp nhị phân hoặc Base64 lên S3 Bucket.
- `GET /api/s3/presign?url={s3_url}`: Lấy Presigned URL có thời hạn truy cập.
- `GET /api/media/proxy?url={url}`: Proxy stream hình ảnh hỗ trợ CORS.

---

## 6. Quản lý Thẻ Tags & Trợ lý Tìm kiếm

### 6.1. Danh mục Thẻ Tags
- `GET /api/tags`: Danh sách toàn bộ thẻ tags kèm tần suất xuất hiện.
- `GET /api/prompts/{prompt_id}/tags`: Danh sách thẻ tags của 1 prompt cụ thể.
- `POST /api/prompts/{prompt_id}/tags`: Gán thêm tag cho prompt (`{"tag": "TikTok"}`).
- `DELETE /api/prompts/{prompt_id}/tags/{tag_name}`: Gỡ bỏ thẻ tag.

### 6.2. Trợ lý AI Tìm kiếm (Semantic Search Assistant)
- `POST /api/assistant/chat`: Trò chuyện và tìm kiếm prompt phù hợp qua ngôn ngữ tự nhiên.
- `GET /api/assistant/suggestions`: Danh sách câu hỏi gợi ý nhanh.

---

## 7. Hệ thống, Cấu hình & Đồng bộ

### 7.1. Thống kê & Kiểm tra Sức khỏe
- `GET /health`: Trả về `{"status": "ok", "app": "AI Prompt Studio"}`.
- `GET /api/stats`: Thống kê tổng số prompt, số ảnh, phân bố theo danh mục/loại.

### 7.2. Cấu hình Hệ thống
- `GET /api/config`: Đọc cấu hình hiện tại (đã ẩn các khóa bí mật).
- `POST /api/config`: Cập nhật cấu hình và lưu vào `.env`.
- `GET /api/config/providers`: Danh sách nhà cung cấp AI và mô hình đang khả dụng.
- `GET /api/ai/ping`: Kiểm tra kết nối tới AI Provider API.
- `POST /api/db/backup`: Tạo bản sao lưu SQLite Database vào thư mục `backups/`.
