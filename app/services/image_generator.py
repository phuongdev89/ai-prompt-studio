import os
import re
import ssl
import time
import json
import base64
import hashlib
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from app.config import get_ai_config, IMAGES_DIR
from app.db.repository import PromptRepository
from app.services.s3_storage import is_configured, upload_content_to_s3, compute_md5

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

def fetch_url_to_base64(url: str, timeout: int = 30) -> Optional[str]:
    """Tải ảnh từ URL (kể cả localhost từ upstream) và chuyển thành base64 data URL."""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            data = resp.read()
            mime = resp.headers.get_content_type() or "image/png"
            b64 = base64.b64encode(data).decode("utf-8")
            return f"data:{mime};base64,{b64}"
    except Exception:
        return None


def robust_json_loads(s: str) -> Optional[Any]:
    """
    Parse JSON an toàn tuyệt đối, chịu lỗi tốt với dấu nháy đơn ('), dấu ngoặc đơn,
    dấu phẩy thừa và văn bản lồng ghép để không bao giờ bị cắt cụt prompt.
    """
    if not s or not isinstance(s, str):
        return None
    s_trimmed = s.strip()

    # 1. Parse JSON chuẩn trực tiếp
    try:
        return json.loads(s_trimmed)
    except Exception:
        pass

    # 2. Tìm khối JSON { ... } hoặc [ ... ] lớn nhất nếu có text thừa bên ngoài
    brace_start = s_trimmed.find("{")
    brace_end = s_trimmed.rfind("}")
    if brace_start != -1 and brace_end > brace_start:
        candidate = s_trimmed[brace_start:brace_end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass

        # 3. Thử sửa dấu ngoặc đơn thành ngoặc kép an toàn bằng ast.literal_eval
        try:
            import ast
            val = ast.literal_eval(candidate)
            if isinstance(val, (dict, list)):
                return val
        except Exception:
            pass

        # 4. Thay thế regex các trường hợp key/value dùng nháy đơn
        try:
            fixed = re.sub(r"(?<=\{|\,)\s*\'([a-zA-Z0-9_\-\.]+)\'\s*:", r' "\1":', candidate)
            fixed = re.sub(r",\s*([\}\]])", r"\1", fixed)
            return json.loads(fixed)
        except Exception:
            pass

    return None



class BaseImageProvider:
    """Base adapter for AI Image generation/editing providers."""

    def __init__(self, base_url: str, api_key: str, model_name: str, timeout: int = 300):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key or ""
        self.model_name = model_name or ""
        self.timeout = timeout

    def get_endpoint(self) -> str:
        raise NotImplementedError

    def get_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "text/event-stream",
        }

    def prepare_prompt(self, prompt: str) -> str:
        return prompt

    def build_payload(self, prompt: str, reference_image: Optional[str] = None, image_detail: str = "high") -> Dict[str, Any]:
        raise NotImplementedError

    def extract_image_from_parsed(self, parsed: Any) -> Optional[str]:
        if not isinstance(parsed, dict):
            return None
        if "data" in parsed and isinstance(parsed["data"], list) and len(parsed["data"]) > 0:
            first = parsed["data"][0]
            if isinstance(first, dict):
                if first.get("b64_json"):
                    return f"data:image/png;base64,{first['b64_json']}"
                if first.get("url"):
                    return first["url"]
        for key in ("url", "image_url", "image"):
            val = parsed.get(key)
            if val and isinstance(val, str):
                return val
        if parsed.get("b64_json"):
            return f"data:image/png;base64,{parsed['b64_json']}"
        return None


class ZProEditProvider(BaseImageProvider):
    """Provider for api.zpro.io.vn and standard OpenAI Image Edits API (/v1/images/edits)."""

    IMAGE_ID = "input_file_0.png"

    def get_endpoint(self) -> str:
        return f"{self.base_url}/images/edits"

    def prepare_prompt(self, prompt: str) -> str:
        if "[ATTACHED_PHOTO]" in prompt:
            return prompt.replace("[ATTACHED_PHOTO]", self.IMAGE_ID)
        return prompt

    def build_payload(self, prompt: str, reference_image: Optional[str] = None, image_detail: str = "high") -> Dict[str, Any]:
        prepared_prompt = self.prepare_prompt(prompt)
        payload = {
            "model": self.model_name,
            "prompt": prepared_prompt,
            "n": 1,
            "size": "auto",
            "quality": "auto",
            "background": "auto",
            "image_detail": image_detail or "high",
            "output_format": "png",
            "response_format": "b64_json",
            "stream": True,
            "images": [],
        }
        if reference_image and str(reference_image).strip():
            payload["images"].append({
                "id": self.IMAGE_ID,
                "image_url": str(reference_image).strip()
            })
        return payload


class NineRouterGenerationsProvider(BaseImageProvider):
    """Provider for 9router.phuonganh.io.vn (/v1/images/generations with flat image field)."""

    def get_endpoint(self) -> str:
        return f"{self.base_url}/images/generations"

    def prepare_prompt(self, prompt: str) -> str:
        if "[ATTACHED_PHOTO]" in prompt:
            return prompt.replace("[ATTACHED_PHOTO]", "the attached reference image")
        return prompt

    def build_payload(self, prompt: str, reference_image: Optional[str] = None, image_detail: str = "high") -> Dict[str, Any]:
        prepared_prompt = self.prepare_prompt(prompt)
        payload = {
            "model": self.model_name,
            "prompt": prepared_prompt,
            "n": 1,
            "size": "auto",
            "quality": "auto",
            "background": "auto",
            "image_detail": image_detail or "high",
            "output_format": "png",
            "response_format": "b64_json",
            "stream": True,
        }
        if reference_image and str(reference_image).strip():
            payload["image"] = str(reference_image).strip()
        return payload


class OmniRouteResponseProvider(BaseImageProvider):
    """Provider for omniroute.phuonganh.io.vn (/v1/responses)."""

    def get_endpoint(self) -> str:
        return f"{self.base_url}/responses"

    def prepare_prompt(self, prompt: str) -> str:
        if "[ATTACHED_PHOTO]" in prompt:
            return prompt.replace("[ATTACHED_PHOTO]", "the input image")
        return prompt

    def build_payload(self, prompt: str, reference_image: Optional[str] = None, image_detail: str = "high") -> Dict[str, Any]:
        prepared_prompt = self.prepare_prompt(prompt)
        content_list = []
        if reference_image and str(reference_image).strip():
            content_list.append({
                "type": "input_image",
                "image_url": str(reference_image).strip(),
                "detail": image_detail or "high"
            })
        content_list.append({
            "type": "input_text",
            "text": prepared_prompt
        })
        return {
            "model": self.model_name,
            "input": [
                {
                    "role": "user",
                    "content": content_list
                }
            ],
            "tools": [
                {
                    "type": "image_generation",
                    "model": self.model_name,
                    "action": "edit" if reference_image else "generate",
                    "quality": "auto",
                    "size": "auto",
                    "output_format": "png"
                }
            ],
            "tool_choice": {
                "type": "image_generation"
            }
        }


def get_image_provider(
    base_url: str,
    api_key: str,
    model_name: str,
    image_type: Optional[str] = None,
    timeout: int = 300,
) -> BaseImageProvider:
    """Factory to return provider adapter. Default is ZProEditProvider (OpenAI Image Edits spec)."""
    t = (image_type or "").strip().lower()
    if not t:
        if "9router" in (base_url or "").lower():
            t = "9router"
        elif "omniroute" in (base_url or "").lower():
            t = "response"
        else:
            t = "edit"

    if t in ("9router", "generation", "generations"):
        return NineRouterGenerationsProvider(base_url, api_key, model_name, timeout)
    elif t in ("response", "responses", "omni", "omniroute"):
        return OmniRouteResponseProvider(base_url, api_key, model_name, timeout)
    else:
        return ZProEditProvider(base_url, api_key, model_name, timeout)


def call_openai_images_generations(
    base_url: str, api_key: str, model_name: str, prompt: str, timeout: int,
    reference_image: Optional[str] = None, image_detail: str = "high",
    image_type: Optional[str] = None,
) -> Optional[str]:
    """Call image provider contract and parse JSON or SSE output."""
    provider = get_image_provider(base_url, api_key, model_name, image_type, timeout)
    endpoint = provider.get_endpoint()
    headers = provider.get_headers()
    payload = provider.build_payload(prompt, reference_image, image_detail)

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req_data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(endpoint, data=req_data, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            body = resp.read().decode("utf-8", errors="ignore")

        candidates = [body] + [
            line[5:].strip() for line in body.splitlines()
            if line.startswith("data:") and line[5:].strip() not in ("", "[DONE]")
        ]
        for candidate in reversed(candidates):
            data = robust_json_loads(candidate)
            if not data:
                extracted = extract_image_from_text(candidate)
                if extracted:
                    return extracted[0]
                continue

            img = provider.extract_image_from_parsed(data)
            if img:
                return img

            extracted = extract_image_from_text(json.dumps(data, ensure_ascii=False))
            if extracted:
                return extracted[0]
    except Exception:
        return None
    return None

def stream_openai_images_generations(
    base_url: str, api_key: str, model_name: str, prompt: str, timeout: int,
    reference_image: Optional[str] = None, image_detail: str = "high",
    image_type: Optional[str] = None,
):
    """Gọi endpoint upstream qua SSE và yield trạng thái theo thời gian thực."""
    provider = get_image_provider(base_url, api_key, model_name, image_type, timeout)
    endpoint = provider.get_endpoint()
    headers = provider.get_headers()
    payload = provider.build_payload(prompt, reference_image, image_detail)

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    yield {"type": "status", "message": f"Đang kết nối SSE tới {endpoint} (model: {model_name})..."}

    try:
        req_data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(endpoint, data=req_data, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            yield {"type": "status", "message": f"Đã kết nối stream thành công. Đang nhận phản hồi thời gian thực từ {model_name}..."}
            has_image = False
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue

                # Bỏ qua các dòng điều khiển SSE như event:, id:, comment
                if line.startswith("event:") or line.startswith(":") or line.startswith("id:"):
                    continue

                data_str = line[5:].strip() if line.startswith("data:") else line
                if data_str == "[DONE]":
                    break
                if not data_str:
                    continue

                parsed = robust_json_loads(data_str)
                if isinstance(parsed, dict):
                    if "error" in parsed:
                        err_obj = parsed["error"]
                        err_msg = err_obj.get("message") if isinstance(err_obj, dict) else str(err_obj)
                        yield {"type": "error", "message": f"Lỗi upstream: {err_msg}"}
                        return

                    img_candidate = provider.extract_image_from_parsed(parsed)

                    if img_candidate:
                        has_image = True
                        if img_candidate.startswith("http://") or img_candidate.startswith("https://"):
                            yield {"type": "status", "message": "Đã nhận URL ảnh từ 9router, đang chuyển đổi sang Base64..."}
                            b64 = fetch_url_to_base64(img_candidate)
                            if b64:
                                img_candidate = b64

                        fmt = "base64" if img_candidate.startswith("data:image/") else "url"
                        yield {
                            "type": "complete",
                            "image_url": img_candidate,
                            "format": fmt,
                            "message": f"Sinh ảnh thành công bằng {model_name}"
                        }
                        return

                    # Đọc content delta nếu model trả về dạng choices
                    if "choices" in parsed and isinstance(parsed["choices"], list):
                        for choice in parsed["choices"]:
                            if isinstance(choice, dict):
                                delta = choice.get("delta") or {}
                                content = delta.get("content") or delta.get("reasoning_content") or choice.get("text")
                                if content:
                                    yield {"type": "chunk", "text": content}
                        continue

                    # Các trường JSON trạng thái tiến trình (progress, stage, bytesReceived...)
                    filtered = {k: v for k, v in parsed.items() if k not in ("id", "object", "created", "model")}
                    if filtered:
                        yield {"type": "progress", "data": filtered}
                    else:
                        yield {"type": "progress", "data": parsed}
                else:
                    # Trích xuất ảnh nếu là text dạng SVG hoặc URL
                    extracted = extract_image_from_text(data_str)
                    if extracted:
                        has_image = True
                        img_res = extracted[0]
                        if img_res.startswith("http://") or img_res.startswith("https://"):
                            yield {"type": "status", "message": "Đang chuyển ảnh kết quả sang định dạng Base64..."}
                            b64 = fetch_url_to_base64(img_res)
                            if b64:
                                img_res = b64
                        fmt = "base64" if img_res.startswith("data:image/") else "url"
                        yield {
                            "type": "complete",
                            "image_url": img_res,
                            "format": fmt,
                            "message": f"Sinh ảnh thành công bằng {model_name}"
                        }
                        return
                    else:
                        yield {"type": "status", "message": data_str}

            if not has_image:
                yield {"type": "error", "message": "Mô hình AI đã hoàn tất stream nhưng không có dữ liệu ảnh trả về"}

    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        parsed_err = robust_json_loads(err_body)
        msg = f"HTTP {e.code}"
        if isinstance(parsed_err, dict) and "error" in parsed_err:
            err_obj = parsed_err["error"]
            msg = err_obj.get("message") if isinstance(err_obj, dict) else str(err_obj)
        elif err_body:
            msg = err_body[:300]
        yield {"type": "error", "message": f"Lỗi upstream ({e.code}): {msg}"}
    except Exception as e:
        yield {"type": "error", "message": f"Lỗi kết nối mô hình AI: {str(e)}"}


def sanitize_prompt_for_image_generation(prompt_str: str) -> str:
    """
    Sanitizes prompt text or JSON string before sending to image generation API.
    Removes any specific filename placeholders (image_0.png, input.jpg, etc.)
    and standardizes them to [ATTACHED_PHOTO] so downstream endpoints never
    reject requests with 'Vui lòng tải lên ảnh tham chiếu...'.
    """
    if not prompt_str or not isinstance(prompt_str, str):
        return prompt_str or ""

    parsed = robust_json_loads(prompt_str)
    if isinstance(parsed, dict):
        try:
            from app.services.ai_converter import normalize_reference_image_in_json
            normalized, _ = normalize_reference_image_in_json(parsed)
            return json.dumps(normalized, ensure_ascii=False, indent=2)
        except Exception:
            pass

    from app.services.ai_converter import sanitize_text_reference_images
    return sanitize_text_reference_images(prompt_str)


def call_ai_generate_image_stream(
    prompt_text: str, reference_image: Optional[str] = None,
    extra_description: Optional[str] = None, size: str = "1024x1024",
    quality: str = "hd", image_detail: str = "high",
    provider: Optional[str] = None,
    model: Optional[str] = None,
):
    """Stream các sự kiện tạo ảnh theo thời gian thực (SSE)."""
    cfg = get_ai_config()
    api_key = cfg.get("image_api_key") or cfg.get("api_key", "")
    base_url = cfg.get("image_url") or cfg.get("base_url") or "https://9router.phuonganh.io.vn/v1"

    available_models = cfg.get("image_models") or [cfg.get("image_model") or "cx/gpt-5.6-sol-image"]
    model_name = model.strip() if (model and model.strip()) else available_models[0]

    timeout = int(cfg.get("timeout", 300))
    if not api_key:
        yield {"type": "error", "message": "Chưa cấu hình API key trong .env (AI_IMAGE_KEY hoặc AI_API_KEY)"}
        return

    parts = [prompt_text.strip()]
    if extra_description and extra_description.strip():
        parts.append(f"[Yêu cầu phụ]: {extra_description.strip()}")
    full_prompt = "\n\n".join(parts)
    full_prompt = sanitize_prompt_for_image_generation(full_prompt)

    yield from stream_openai_images_generations(
        base_url=base_url,
        api_key=api_key,
        model_name=model_name,
        prompt=full_prompt,
        timeout=timeout,
        reference_image=reference_image,
        image_detail=image_detail,
    )

def call_ai_generate_image(
    prompt_text: str, reference_image: Optional[str] = None,
    extra_description: Optional[str] = None, size: str = "1024x1024",
    quality: str = "hd", image_detail: str = "high",
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> Tuple[bool, Optional[str], Optional[str], str]:
    cfg = get_ai_config()
    api_key = cfg.get("image_api_key") or cfg.get("api_key", "")
    base_url = cfg.get("image_url") or cfg.get("base_url") or "https://9router.phuonganh.io.vn/v1"

    # Ưu tiên model được người dùng chọn từ dropdown, nếu không có lấy model mặc định đầu tiên
    available_models = cfg.get("image_models") or [cfg.get("image_model") or "cx/gpt-5.6-sol-image"]
    model_name = model.strip() if (model and model.strip()) else available_models[0]

    timeout = int(cfg.get("timeout", 300))
    if not api_key:
        return False, None, None, "Chưa cấu hình API key (AI_IMAGE_KEY hoặc AI_API_KEY)"
    parts = [prompt_text.strip()]
    if extra_description and extra_description.strip():
        parts.append(f"[Yêu cầu phụ]: {extra_description.strip()}")
    full_prompt = "\n\n".join(parts)
    full_prompt = sanitize_prompt_for_image_generation(full_prompt)
    image_source = call_openai_images_generations(
        base_url, api_key, model_name, full_prompt, timeout,
        reference_image=reference_image, image_detail=image_detail,
        image_type=config.get("image_type"),
    )
    if not image_source:
        return False, None, None, "API tạo ảnh không trả về ảnh hợp lệ"
    if image_source.startswith("http://") or image_source.startswith("https://"):
        b64_img = fetch_url_to_base64(image_source)
        if b64_img:
            image_source = b64_img
    fmt = "base64" if image_source.startswith("data:image/") else "url"
    return True, image_source, fmt, f"Sinh ảnh thành công bằng {model_name}"


def resize_image_to_max_dimension(img_bytes: bytes, max_dim: int = 480, default_ext: str = "png") -> Tuple[bytes, str, str]:
    """Resize image so that max(width, height) <= max_dim (preserving aspect ratio).
    Returns (resized_bytes, extension, mime_type).
    """
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(img_bytes))
        orig_w, orig_h = img.size
        img_format = (img.format or "").upper()

        if max(orig_w, orig_h) > max_dim:
            scale = max_dim / max(orig_w, orig_h)
            new_w = max(1, int(round(orig_w * scale)))
            new_h = max(1, int(round(orig_h * scale)))
            resample_filter = getattr(getattr(Image, "Resampling", Image), "LANCZOS", Image.LANCZOS)
            img = img.resize((new_w, new_h), resample=resample_filter)

        out_buf = io.BytesIO()
        if img_format in ("JPEG", "JPG"):
            ext = "jpg"
            mime = "image/jpeg"
            if img.mode in ("RGBA", "LA", "P"):
                rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                rgb_img.paste(img, mask=img.split()[3] if img.mode == "RGBA" else None)
                img = rgb_img
            img.save(out_buf, format="JPEG", quality=85, optimize=True)
        elif img_format == "WEBP":
            ext = "webp"
            mime = "image/webp"
            img.save(out_buf, format="WEBP", quality=85)
        else:
            ext = "png"
            mime = "image/png"
            img.save(out_buf, format="PNG", optimize=True)

        return out_buf.getvalue(), ext, mime
    except Exception as e:
        mime = f"image/{default_ext}"
        return img_bytes, default_ext, mime


def save_generated_image_to_prompt(prompt_id: str, image_data_or_url: str) -> Tuple[bool, Optional[str], str]:
    """Save newly generated AI image to a prompt record.
    Resizes image to max 480px, saves locally and uploads the 480px version to S3 (no original file saved).
    """
    if not image_data_or_url or not str(image_data_or_url).strip():
        return False, None, "Dữ liệu không hợp lệ"

    # Check prompt exists
    prompt = PromptRepository.get_prompt_by_id(prompt_id)
    if not prompt:
        return False, None, f"Không tìm thấy bản ghi {prompt_id}"

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    cfg = get_ai_config()

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

            img_bytes = base64.b64decode(b64_str)

            # Resize to max 480px before saving or uploading to S3
            if ext != "svg":
                img_bytes, ext, mime_type = resize_image_to_max_dimension(img_bytes, max_dim=480, default_ext=ext)
            else:
                mime_type = "image/svg+xml"

            md5_hex = hashlib.md5(img_bytes).hexdigest()
            filename = f"{md5_hex}.{ext}"
            file_path = IMAGES_DIR / filename
            with open(file_path, "wb") as f:
                f.write(img_bytes)

            file_size = len(img_bytes)
            local_path = f"images/{filename}"

            target_url = local_path
            if is_configured(cfg):
                try:
                    s3_res = upload_content_to_s3(
                        content=img_bytes,
                        filename=filename,
                        mime=mime_type,
                        prefix=cfg.get("s3_key_prefix", "ai_prompts_database"),
                        cfg=cfg
                    )
                    target_url = s3_res.get("url") or local_path
                except Exception as s3_err:
                    print(f"[!] Warning S3 upload failed on save generated image: {s3_err}")

            PromptRepository.add_image_to_prompt(
                prompt_id=prompt_id,
                filename=filename,
                local_path=local_path,
                url=target_url,
                file_size=file_size,
                status="downloaded"
            )
            return True, filename, "Lưu ảnh (480px) thành công vào bản ghi"

        # 2. SVG string
        elif image_data_or_url.strip().startswith("<svg"):
            svg_bytes = image_data_or_url.encode("utf-8")
            md5_hex = hashlib.md5(svg_bytes).hexdigest()
            filename = f"{md5_hex}.svg"
            file_path = IMAGES_DIR / filename
            with open(file_path, "wb") as f:
                f.write(svg_bytes)

            file_size = len(svg_bytes)
            local_path = f"images/{filename}"

            target_url = local_path
            if is_configured(cfg):
                try:
                    s3_res = upload_content_to_s3(
                        content=svg_bytes,
                        filename=filename,
                        mime="image/svg+xml",
                        prefix=cfg.get("s3_key_prefix", "ai_prompts_database"),
                        cfg=cfg
                    )
                    target_url = s3_res.get("url") or local_path
                except Exception as s3_err:
                    print(f"[!] Warning S3 upload failed on save generated svg: {s3_err}")

            PromptRepository.add_image_to_prompt(
                prompt_id=prompt_id,
                filename=filename,
                local_path=local_path,
                url=target_url,
                file_size=file_size,
                status="downloaded"
            )
            return True, filename, "Lưu ảnh SVG thành công vào bản ghi"

        # 3. HTTP / HTTPS URL
        elif image_data_or_url.startswith("http://") or image_data_or_url.startswith("https://"):
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            req = urllib.request.Request(
                image_data_or_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                raw_content = resp.read()
                ct = resp.headers.get("Content-Type", "")
                ext = "jpg"
                if "png" in ct:
                    ext = "png"
                elif "webp" in ct:
                    ext = "webp"

            # Resize to max 480px before saving or uploading to S3
            content, ext, mime_type = resize_image_to_max_dimension(raw_content, max_dim=480, default_ext=ext)

            md5_hex = hashlib.md5(content).hexdigest()
            filename = f"{md5_hex}.{ext}"
            file_path = IMAGES_DIR / filename

            with open(file_path, "wb") as f:
                f.write(content)

            file_size = len(content)
            local_path = f"images/{filename}"

            target_url = local_path
            if is_configured(cfg):
                try:
                    s3_res = upload_content_to_s3(
                        content=content,
                        filename=filename,
                        mime=mime_type,
                        prefix=cfg.get("s3_key_prefix", "ai_prompts_database"),
                        cfg=cfg
                    )
                    target_url = s3_res.get("url") or local_path
                except Exception as s3_err:
                    print(f"[!] Warning S3 upload failed on save generated url: {s3_err}")

            PromptRepository.add_image_to_prompt(
                prompt_id=prompt_id,
                filename=filename,
                local_path=local_path,
                url=target_url,
                file_size=file_size,
                status="downloaded"
            )
            return True, filename, "Lưu ảnh (480px) thành công vào bản ghi"

        else:
            return False, None, "Định dạng dữ liệu ảnh không hỗ trợ"

    except Exception as e:
        return False, None, f"Lỗi lưu ảnh: {str(e)}"
