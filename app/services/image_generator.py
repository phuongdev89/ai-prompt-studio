import os
import re
import ssl
import time
import json
import base64
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from app.config import get_ai_config, IMAGES_DIR
from app.db.repository import PromptRepository

GENERATE_IMAGE_SYSTEM_PROMPT = """You are an expert AI Image Generation & Creative Visual Artist.
The user will provide a prompt and optional reference image or extra specifications.
Your goal is to generate or provide the final image matching the prompt.
If you can generate images directly or invoke an image tool, please return the image.
You can return the image as:
1. Markdown image tag: ![Generated Image](IMAGE_URL_OR_DATA_URI)
2. Direct image URL: https://...
3. Base64 data URI: data:image/png;base64,...
4. Or a full scalable vector graphic: <svg ...>...</svg>
Make sure the visual composition strictly respects the user's style, subject identity lock, and constraints."""

def format_b64_image(b64_str: str) -> str:
    b64_str = b64_str.strip()
    if b64_str.startswith("data:image/"):
        return b64_str
    if b64_str.startswith("/9j/"):
        return f"data:image/jpeg;base64,{b64_str}"
    elif b64_str.startswith("UklGR"):
        return f"data:image/webp;base64,{b64_str}"
    elif b64_str.startswith("PHN2Zy") or b64_str.startswith("PD94bW"):
        return f"data:image/svg+xml;base64,{b64_str}"
    return f"data:image/png;base64,{b64_str}"

def extract_image_from_text(text: str) -> Optional[Tuple[str, str]]:
    """
    Extracts image URL, Base64 data URI, or SVG from AI response text.
    Returns (image_source, format_type) or None.
    format_type: 'url', 'base64', 'svg'
    """
    if not text:
        return None

    text = text.strip()

    # 1. Check for data URI: data:image/...;base64,...
    b64_match = re.search(r'(data:image\/[a-zA-Z0-9\+\-\.]+;base64,[A-Za-z0-9+/=]+)', text)
    if b64_match:
        return b64_match.group(1), "base64"

    # 2. Check for markdown image: ![...](...)
    md_match = re.search(r'!\[.*?\]\((https?:\/\/[^\s\)\"\']+)\)', text)
    if md_match:
        return md_match.group(1), "url"

    md_b64_match = re.search(r'!\[.*?\]\((data:image\/[^\s\)\"\']+)\)', text)
    if md_b64_match:
        return md_b64_match.group(1), "base64"

    # 3. Check for SVG tag
    svg_match = re.search(r'(<svg[\s\S]*?<\/svg>)', text, re.IGNORECASE)
    if svg_match:
        svg_content = svg_match.group(1).strip()
        # Convert SVG to data URI for universal <img> tag support
        svg_b64 = base64.b64encode(svg_content.encode("utf-8")).decode("ascii")
        return f"data:image/svg+xml;base64,{svg_b64}", "svg"

    # 4. Check for direct URL ending in image extension
    url_match = re.search(r'(https?:\/\/[^\s\)\"\'<>]+?\.(?:png|jpg|jpeg|webp|gif))(?:\?[^\s\)\"\'<>]*)?', text, re.IGNORECASE)
    if url_match:
        return url_match.group(0), "url"

    # 5. Check if entire text is a valid HTTP URL
    if text.startswith("http://") or text.startswith("https://"):
        first_line = text.splitlines()[0].strip()
        if " " not in first_line:
            return first_line, "url"

    # 6. Check for JSON format inside text
    try:
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            data = json.loads(json_match.group(0))
            if isinstance(data, dict):
                # Common fields: url, image, image_url, b64_json
                if "data" in data and isinstance(data["data"], list) and len(data["data"]) > 0:
                    item = data["data"][0]
                    if "url" in item:
                        return item["url"], "url"
                    if "b64_json" in item:
                        return f"data:image/png;base64,{item['b64_json']}", "base64"
                if "url" in data:
                    return data["url"], "url"
                if "image_url" in data:
                    return data["image_url"], "url"
                if "image" in data and isinstance(data["image"], str):
                    if data["image"].startswith("http"):
                        return data["image"], "url"
                    elif data["image"].startswith("data:"):
                        return data["image"], "base64"
                    else:
                        return f"data:image/png;base64,{data['image']}", "base64"
    except Exception:
        pass

    return None

def call_openai_images_generations(
    base_url: str, api_key: str, model_name: str, prompt: str, timeout: int,
    reference_image: Optional[str] = None, image_detail: str = "high",
) -> Optional[str]:
    """Call the tested router contract and parse JSON or SSE output."""
    endpoint = f"{base_url.rstrip('/')}/images/generations"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "Accept": "text/event-stream",
    }
    payload = {
        "model": model_name, "prompt": prompt, "n": 1,
        "size": "auto", "quality": "auto", "background": "auto",
        "image_detail": image_detail or "high", "output_format": "png",
    }
    if reference_image:
        payload["image"] = reference_image
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
        candidates = [body] + [
            line[5:].strip() for line in body.splitlines()
            if line.startswith("data:") and line[5:].strip() not in ("", "[DONE]")
        ]
        for candidate in reversed(candidates):
            try:
                data = json.loads(candidate)
            except (TypeError, json.JSONDecodeError):
                extracted = extract_image_from_text(candidate)
                if extracted:
                    return extracted[0]
                continue
            if isinstance(data, dict) and data.get("data"):
                first = data["data"][0]
                if first.get("url"):
                    return first["url"]
                if first.get("b64_json"):
                    return f"data:image/png;base64,{first['b64_json']}"
            extracted = extract_image_from_text(json.dumps(data, ensure_ascii=False))
            if extracted:
                return extracted[0]
    except Exception:
        return None
    return None


def call_ai_generate_image(
    prompt_text: str, reference_image: Optional[str] = None,
    extra_description: Optional[str] = None, size: str = "1024x1024",
    quality: str = "hd", image_detail: str = "high",
    provider: Optional[str] = None,
) -> Tuple[bool, Optional[str], Optional[str], str]:
    cfg = get_ai_config()
    api_key = cfg.get("api_key", "")
    base_url = cfg.get("base_url") or "https://api.openai.com/v1"
    model_name = cfg.get("image_model") or cfg.get("chat_model") or cfg.get("model") or "gpt-4o-mini"
    timeout = int(cfg.get("timeout", 300))
    if not api_key:
        return False, None, None, "Chưa cấu hình API key"
    parts = [prompt_text.strip()]
    if extra_description and extra_description.strip():
        parts.append(f"[Yêu cầu phụ]: {extra_description.strip()}")
    full_prompt = "\n\n".join(parts)
    image_source = call_openai_images_generations(
        base_url, api_key, model_name, full_prompt, timeout,
        reference_image=reference_image, image_detail=image_detail,
    )
    if not image_source:
        return False, None, None, "API tạo ảnh không trả về ảnh hợp lệ"
    fmt = "base64" if image_source.startswith("data:image/") else "url"
    return True, image_source, fmt, f"Sinh ảnh thành công bằng {model_name}"


def save_generated_image_to_prompt(prompt_id: str, image_data_or_url: str) -> Tuple[bool, Optional[str], str]:
    """
    Saves the generated image to local disk (data/images/) and adds it to the prompt's database record.
    Returns: (success, filename, message)
    """
    if not prompt_id or not image_data_or_url:
        return False, None, "Dữ liệu không hợp lệ"

    # Check prompt exists
    prompt = PromptRepository.get_prompt_by_id(prompt_id)
    if not prompt:
        return False, None, f"Không tìm thấy bản ghi {prompt_id}"

    timestamp = int(time.time())
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    try:
        # 1. Base64 data URI
        if image_data_or_url.startswith("data:image/"):
            header, b64_str = image_data_or_url.split(",", 1)
            ext = "png"
            if "jpeg" in header or "jpg" in header:
                ext = "jpg"
            elif "webp" in header:
                ext = "webp"
            elif "svg" in header:
                ext = "svg"

            filename = f"{prompt_id}_gen_{timestamp}.{ext}"
            file_path = IMAGES_DIR / filename
            img_bytes = base64.b64decode(b64_str)
            with open(file_path, "wb") as f:
                f.write(img_bytes)

            file_size = len(img_bytes)
            local_path = f"images/{filename}"

            PromptRepository.add_image_to_prompt(
                prompt_id=prompt_id,
                filename=filename,
                local_path=local_path,
                url=local_path,
                file_size=file_size,
                status="downloaded"
            )
            return True, filename, "Lưu ảnh thành công vào bản ghi"

        # 2. SVG string
        elif image_data_or_url.strip().startswith("<svg"):
            filename = f"{prompt_id}_gen_{timestamp}.svg"
            file_path = IMAGES_DIR / filename
            svg_bytes = image_data_or_url.encode("utf-8")
            with open(file_path, "wb") as f:
                f.write(svg_bytes)

            file_size = len(svg_bytes)
            local_path = f"images/{filename}"

            PromptRepository.add_image_to_prompt(
                prompt_id=prompt_id,
                filename=filename,
                local_path=local_path,
                url=local_path,
                file_size=file_size,
                status="downloaded"
            )
            return True, filename, "Lưu ảnh SVG thành công vào bản ghi"

        # 3. HTTP / HTTPS URL
        elif image_data_or_url.startswith("http://") or image_data_or_url.startswith("https://"):
            filename = f"{prompt_id}_gen_{timestamp}.jpg"
            file_path = IMAGES_DIR / filename

            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            req = urllib.request.Request(
                image_data_or_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                content = resp.read()
                # Detect actual content type
                ct = resp.headers.get("Content-Type", "")
                if "png" in ct:
                    filename = f"{prompt_id}_gen_{timestamp}.png"
                    file_path = IMAGES_DIR / filename
                elif "webp" in ct:
                    filename = f"{prompt_id}_gen_{timestamp}.webp"
                    file_path = IMAGES_DIR / filename

                with open(file_path, "wb") as f:
                    f.write(content)

            file_size = len(content)
            local_path = f"images/{filename}"

            PromptRepository.add_image_to_prompt(
                prompt_id=prompt_id,
                filename=filename,
                local_path=local_path,
                url=image_data_or_url,
                file_size=file_size,
                status="downloaded"
            )
            return True, filename, "Lưu ảnh thành công vào bản ghi"

        else:
            return False, None, "Định dạng dữ liệu ảnh không hỗ trợ"

    except Exception as e:
        return False, None, f"Lỗi lưu ảnh: {str(e)}"
