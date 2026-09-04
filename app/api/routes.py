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

class UpdatePromptRequest(BaseModel):
    title: Optional[str] = None
    prompt_code: Optional[str] = None
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

@router.get("/prompts")
@router.get("/prompts/")
def list_prompts(
    q: Optional[str] = Query(None, description="Search keyword"),
    tag: str = Query("all", description="Tag filter: all, has_img, storyboard, portrait, video"),
    limit: Optional[int] = Query(None, description="Limit results"),
    offset: int = Query(0, description="Offset results")
):
    prompts = PromptRepository.get_prompts(query=q, tag=tag, limit=limit, offset=offset)
    return {
        "count": len(prompts),
        "tag": tag,
        "query": q,
        "items": prompts
    }

@router.post("/prompts")
@router.post("/prompts/")
def create_prompt(payload: CreatePromptRequest):
    if not payload.prompt or not payload.prompt.strip():
        raise HTTPException(status_code=400, detail="Nội dung prompt không được để trống")

    parsed_data = parse_incoming_prompt(
        raw_content=payload.prompt,
        raw_media=payload.media
    )

    created_item = PromptRepository.create_prompt(parsed_data)

    # Immediately download any attached images or videos to local storage
    if created_item and created_item.get("images"):
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

# Support PUT, POST, and PATCH for updating prompt title
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
    
    success = PromptRepository.update_prompt_title(
        prompt_id=prompt_id,
        title=payload.title or ""
    )
    return {"status": "success", "updated": success}

@router.delete("/prompts/{prompt_id}")
@router.delete("/prompts/{prompt_id}/")
@router.post("/prompts/{prompt_id}/delete")
def delete_prompt(prompt_id: str):
    prompt = PromptRepository.get_prompt_by_id(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    success = PromptRepository.delete_prompt(prompt_id)
    return {"status": "success", "deleted": success, "id": prompt_id}

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
