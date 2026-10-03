# -*- coding: utf-8 -*-
"""
Pydantic v2 Schemas for AI Prompt Studio API
Cung cấp định dạng dữ liệu chuẩn hóa, metadata OpenAPI và ví dụ mẫu cho /docs.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# -------------------------------------------------------------
# Base & Utility Schemas
# -------------------------------------------------------------

class StatusResponse(BaseModel):
    status: str = Field("ok", description="Trạng thái phản hồi", json_schema_extra={"example": "ok"})
    message: Optional[str] = Field(None, description="Thông điệp chi tiết", json_schema_extra={"example": "Thao tác thành công"})


class HealthResponse(BaseModel):
    status: str = Field("ok", description="Trạng thái hệ thống", json_schema_extra={"example": "ok"})
    app: str = Field("AI Prompt Studio", description="Tên ứng dụng", json_schema_extra={"example": "AI Prompt Studio"})
    version: str = Field("1.1.0", description="Phiên bản API hiện tại", json_schema_extra={"example": "1.1.0"})


# -------------------------------------------------------------
# Prompt Request Schemas
# -------------------------------------------------------------

class CreatePromptRequest(BaseModel):
    prompt: Optional[str] = Field("", description="Nội dung câu lệnh (JSON hoặc Text thuần)", json_schema_extra={"example": "A photorealistic portrait of an East Asian woman..."})
    title: Optional[str] = Field(None, description="Tiêu đề câu lệnh tùy chỉnh", json_schema_extra={"example": "Chân dung KOC AI phong cách Studio"})
    media: Optional[str] = Field(None, description="URL hoặc đường dẫn ảnh/video kết quả mẫu", json_schema_extra={"example": "https://example.com/sample.jpg"})
    images: Optional[List[str]] = Field(None, description="Danh sách URL hoặc Base64 ảnh tải lên từ máy tính")
    category: Optional[str] = Field("image", description="Loại prompt: 'image', 'video' hoặc 'content'", json_schema_extra={"example": "image"})
    note: Optional[str] = Field("", description="Ghi chú / chú thích cho câu lệnh", json_schema_extra={"example": "Sử dụng cho chiến dịch thời trang xuân hè"})
    sample_content: Optional[str] = Field(None, description="Nội dung kết quả mẫu dạng văn bản", json_schema_extra={"example": "Tiêu đề bài viết: 5 cách phối đồ..."})
    requires_reference: Optional[bool] = Field(None, description="Cờ yêu cầu ảnh tham chiếu khuôn mặt", json_schema_extra={"example": True})
    scenes: Optional[List[Dict[str, str]]] = Field(None, description="Danh sách phân cảnh video (dialogue, action, camera)")


class UpdatePromptRequest(BaseModel):
    title: Optional[str] = Field(None, description="Tiêu đề mới của câu lệnh", json_schema_extra={"example": "Tiêu đề cập nhật mới"})
    prompt_code: Optional[str] = Field(None, description="Nội dung mã prompt tùy biến mới")
    note: Optional[str] = Field(None, description="Ghi chú cập nhật", json_schema_extra={"example": "Ghi chú mới cho câu lệnh"})
    category: Optional[str] = Field(None, description="Danh mục mới: 'image', 'video', 'content'", json_schema_extra={"example": "video"})
    requires_reference: Optional[bool] = Field(None, description="Cờ bật/tắt yêu cầu ảnh tham chiếu", json_schema_extra={"example": False})
    fields: Optional[List[Dict[str, Any]]] = Field(None, description="Danh sách các thuộc tính tùy biến đã chỉnh sửa")


class SetPrimaryFieldRequest(BaseModel):
    is_primary: bool = Field(..., description="Cờ đánh dấu thuộc tính chính (hiển thị trên giao diện thu gọn)", json_schema_extra={"example": True})


class GenerateContentRequest(BaseModel):
    prompt: str = Field(..., description="Nội dung câu lệnh prompt", json_schema_extra={"example": "Viết kịch bản video TikTok 30 giây review son môi"})
    extra_instruction: Optional[str] = Field(None, description="Yêu cầu bổ sung cho AI", json_schema_extra={"example": "Giọng điệu hài hước, tự nhiên"})
    provider: Optional[str] = Field(None, description="Nhà cung cấp AI (mặc định cấu hình hệ thống)", json_schema_extra={"example": "openai"})


class AddSampleContentRequest(BaseModel):
    content: str = Field(..., description="Nội dung văn bản mẫu đính kèm", json_schema_extra={"example": "Kịch bản mẫu hoàn chỉnh..."})
    title: Optional[str] = Field("", description="Tiêu đề mẫu tùy chọn", json_schema_extra={"example": "Kịch bản TikTok số 1"})


class ReorderSampleContentsRequest(BaseModel):
    ordered_ids: List[int] = Field(..., description="Danh sách ID mẫu theo thứ tự hiển thị mới", json_schema_extra={"example": [3, 1, 2]})


class ImprovePromptRequest(BaseModel):
    instruction: str = Field(..., description="Yêu cầu cải tiến hoặc sửa đổi từ người dùng", json_schema_extra={"example": "Thêm chi tiết ánh sáng cinematic và góc máy góc thấp"})
    provider: Optional[str] = Field(None, description="Nhà cung cấp AI", json_schema_extra={"example": "openai"})
    auto_save: Optional[bool] = Field(False, description="Tự động lưu đè vào bản ghi sau khi sinh thành công", json_schema_extra={"example": False})


class SaveImprovedPromptRequest(BaseModel):
    mode: str = Field("overwrite", description="Chế độ lưu: 'overwrite' (ghi đè) hoặc 'new_version' (tạo bản ghi mới)", json_schema_extra={"example": "overwrite"})
    title: Optional[str] = Field(None, description="Tiêu đề câu lệnh mới", json_schema_extra={"example": "KOC Studio - Phiên bản cải tiến"})
    prompt_code: str = Field(..., description="Nội dung câu lệnh prompt mới", json_schema_extra={"example": "{...}"})
    raw_content: Optional[str] = Field(None, description="Nội dung văn bản gốc")
    prompt_type: Optional[str] = Field("json", description="Loại câu lệnh: 'json' hoặc 'text'", json_schema_extra={"example": "json"})
    parsed_json: Optional[Dict[str, Any]] = Field(None, description="Cấu trúc JSON đã phân tích")
    fields: Optional[List[Dict[str, Any]]] = Field(None, description="Danh sách trường tùy biến mới")


class ExtractJsonFromImageRequest(BaseModel):
    image: str = Field(..., description="Base64 data URI hoặc URL của ảnh cần trích xuất VisionStruct", json_schema_extra={"example": "data:image/jpeg;base64,..."})
    provider: Optional[str] = Field(None, description="Nhà cung cấp AI", json_schema_extra={"example": "openai"})


class GenerateImageRequest(BaseModel):
    prompt: str = Field(..., description="Nội dung câu lệnh tạo ảnh", json_schema_extra={"example": "A stylish portrait of an Asian model in neon street"})
    model: Optional[str] = Field(None, description="Tên mô hình AI tạo ảnh", json_schema_extra={"example": "dall-e-3"})
    reference_image: Optional[str] = Field(None, description="Chuỗi Base64 hoặc URL ảnh tham chiếu")
    extra_description: Optional[str] = Field(None, description="Mô tả phụ bổ sung")
    size: Optional[str] = Field("1024x1024", description="Kích thước ảnh đầu ra", json_schema_extra={"example": "1024x1024"})
    quality: Optional[str] = Field("hd", description="Chất lượng ảnh: 'standard' hoặc 'hd'", json_schema_extra={"example": "hd"})
    image_detail: Optional[str] = Field("high", description="Mức độ bám sát ảnh mẫu: 'low', 'high'", json_schema_extra={"example": "high"})
    provider: Optional[str] = Field(None, description="Nhà cung cấp dịch vụ AI", json_schema_extra={"example": "openai"})


class GenerateVideoRequest(BaseModel):
    prompt: str = Field(..., description="Nội dung câu lệnh render video cảnh này", json_schema_extra={"example": "Slow pan across the studio..."})
    model: Optional[str] = Field(None, description="Tên mô hình AI tạo video", json_schema_extra={"example": "kling-v1"})
    ratio: Optional[str] = Field("9:16", description="Tỷ lệ khung hình: '9:16' hoặc '16:9'", json_schema_extra={"example": "9:16"})
    duration: Optional[int] = Field(6, description="Thời lượng cảnh tính bằng giây: 4, 6, 8, 10", json_schema_extra={"example": 6})
    reference_media: Optional[str] = Field(None, description="Ảnh hoặc video tham chiếu")
    scene_number: Optional[int] = Field(None, description="Số thứ tự cảnh", json_schema_extra={"example": 1})
    provider: Optional[str] = Field(None, description="Nhà cung cấp video AI")


class UploadReferenceImageRequest(BaseModel):
    image: str = Field(..., description="Ảnh tham chiếu dạng base64 data URI hoặc đường dẫn tệp", json_schema_extra={"example": "data:image/png;base64,..."})
    is_koc: Optional[bool] = Field(False, description="Đánh dấu ảnh được chọn từ danh mục KOC", json_schema_extra={"example": False})


class SaveKocGalleryRequest(BaseModel):
    image: str = Field(..., description="Dữ liệu ảnh base64 hoặc URL ảnh", json_schema_extra={"example": "data:image/png;base64,..."})
    koc_name: Optional[str] = Field("", description="Tên nhân vật KOC", json_schema_extra={"example": "Thu Trang"})
    ref_path: Optional[str] = Field(None, description="Đường dẫn tệp tham chiếu để lưu cùng thư mục", json_schema_extra={"example": "Thu Trang/ref.png"})
    prompt_id: Optional[str] = Field(None, description="ID bản ghi prompt liên quan", json_schema_extra={"example": "prompt_1"})


class S3UploadRequest(BaseModel):
    data: Optional[str] = Field(None, description="Base64 data URI hoặc text nội dung", json_schema_extra={"example": "data:image/png;base64,..."})
    filename: Optional[str] = Field(None, description="Tên tệp gốc mong muốn", json_schema_extra={"example": "generated_image.png"})
    mime: Optional[str] = Field(None, description="MIME type của tệp", json_schema_extra={"example": "image/png"})
    prefix: Optional[str] = Field(None, description="S3 prefix tùy chọn", json_schema_extra={"example": "ai_prompts_database"})


class SaveGeneratedImageRequest(BaseModel):
    image_data: str = Field(..., description="URL hoặc Base64 ảnh đã tạo", json_schema_extra={"example": "data:image/jpeg;base64,..."})


class AddImagesRequest(BaseModel):
    images: Optional[List[str]] = Field(default_factory=list, description="Danh sách Base64 ảnh hoặc URLs đính kèm")
    media: Optional[str] = Field(None, description="Chuỗi URLs phân cách bằng dấu phẩy hoặc xuống dòng")


class ReorderImagesRequest(BaseModel):
    image_ids: List[int] = Field(..., description="Danh sách ID ảnh theo thứ tự hiển thị mới", json_schema_extra={"example": [2, 1, 3]})


class DeleteImageRequest(BaseModel):
    image_id: Optional[int] = Field(None, description="ID ảnh cần xóa khỏi bản ghi", json_schema_extra={"example": 10})


class AddTagRequest(BaseModel):
    tag: str = Field(..., min_length=1, max_length=50, description="Tên thẻ tag cần gán", json_schema_extra={"example": "KOC"})


class AssistantChatRequest(BaseModel):
    message: str = Field(..., description="Nội dung câu hỏi hoặc yêu cầu tìm kiếm của người dùng", json_schema_extra={"example": "Tìm các prompt tạo dáng ngoại cảnh quán cafe"})
    history: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Lịch sử tin nhắn gần nhất")
    category: Optional[str] = Field("all", description="Bộ lọc danh mục: 'all', 'image' hoặc 'content'", json_schema_extra={"example": "all"})
    provider: Optional[str] = Field(None, description="Nhà cung cấp AI", json_schema_extra={"example": "openai"})


class CompactPromptRequest(BaseModel):
    prompt: Optional[str] = Field(None, description="Tùy chọn: câu lệnh tùy biến cần rút gọn")
    force_refresh: Optional[bool] = Field(False, description="Bắt buộc gọi AI sinh lại kể cả khi đã có trong DB", json_schema_extra={"example": False})


# -------------------------------------------------------------
# Response Schemas
# -------------------------------------------------------------

class PromptItem(BaseModel):
    id: str = Field(..., description="Mã định danh duy nhất của prompt", json_schema_extra={"example": "prompt_1"})
    title: Optional[str] = Field(None, description="Tiêu đề câu lệnh", json_schema_extra={"example": "Bảng phân cảnh góc máy và tạo dáng studio"})
    category: Optional[str] = Field("image", description="Danh mục câu lệnh: 'image', 'video', 'content'", json_schema_extra={"example": "image"})
    prompt_type: Optional[str] = Field("json", description="Định dạng prompt: 'json', 'text', 'video'", json_schema_extra={"example": "json"})
    raw_content: Optional[str] = Field(None, description="Nội dung văn bản câu lệnh gốc")
    prompt_code: Optional[str] = Field(None, description="Nội dung mã câu lệnh có thể chỉnh sửa")
    compact_prompt: Optional[str] = Field(None, description="Phiên bản câu lệnh rút gọn")
    note: Optional[str] = Field(None, description="Ghi chú người dùng")
    requires_reference: Optional[int] = Field(0, description="Cờ yêu cầu ảnh tham chiếu (0 hoặc 1)")
    image_count: int = Field(0, description="Số lượng ảnh mẫu đính kèm", json_schema_extra={"example": 2})
    sample_count: int = Field(0, description="Số lượng kết quả mẫu văn bản", json_schema_extra={"example": 1})
    tags: Optional[List[str]] = Field(default_factory=list, description="Danh sách các thẻ tag đính kèm", json_schema_extra={"example": ["KOC", "Studio"]})


class PromptListResponse(BaseModel):
    count: int = Field(..., description="Số lượng kết quả trả về", json_schema_extra={"example": 20})
    tag: str = Field("all", description="Bộ lọc tag đang áp dụng", json_schema_extra={"example": "all"})
    category: str = Field("image", description="Bộ lọc danh mục đang áp dụng", json_schema_extra={"example": "image"})
    query: Optional[str] = Field(None, description="Từ khóa tìm kiếm đang áp dụng", json_schema_extra={"example": "studio"})
    items: List[Dict[str, Any]] = Field(..., description="Danh sách các bản ghi prompt")


class StatsResponse(BaseModel):
    total_prompts: int = Field(..., description="Tổng số prompt trong cơ sở dữ liệu", json_schema_extra={"example": 442})
    total_images: int = Field(..., description="Tổng số ảnh đính kèm", json_schema_extra={"example": 381})
    downloaded_images: int = Field(..., description="Số ảnh đã lưu trữ cục bộ thành công", json_schema_extra={"example": 381})
    pending_images: int = Field(..., description="Số ảnh đang chờ tải xuống", json_schema_extra={"example": 0})
    failed_images: int = Field(..., description="Số ảnh tải xuống thất bại", json_schema_extra={"example": 0})
    by_type: Dict[str, int] = Field(..., description="Thống kê theo loại prompt (json, text, ...)")
    by_category: Dict[str, int] = Field(..., description="Thống kê theo danh mục (image, video, content)")


class TagItem(BaseModel):
    tag: str = Field(..., description="Tên thẻ tag", json_schema_extra={"example": "KOC"})
    count: int = Field(..., description="Số lượng prompt gắn thẻ này", json_schema_extra={"example": 330})


class TagListResponse(BaseModel):
    tags: List[Dict[str, Any]] = Field(..., description="Danh sách các thẻ tag kèm tần suất")
