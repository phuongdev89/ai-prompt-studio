from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from app.db.repository import PromptRepository
from app.services.parser import parse_incoming_prompt
from app.services.downloader import download_prompt_images_now

router = APIRouter(prefix="/api", tags=["prompts"])

class CreatePromptRequest(BaseModel):
    prompt: str = Field(..., description="Nội dung câu lệnh (JSON hoặc Text)")
    media: Optional[str] = Field(None, description="URL hoặc đường dẫn ảnh/video kết quả mẫu")
    images: Optional[List[str]] = Field(None, description="Danh sách URL hoặc Base64 ảnh tải lên từ máy tính")
    category: Optional[str] = Field("character", description="Loại prompt: 'character' hoặc 'content'")
    note: Optional[str] = Field("", description="Ghi chú / chú thích cho câu lệnh")
    sample_content: Optional[str] = Field(None, description="Nội dung kết quả mẫu dạng văn bản")

class SetPrimaryFieldRequest(BaseModel):
    is_primary: bool = Field(..., description="Cờ đánh dấu thuộc tính chính")

class GenerateContentRequest(BaseModel):
    prompt: str = Field(..., description="Nội dung câu lệnh prompt")
    extra_instruction: Optional[str] = Field(None, description="Yêu cầu bổ sung cho AI")
    provider: Optional[str] = Field(None, description="Nhà cung cấp: 'openai' hoặc 'gemini'")

class AddSampleContentRequest(BaseModel):
    content: str = Field(..., description="Nội dung văn bản mẫu")
    title: Optional[str] = Field("", description="Tiêu đề mẫu (tùy chọn)")

class UpdatePromptRequest(BaseModel):
    title: Optional[str] = None
    prompt_code: Optional[str] = None
    note: Optional[str] = None
    fields: Optional[List[Dict[str, Any]]] = None

class ImprovePromptRequest(BaseModel):
    instruction: str = Field(..., description="Yêu cầu cải tiến của người dùng")
    provider: Optional[str] = Field(None, description="Nhà cung cấp AI: 'openai' hoặc 'gemini'")

class SaveImprovedPromptRequest(BaseModel):
    mode: str = Field("overwrite", description="Chế độ lưu: 'overwrite' hoặc 'new_version'")
    title: Optional[str] = None
    prompt_code: str = Field(..., description="Nội dung câu lệnh prompt mới")
    raw_content: Optional[str] = None
    prompt_type: Optional[str] = "json"
    parsed_json: Optional[Dict[str, Any]] = None
    fields: Optional[List[Dict[str, Any]]] = None

class GenerateImageRequest(BaseModel):
    prompt: str = Field(..., description="Nội dung câu lệnh tạo ảnh")
    reference_image: Optional[str] = Field(None, description="Chuỗi Base64 hoặc URL ảnh tham chiếu")
    extra_description: Optional[str] = Field(None, description="Mô tả phụ bổ sung")
    size: Optional[str] = Field("1024x1024", description="Kích thước ảnh")
    quality: Optional[str] = Field("hd", description="Chất lượng ảnh")
    image_detail: Optional[str] = Field("high", description="Mức độ bám sát chi tiết ảnh tham chiếu")
    provider: Optional[str] = Field(None, description="Nhà cung cấp: 'openai' hoặc 'gemini'")

class SaveGeneratedImageRequest(BaseModel):
    image_data: str = Field(..., description="URL hoặc Base64 ảnh đã tạo")

class AddImagesRequest(BaseModel):
    images: Optional[List[str]] = Field(default_factory=list, description="Danh sách Base64 ảnh hoặc URLs")
    media: Optional[str] = Field(None, description="Chuỗi URLs phân cách bằng dấu phẩy hoặc xuống dòng")

class ReorderImagesRequest(BaseModel):
    image_ids: List[int] = Field(..., description="Danh sách ID ảnh theo thứ tự mới")

class DeleteImageRequest(BaseModel):
    image_id: Optional[int] = Field(None, description="ID ảnh cần xóa")

class AddTagRequest(BaseModel):
    tag: str = Field(..., min_length=1, max_length=50, description="Tên thẻ tag cần thêm")

@router.get("/prompts")
@router.get("/prompts/")
def list_prompts(
    q: Optional[str] = Query(None, description="Search keyword"),
    tag: str = Query("all", description="Tag filter: all, has_img, has_sample, storyboard, portrait, video, seo, live"),
    category: Optional[str] = Query("character", description="Filter by category: 'character' or 'content'"),
    limit: Optional[int] = Query(None, description="Limit results"),
    offset: int = Query(0, description="Offset results")
):
    query_val = q if isinstance(q, str) else None
    tag_val = tag if isinstance(tag, str) else "all"
    cat_val = category if isinstance(category, str) else "character"
    limit_val = limit if isinstance(limit, int) else None
    offset_val = offset if isinstance(offset, int) else 0

    prompts = PromptRepository.get_prompts(query=query_val, tag=tag_val, category=cat_val, limit=limit_val, offset=offset_val)
    return {
        "count": len(prompts),
        "tag": tag_val,
        "category": cat_val,
        "query": query_val,
        "items": prompts
    }

@router.post("/prompts")
@router.post("/prompts/")
def create_prompt(payload: CreatePromptRequest):
    import re
    if not payload.prompt or not payload.prompt.strip():
        raise HTTPException(status_code=400, detail="Nội dung prompt không được để trống")

    # Combine images from payload.media and payload.images
    media_list = []
    if payload.media and payload.media.strip():
        lines = re.split(r'[\r\n,]+', payload.media.strip())
        for l in lines:
            cleaned = l.strip()
            if cleaned:
                media_list.append(cleaned)

    if payload.images:
        for img in payload.images:
            if isinstance(img, str) and img.strip():
                media_list.append(img.strip())

    parsed_data = parse_incoming_prompt(
        raw_content=payload.prompt,
        raw_media=None
    )
    parsed_data["images"] = media_list
    parsed_data["category"] = payload.category or "character"
    parsed_data["note"] = payload.note or ""
    parsed_data["sample_content"] = payload.sample_content

    created_item = PromptRepository.create_prompt(parsed_data)

    # Immediately download any attached pending HTTP images or videos to local storage
    if created_item and created_item.get("images"):
        has_pending = any(img.get("status") == "pending" for img in created_item["images"] if isinstance(img, dict))
        if has_pending:
            try:
                download_prompt_images_now(created_item["id"])
                # Refresh prompt detail after download
                refreshed = PromptRepository.get_prompt_by_id(created_item["id"])
                if refreshed:
                    created_item = refreshed
            except Exception as e:
                print(f"[!] Warning: Immediate media download failed: {e}")

    return created_item

@router.get("/prompts/{prompt_id}")
@router.get("/prompts/{prompt_id}/")
def get_prompt(prompt_id: str):
    prompt = PromptRepository.get_prompt_by_id(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return prompt

# Support PUT, POST, and PATCH for updating prompt title & note
@router.put("/prompts/{prompt_id}")
@router.put("/prompts/{prompt_id}/")
@router.post("/prompts/{prompt_id}")
@router.post("/prompts/{prompt_id}/")
@router.patch("/prompts/{prompt_id}")
@router.patch("/prompts/{prompt_id}/")
def update_prompt(prompt_id: str, payload: UpdatePromptRequest):
    prompt = PromptRepository.get_prompt_by_id(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    updated = False
    if payload.title is not None and payload.title.strip():
        PromptRepository.update_prompt_title(prompt_id=prompt_id, title=payload.title.strip())
        updated = True
    if payload.note is not None:
        PromptRepository.update_prompt_note(prompt_id=prompt_id, note=payload.note)
        updated = True

    return {"status": "success", "updated": updated}

@router.delete("/prompts/{prompt_id}")
@router.delete("/prompts/{prompt_id}/")
@router.post("/prompts/{prompt_id}/delete")
def delete_prompt(prompt_id: str):
    prompt = PromptRepository.get_prompt_by_id(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    success = PromptRepository.delete_prompt(prompt_id)
    return {"status": "success", "deleted": success, "id": prompt_id}

@router.post("/prompts/{prompt_id}/fields/{field_id}/primary")
def toggle_field_primary(prompt_id: str, field_id: int, payload: SetPrimaryFieldRequest):
    prompt = PromptRepository.get_prompt_by_id(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt không tồn tại")
    
    success = PromptRepository.update_field_primary(prompt_id, field_id, payload.is_primary)
    if not success:
        raise HTTPException(status_code=400, detail="Không tìm thấy trường thuộc tính để cập nhật")
    
    return {
        "status": "success",
        "prompt_id": prompt_id,
        "field_id": field_id,
        "is_primary": payload.is_primary
    }

@router.post("/prompts/{prompt_id}/generate-content")
def generate_content_for_prompt(prompt_id: str, payload: GenerateContentRequest):
    from app.services.content_generator import call_ai_generate_content
    prompt = PromptRepository.get_prompt_by_id(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt không tồn tại")

    prompt_text = payload.prompt.strip() if payload.prompt else ""
    if not prompt_text:
        prompt_text = prompt.get("prompt_code") or prompt.get("raw_content") or ""
    if not prompt_text.strip():
        raise HTTPException(status_code=400, detail="Nội dung prompt không được để trống")

    success, content, msg = call_ai_generate_content(
        prompt_text=prompt_text,
        provider=payload.provider,
        extra_instruction=payload.extra_instruction
    )
    if not success:
        raise HTTPException(status_code=500, detail=msg)

    return {
        "status": "success",
        "content": content,
        "message": msg,
        "prompt_id": prompt_id
    }

@router.post("/prompts/{prompt_id}/sample-contents")
def add_sample_content_endpoint(prompt_id: str, payload: AddSampleContentRequest):
    prompt = PromptRepository.get_prompt_by_id(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt không tồn tại")
    if not payload.content or not payload.content.strip():
        raise HTTPException(status_code=400, detail="Nội dung content mẫu không được để trống")

    new_sample = PromptRepository.add_sample_content(prompt_id, payload.content.strip(), payload.title or "")
    if not new_sample:
        raise HTTPException(status_code=500, detail="Không thể lưu content mẫu")

    refreshed = PromptRepository.get_prompt_by_id(prompt_id)
    return {
        "status": "success",
        "message": "Đã lưu content này vào kết quả mẫu!",
        "sample": new_sample,
        "prompt": refreshed
    }

@router.delete("/prompts/{prompt_id}/sample-contents/{content_id}")
@router.post("/prompts/{prompt_id}/sample-contents/{content_id}/delete")
def delete_sample_content_endpoint(prompt_id: str, content_id: int):
    prompt = PromptRepository.get_prompt_by_id(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt không tồn tại")

    success = PromptRepository.delete_sample_content(prompt_id, content_id)
    if not success:
        raise HTTPException(status_code=404, detail="Content mẫu không tồn tại")

    refreshed = PromptRepository.get_prompt_by_id(prompt_id)
    return {
        "status": "success",
        "message": "Đã xóa content mẫu thành công!",
        "prompt": refreshed
    }

@router.post("/prompts/{prompt_id}/convert-json")
def convert_prompt_to_json(prompt_id: str):
    import json
    from app.services.ai_converter import call_ai_convert_to_json
    prompt = PromptRepository.get_prompt_by_id(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt không tồn tại")
    
    raw_text = prompt.get("raw_content") or prompt.get("prompt_code") or ""
    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="Không có nội dung để chuyển đổi")

    success, parsed_json, msg = call_ai_convert_to_json(raw_text)
    if not success:
        raise HTTPException(status_code=500, detail=msg)

    prompt_code = json.dumps(parsed_json, indent=2, ensure_ascii=False)
    PromptRepository.update_prompt_json_structure(prompt_id, parsed_json, prompt_code)

    # Return refreshed prompt
    refreshed = PromptRepository.get_prompt_by_id(prompt_id)
    return refreshed

@router.post("/prompts/{prompt_id}/improve")
def improve_prompt_endpoint(prompt_id: str, payload: ImprovePromptRequest):
    from app.services.ai_improver import call_ai_improve_prompt
    prompt = PromptRepository.get_prompt_by_id(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt không tồn tại")

    if not payload.instruction or not payload.instruction.strip():
        raise HTTPException(status_code=400, detail="Vui lòng nhập yêu cầu cải tiến")

    prompt_text = prompt.get("prompt_code") or prompt.get("raw_content") or ""
    if not prompt_text.strip():
        raise HTTPException(status_code=400, detail="Bản ghi prompt không có nội dung để cải tiến")

    success, result, msg = call_ai_improve_prompt(
        original_prompt=prompt_text,
        instructions=payload.instruction.strip(),
        provider=payload.provider,
        original_parsed_json=prompt.get("parsed_json"),
        original_prompt_type=prompt.get("prompt_type"),
        original_title=prompt.get("title")
    )

    if not success:
        raise HTTPException(status_code=500, detail=msg)

    return {
        "status": "success",
        "message": msg,
        "original_prompt_id": prompt_id,
        "title": result.get("title") or prompt.get("title") or "Prompt đã cải tiến",
        "prompt_type": result.get("prompt_type", "json"),
        "prompt_code": result.get("prompt_code", ""),
        "parsed_json": result.get("parsed_json"),
        "fields": result.get("fields", []),
        "explanation": result.get("explanation", ""),
        "changes": result.get("changes", [])
    }

@router.post("/prompts/{prompt_id}/save-improved")
def save_improved_prompt_endpoint(prompt_id: str, payload: SaveImprovedPromptRequest):
    prompt = PromptRepository.get_prompt_by_id(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt gốc không tồn tại")

    if not payload.prompt_code or not payload.prompt_code.strip():
        raise HTTPException(status_code=400, detail="Nội dung prompt không được để trống")

    title = (payload.title or "").strip()
    if not title:
        title = prompt.get("title", "Prompt đã cải tiến")
        if payload.mode == "new_version":
            title = f"{title} (Bản cải tiến)"

    if payload.mode == "new_version":
        saved_prompt = PromptRepository.save_as_new_version(
            parent_prompt_id=prompt_id,
            title=title,
            prompt_code=payload.prompt_code.strip(),
            raw_content=payload.raw_content or payload.prompt_code.strip(),
            prompt_type=payload.prompt_type or "json",
            parsed_json=payload.parsed_json,
            fields=payload.fields
        )
        msg = f"Đã lưu thành phiên bản mới: {title}"
    else:
        saved_prompt = PromptRepository.overwrite_prompt(
            prompt_id=prompt_id,
            title=title,
            prompt_code=payload.prompt_code.strip(),
            raw_content=payload.raw_content or payload.prompt_code.strip(),
            prompt_type=payload.prompt_type or "json",
            parsed_json=payload.parsed_json,
            fields=payload.fields
        )
        msg = f"Đã lưu đè thành công câu lệnh: {title}"

    if not saved_prompt:
        raise HTTPException(status_code=500, detail="Không thể lưu câu lệnh vào CSDL")

    return {
        "status": "success",
        "mode": payload.mode,
        "message": msg,
        "prompt": saved_prompt
    }

@router.post("/prompts/{prompt_id}/suggest-title")
def suggest_prompt_title(prompt_id: str):
    prompt = PromptRepository.get_prompt_by_id(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt không tồn tại")

    prompt_text = prompt.get("prompt_code") or prompt.get("raw_content") or ""
    if not prompt_text.strip():
        raise HTTPException(status_code=400, detail="Prompt không có nội dung để đặt tiêu đề")

    from app.config import get_ai_config
    import urllib.request, json, ssl, re

    cfg = get_ai_config()
    api_key = cfg.get("api_key", "").strip()
    base_url = cfg.get("base_url", "https://api.openai.com/v1").strip()
    model_name = cfg.get("chat_model") or cfg.get("model_name") or "gpt-4o-mini"
    timeout = 60

    system_prompt = (
        "Bạn là một Giám đốc nghệ thuật AI (Art Director) và chuyên gia sáng tạo tiêu đề chuyên nghiệp.\n"
        "Nhiệm vụ: Hãy đặt một tiêu đề ngắn gọn, bắt mắt, cuốn hút và mang tính miêu tả cao cho câu lệnh prompt AI.\n\n"
        "YÊU CẦU BẮT BUỘC:\n"
        "- Ngôn ngữ: 100% TIẾNG VIỆT. Kể cả khi câu lệnh gốc viết hoàn toàn bằng tiếng Anh hay có chứa các thuật ngữ kỹ thuật, bạn PHẢI dịch và tóm lược thành một tiêu đề hoàn toàn bằng tiếng Việt tự nhiên, chuẩn ngữ pháp, lôi cuốn.\n"
        "- Độ dài: Từ 4 đến 10 từ.\n"
        "- Phong cách: Ngắn gọn, súc tích, sang trọng, mang phong cách nghệ thuật/nhiếp ảnh.\n"
        "- Định dạng: CHỈ trả về duy nhất chuỗi tiêu đề tiếng Việt, KHÔNG có ngoặc kép, KHÔNG có dấu chấm cuối câu, KHÔNG có chữ 'Tiêu đề:', KHÔNG có giải thích nào khác."
    )

    user_content = f"Hãy đặt tiêu đề bằng TIẾNG VIỆT cho câu lệnh prompt sau:\n\n{prompt_text[:2000]}"

    new_title = ""
    active_provider = (cfg.get("provider") or "openai").lower()
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        if active_provider == "gemini" and cfg.get("gemini_api_key"):
            gemini_key = cfg.get("gemini_api_key")
            g_model = cfg.get("gemini_chat_model", "gemini-2.0-flash") or "gemini-2.0-flash"
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{g_model}:generateContent?key={gemini_key}"
            payload = {
                "system_instruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": user_content}]}],
                "generationConfig": {"temperature": 0.4}
            }
            req = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                parts = data.get("candidates", [])[0].get("content", {}).get("parts", [])
                if parts:
                    new_title = parts[0].get("text", "").strip()
        else:
            if not api_key:
                raise HTTPException(status_code=500, detail="Chưa cấu hình API Key trong .env")

            endpoint = f"{base_url.rstrip('/')}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                "temperature": 0.4,
                "stream": False
            }
            req = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                choices = data.get("choices", [])
                if choices:
                    new_title = choices[0].get("message", {}).get("content", "").strip()

        # Clean title
        new_title = re.sub(r"^[\"'\s*`]+|[\"'\s*`]+$", "", new_title)
        new_title = re.sub(r"^(?:tiêu đề|title)\s*:\s*", "", new_title, flags=re.IGNORECASE).strip()
        new_title = re.sub(r"^[\"'\s*`]+|[\"'\s*`]+$", "", new_title)

        if not new_title:
            raise HTTPException(status_code=500, detail="Mô hình AI không trả về tiêu đề")

        # Save to database immediately
        PromptRepository.update_prompt_title(prompt_id=prompt_id, title=new_title)

        return {
            "status": "success",
            "prompt_id": prompt_id,
            "title": new_title
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi AI gợi ý tiêu đề: {str(e)}")

@router.post("/prompts/{prompt_id}/generate-image")

def generate_image_for_prompt(prompt_id: str, payload: GenerateImageRequest):
    from app.services.image_generator import call_ai_generate_image
    prompt = PromptRepository.get_prompt_by_id(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt không tồn tại")

    prompt_text = payload.prompt.strip() if payload.prompt else ""
    if not prompt_text:
        prompt_text = prompt.get("prompt_code") or prompt.get("raw_content") or ""

    if not prompt_text.strip():
        raise HTTPException(status_code=400, detail="Câu lệnh prompt không được để trống")

    success, img_result, fmt, msg = call_ai_generate_image(
        prompt_text=prompt_text,
        reference_image=payload.reference_image,
        extra_description=payload.extra_description,
        size=payload.size or "1024x1024",
        quality=payload.quality or "hd",
        image_detail=payload.image_detail or "high",
        provider=payload.provider
    )

    if not success:
        raise HTTPException(status_code=500, detail=msg)

    return {
        "status": "success",
        "image_url": img_result,
        "format": fmt,
        "message": msg,
        "prompt_id": prompt_id
    }

@router.post("/prompts/{prompt_id}/save-generated-image")
def save_generated_image_endpoint(prompt_id: str, payload: SaveGeneratedImageRequest):
    from app.services.image_generator import save_generated_image_to_prompt
    prompt = PromptRepository.get_prompt_by_id(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt không tồn tại")

    if not payload.image_data or not payload.image_data.strip():
        raise HTTPException(status_code=400, detail="Dữ liệu ảnh không được để trống")

    success, filename, msg = save_generated_image_to_prompt(
        prompt_id=prompt_id,
        image_data_or_url=payload.image_data.strip()
    )

    if not success:
        raise HTTPException(status_code=500, detail=msg)

    # Return refreshed prompt with newly added image
    refreshed = PromptRepository.get_prompt_by_id(prompt_id)
    return {
        "status": "success",
        "message": msg,
        "filename": filename,
        "prompt": refreshed
    }

@router.post("/prompts/{prompt_id}/add-images")
def add_images_to_prompt_endpoint(prompt_id: str, payload: AddImagesRequest):
    import re
    prompt = PromptRepository.get_prompt_by_id(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt không tồn tại")

    media_list = []
    if payload.media and payload.media.strip():
        lines = re.split(r'[\r\n,]+', payload.media.strip())
        for l in lines:
            cleaned = l.strip()
            if cleaned:
                media_list.append(cleaned)

    if payload.images:
        for img in payload.images:
            if isinstance(img, str) and img.strip():
                media_list.append(img.strip())

    if not media_list:
        raise HTTPException(status_code=400, detail="Vui lòng tải lên ít nhất 1 ảnh hoặc dán 1 đường link ảnh")

    added_files = PromptRepository.add_multiple_images_to_prompt(prompt_id, media_list)

    # Immediately download any pending URLs
    try:
        download_prompt_images_now(prompt_id)
    except Exception as e:
        print(f"[!] Warning: Immediate media download failed: {e}")

    refreshed = PromptRepository.get_prompt_by_id(prompt_id)
    return {
        "status": "success",
        "message": f"Đã thêm thành công {len(added_files)} ảnh tham chiếu vào câu lệnh!",
        "added_count": len(added_files),
        "prompt": refreshed
    }

@router.post("/prompts/{prompt_id}/reorder-images")
def reorder_prompt_images(prompt_id: str, payload: ReorderImagesRequest):
    prompt = PromptRepository.get_prompt_by_id(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt không tồn tại")

    PromptRepository.reorder_prompt_images(prompt_id, payload.image_ids)
    refreshed = PromptRepository.get_prompt_by_id(prompt_id)
    return {
        "status": "success",
        "message": "Đã cập nhật thứ tự ảnh thành công!",
        "prompt": refreshed
    }

@router.delete("/prompts/{prompt_id}/images/{image_id}")
@router.post("/prompts/{prompt_id}/delete-image")
def delete_prompt_image(prompt_id: str, image_id: Optional[int] = None, payload: Optional[DeleteImageRequest] = None):
    target_img_id = image_id or (payload.image_id if payload else None)
    if not target_img_id:
        raise HTTPException(status_code=400, detail="Thiếu ID ảnh cần xóa")

    prompt = PromptRepository.get_prompt_by_id(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt không tồn tại")

    success = PromptRepository.delete_prompt_image(prompt_id, target_img_id)
    if not success:
        raise HTTPException(status_code=404, detail="Ảnh không tồn tại hoặc đã bị xóa")

    refreshed = PromptRepository.get_prompt_by_id(prompt_id)
    return {
        "status": "success",
        "message": "Đã xóa ảnh khỏi câu lệnh thành công!",
        "prompt": refreshed
    }

@router.get("/stats")
@router.get("/stats/")
def get_stats():
    return PromptRepository.get_stats()

@router.get("/config/providers")
@router.get("/config/providers/")
def get_providers_config():
    from app.config import get_ai_config
    cfg = get_ai_config()
    return {
        "active_provider": cfg.get("provider", "openai"),
        "openai": {
            "has_key": bool(cfg.get("api_key")),
            "base_url": cfg.get("base_url"),
            "chat_model": cfg.get("chat_model"),
            "image_model": cfg.get("image_model")
        },
        "gemini": {
            "has_key": bool(cfg.get("gemini_api_key")),
            "chat_model": cfg.get("gemini_chat_model", "gemini-2.0-flash"),
            "image_model": cfg.get("gemini_image_model", "imagen-3.0-generate-002")
        }
    }

@router.get("/tags")
@router.get("/tags/")
def list_tags(
    q: Optional[str] = Query(None, description="Search keyword for tag autocomplete"),
    limit: int = Query(25, ge=1, le=100, description="Max tags to return")
):
    tags = PromptRepository.get_tags(query=q, limit=limit)
    return {"tags": tags}

@router.get("/prompts/{prompt_id}/tags")
def get_prompt_tags(prompt_id: str):
    prompt = PromptRepository.get_prompt_by_id(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt không tồn tại")
    return {"prompt_id": prompt_id, "tags": PromptRepository.get_prompt_tags(prompt_id)}

@router.post("/prompts/{prompt_id}/tags")
def add_prompt_tag(prompt_id: str, req: AddTagRequest):
    prompt = PromptRepository.get_prompt_by_id(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt không tồn tại")
    tags = PromptRepository.add_tag_to_prompt(prompt_id, req.tag)
    return {"status": "success", "prompt_id": prompt_id, "tags": tags}

@router.delete("/prompts/{prompt_id}/tags/{tag_name}")
def delete_prompt_tag(prompt_id: str, tag_name: str):
    prompt = PromptRepository.get_prompt_by_id(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt không tồn tại")
    tags = PromptRepository.remove_tag_from_prompt(prompt_id, tag_name)
    return {"status": "success", "prompt_id": prompt_id, "tags": tags}

