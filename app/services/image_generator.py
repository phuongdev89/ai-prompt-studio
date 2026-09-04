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
    base_url: str,
    api_key: str,
    model_name: str,
    prompt: str,
    timeout: int
) -> Optional[str]:
    """Attempts to call standard /images/generations endpoint."""
    endpoint = f"{base_url.rstrip('/')}/images/generations"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": model_name,
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024",
        "output_format": "png"
    }

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        req = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=min(timeout, 30), context=ctx) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            data = json.loads(body)
            if "data" in data and len(data["data"]) > 0:
                first = data["data"][0]
                if "url" in first:
                    return first["url"]
                if "b64_json" in first:
                    return f"data:image/png;base64,{first['b64_json']}"
    except Exception as e:
        # Ignore and let caller fallback
        pass
    return None

def call_ai_generate_image(
    prompt_text: str,
    reference_image: Optional[str] = None,
    extra_description: Optional[str] = None,
    size: str = "1024x1024",
    quality: str = "hd",
    image_detail: str = "high"
) -> Tuple[bool, Optional[str], Optional[str], str]:
    """
    Calls configured AI to generate an image.
    Uses exclusively the AI service configured in .env (1 API Base URL, NO external fallback).
    Supports size, quality, and reference image conditioning via multimodal vision.
    Returns: (success, image_result, format_type, message)
    format_type: 'url', 'base64', 'svg'
    """
    cfg = get_ai_config()
    api_key = cfg.get("api_key", "")
    base_url = cfg.get("base_url") or "https://api.openai.com/v1"
    model_name = cfg.get("image_model") or cfg.get("chat_model") or "gpt-4o-mini"
    timeout = cfg.get("timeout", 300)

    if not api_key:
        return False, None, None, "Chưa cấu hình AI_API_KEY trong tệp .env. Vui lòng cấu hình API Key để tạo ảnh."

    # Validate parameters
    size = size.strip() if size else "1024x1024"
    quality = quality.strip() if quality else "hd"
    image_detail = image_detail.strip() if image_detail else "high"

    # Build composite prompt
    prompt_parts = []
    if prompt_text and prompt_text.strip():
        prompt_parts.append(prompt_text.strip())

    if extra_description and extra_description.strip():
        prompt_parts.append(f"\n[Yêu cầu & Mô tả phụ]: {extra_description.strip()}")

    prompt_parts.append(f"\n[Thông số kỹ thuật]: Kích thước ảnh: {size}, Chất lượng: {quality}.")

    if reference_image:
        prompt_parts.append("\n[LƯU Ý QUAN TRỌNG VỀ ẢNH THAM CHIẾU]: BẮT BUỘC giữ nguyên nhận diện nhân vật, diện mạo khuôn mặt, màu sắc và phong cách từ ảnh tham chiếu đính kèm. Hãy tạo hình ảnh mới với nhân vật/chủ thể trong ảnh tham chiếu theo đúng câu lệnh.")

    combined_prompt = "\n\n".join(prompt_parts)

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    chat_endpoint = f"{base_url.rstrip('/')}/chat/completions"
    image_endpoint = f"{base_url.rstrip('/')}/images/generations"

    # STRATEGY:
    # A. If reference_image is provided -> Prioritize /chat/completions with Multimodal Vision (image_url)
    # because vision LLMs/Gemini inspect the actual image pixels and generate conditioned on it!
    # B. If NO reference_image -> Prioritize standard /images/generations endpoint!

    if reference_image:
        # 1. Attempt Multimodal Chat Completion with image_url & detail
        multimodal_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        multimodal_system = (
            f"You are an expert AI visual artist and image generator. "
            f"A reference image has been provided with detail level '{image_detail}'. "
            f"You MUST carefully analyze and preserve the subject's exact identity, facial structure, skin tone, hair, and visual style from the reference image. "
            f"Generate and render a complete new visual image matching the prompt at {size} resolution and {quality} quality. "
            f"Output the resulting image directly as markdown `![image](data:image/...;base64,...)` or direct URL."
        )
        multimodal_payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": multimodal_system},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": combined_prompt},
                        {"type": "image_url", "image_url": {"url": reference_image, "detail": image_detail}}
                    ]
                }
            ],
            "temperature": 0.6,
            "stream": False
        }

        multimodal_error = None
        try:
            req = urllib.request.Request(
                chat_endpoint,
                data=json.dumps(multimodal_payload).encode("utf-8"),
                headers=multimodal_headers
            )
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                body = resp.read().decode("utf-8", errors="ignore")
                data = json.loads(body)
                raw_chat_text = ""
                if "choices" in data and len(data["choices"]) > 0:
                    raw_chat_text = data["choices"][0].get("message", {}).get("content", "")
                elif "data" in data and len(data["data"]) > 0:
                    first = data["data"][0]
                    if "url" in first:
                        return True, first["url"], "url", f"Sinh ảnh thành công theo ảnh tham chiếu từ {model_name}"
                    if "b64_json" in first:
                        return True, format_b64_image(first['b64_json']), "base64", f"Sinh ảnh thành công theo ảnh tham chiếu từ {model_name}"

                extracted = extract_image_from_text(raw_chat_text)
                if extracted:
                    img_src, fmt = extracted
                    return True, img_src, fmt, f"Sinh ảnh thành công theo ảnh tham chiếu từ {model_name}"
        except Exception as e:
            multimodal_error = str(e)

        # 2. Fallback for reference image: try /images/generations with image field
        try:
            img_payload = {
                "model": model_name,
                "prompt": combined_prompt,
                "n": 1,
                "size": size,
                "quality": quality,
                "image": reference_image,
                "init_images": [reference_image]
            }
            req = urllib.request.Request(
                image_endpoint,
                data=json.dumps(img_payload).encode("utf-8"),
                headers=multimodal_headers
            )
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                if "data" in data and len(data["data"]) > 0:
                    first = data["data"][0]
                    if "url" in first and first["url"]:
                        return True, first["url"], "url", f"Sinh ảnh thành công từ {model_name}"
                    if "b64_json" in first and first["b64_json"]:
                        return True, format_b64_image(first['b64_json']), "base64", f"Sinh ảnh thành công từ {model_name}"
        except Exception as e:
            pass

        return False, None, None, f"Không thể tạo ảnh theo ảnh tham chiếu từ {model_name}. Lỗi: {multimodal_error or 'AI không phản hồi dữ liệu ảnh'}"

    else:
        # NO reference image: Call standard /images/generations first
        image_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        image_payload = {
            "model": model_name,
            "prompt": combined_prompt,
            "n": 1,
            "size": size,
            "quality": quality
        }

        image_api_error = None
        try:
            req = urllib.request.Request(
                image_endpoint,
                data=json.dumps(image_payload).encode("utf-8"),
                headers=image_headers
            )
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                body = resp.read().decode("utf-8", errors="ignore")
                data = json.loads(body)
                if "data" in data and len(data["data"]) > 0:
                    first = data["data"][0]
                    if "url" in first and first["url"]:
                        return True, first["url"], "url", f"Sinh ảnh thành công từ {model_name}"
                    if "b64_json" in first and first["b64_json"]:
                        return True, format_b64_image(first['b64_json']), "base64", f"Sinh ảnh thành công từ {model_name}"
                if "url" in data and data["url"]:
                    return True, data["url"], "url", f"Sinh ảnh thành công từ {model_name}"
                if "images" in data and len(data["images"]) > 0:
                    img0 = data["images"][0]
                    if isinstance(img0, str):
                        if img0.startswith("http"):
                            return True, img0, "url", f"Sinh ảnh thành công từ {model_name}"
                        return True, format_b64_image(img0), "base64", f"Sinh ảnh thành công từ {model_name}"
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="ignore")
            image_api_error = f"Lỗi HTTP {e.code} từ /images/generations: {err_msg[:300]}"
        except (urllib.error.URLError, TimeoutError) as e:
            image_api_error = f"Lỗi kết nối tới /images/generations (Timeout {timeout}s): {str(e)}"
        except Exception as e:
            image_api_error = f"Lỗi gọi /images/generations: {str(e)}"

        # Secondary fallback for text-to-image: /chat/completions
        try:
            chat_payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": f"You are an expert AI image generator. Render the requested image at {size} resolution and {quality} quality. Output the image directly."},
                    {"role": "user", "content": combined_prompt}
                ],
                "temperature": 0.7,
                "stream": False
            }
            req = urllib.request.Request(
                chat_endpoint,
                data=json.dumps(chat_payload).encode("utf-8"),
                headers=image_headers
            )
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                body = resp.read().decode("utf-8", errors="ignore")
                data = json.loads(body)
                raw_chat_text = ""
                if "choices" in data and len(data["choices"]) > 0:
                    raw_chat_text = data["choices"][0].get("message", {}).get("content", "")
                elif "data" in data and len(data["data"]) > 0:
                    first = data["data"][0]
                    if "url" in first:
                        return True, first["url"], "url", f"Sinh ảnh thành công từ {model_name}"
                    if "b64_json" in first:
                        return True, format_b64_image(first['b64_json']), "base64", f"Sinh ảnh thành công từ {model_name}"

                extracted = extract_image_from_text(raw_chat_text)
                if extracted:
                    img_src, fmt = extracted
                    return True, img_src, fmt, f"Sinh ảnh thành công từ {model_name}"
        except Exception:
            pass

        return False, None, None, image_api_error or f"Không nhận được ảnh từ mô hình {model_name}."

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
