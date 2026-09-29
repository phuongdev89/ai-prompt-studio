import json
import re
import ssl
import urllib.request
import urllib.error
from typing import Dict, Any, Tuple, List
from app.config import get_ai_config
from app.services.parser import extract_flat_fields

SYSTEM_PROMPT = """ROLE & OBJECTIVE
You are VisionStruct, an advanced Computer Vision & Data Serialization Engine. Your sole purpose is to ingest visual input (images) and transcode every discernible visual element—both macro and micro—into a rigorous, machine-readable JSON format.

CORE DIRECTIVE
Do not summarize. Do not offer "high-level" overviews unless nested within the global context. You must capture 100% of the visual data available in the image. If a detail exists in pixels, it must exist in your JSON output. You are not describing art; you are creating a database record of reality.

ANALYSIS PROTOCOL
Before generating the final JSON, perform a silent "Visual Sweep" (do not output this):
1. Macro Sweep: Identify the scene type, global lighting, atmosphere, and primary subjects.
2. Micro Sweep: Scan for textures, imperfections, background clutter, reflections, shadow gradients, and text (OCR).
3. Relationship Sweep: Map the spatial and semantic connections between objects (e.g., "holding," "obscuring," "next to").
4. Reference Alignment Sweep (if reference image is present): Detect and lock subject identifiers (face structure, hairline, skin tone, facial features, distinct marks) to maintain strict cross-image identity consistency.

OUTPUT FORMAT (STRICT)
You must return the output inside a single markdown code block (```json ... ```) so that it includes a copy button. Do not include conversational filler before or after the code block. Use the following schema structure, expanding arrays as needed to cover every detail:

```json
{
  "meta": {
    "image_quality": "8K Ultra-HD",
    "target_resolution": "7680x4320 (8K)",
    "image_type": "Photo/Illustration/Diagram/Screenshot/etc"
  },
  "reference_image_analysis": {
    "reference_provided": false,
    "identity_lock": {
      "subject_id": "ref_subject_01 or null",
      "facial_structure": "Bone structure, jawline, nose shape, lip shape or null",
      "eyes": "Iris color, eye shape, tilt, eyebrows or null",
      "hair": "Hairline, exact color tones, length, style, part location or null",
      "skin_characteristics": "Undertone, complexion, moles, freckles, unique marks or null",
      "consistency_adherence_score": "High/Exact/null"
    }
  },
  "global_context": {
    "scene_description": "A comprehensive, objective paragraph describing the entire scene in extreme 8K fidelity.",
    "time_of_day": "Specific time or lighting condition",
    "weather_atmosphere": "Foggy/Clear/Rainy/Chaotic/Serene",
    "lighting": {
      "source": "Sunlight/Artificial/Mixed",
      "direction": "Top-down/Backlit/etc",
      "quality": "Hard/Soft/Diffused",
      "color_temp": "Warm/Cool/Neutral"
    }
  },
  "color_palette": {
    "dominant_hex_estimates": ["#RRGGBB", "#RRGGBB"],
    "accent_colors": ["Color name 1", "Color name 2"],
    "contrast_level": "High/Low/Medium"
  },
  "composition": {
    "camera_angle": "Eye-level/High-angle/Low-angle/Macro",
    "framing": "Close-up/Wide-shot/Medium-shot",
    "depth_of_field": "Shallow (blurry background) / Deep (everything in focus)",
    "focal_point": "The primary element drawing the eye"
  },
  "objects": [
    {
      "id": "obj_001",
      "label": "Primary Object Name",
      "category": "Person/Vehicle/Furniture/etc",
      "reference_match": "Linked to ref_subject_01 or null",
      "location": "Center/Top-Left/etc",
      "prominence": "Foreground/Background",
      "visual_attributes": {
        "color": "Detailed color description",
        "texture": "Rough/Smooth/Metallic/Fabric-type",
        "material": "Wood/Plastic/Skin/etc",
        "state": "Damaged/New/Wet/Dirty",
        "dimensions_relative": "Large relative to frame"
      },
      "micro_details": [
        "Scuff mark on left corner",
        "Stitching pattern visible on hem",
        "Reflection of window in surface",
        "Dust particles visible"
      ],
      "pose_or_orientation": "Standing/Tilted/Facing away",
      "text_content": "null or specific text if present on object"
    }
  ],
  "text_ocr": {
    "present": true,
    "content": [
      {
        "text": "The exact text written",
        "location": "Sign post/T-shirt/Screen",
        "font_style": "Serif/Handwritten/Bold",
        "legibility": "Clear/Partially obscured"
      }
    ]
  },
  "semantic_relationships": [
    "Object A is supporting Object B",
    "Object C is casting a shadow on Object A",
    "Object D is visually similar to Object E"
  ]
}
```

CRITICAL CONSTRAINTS
Resolution Standard: Always target and require 8K resolution specs across all descriptions. Never attempt to estimate a lower native resolution of the uploaded file; treat and serialize the subject matter at native 8K clarity.
Reference Image Detection & Normalization: Check if the input prompt, raw text, or description mentions, requires, or implies a reference image, sample photo, or attached image (e.g., 'ảnh tham chiếu', 'hình tham chiếu', 'ảnh mẫu', 'hình mẫu', 'reference image', 'ref image', 'cref', 'sref', or mentions placeholder image filenames like 'image_0.png', 'image.png', 'input.jpg', 'ref.png', 'face.jpg', 'character.png').
If mentioned or if any placeholder filename is used:
- NEVER keep or output arbitrary filenames (e.g., 'image_0.png', 'image.png', 'input.jpg').
- Always specify reference directives clearly:
  * "reference_image_dependency": "Mandatory use of uploaded image for character consistency"
  * "identity_reference": "[ATTACHED_PHOTO]"
  * "outfit_reference": "[ATTACHED_PHOTO]"
  * "primary_subject_reference": "[ATTACHED_PHOTO]"
- In reference_image_analysis:
  * Set reference_provided to true
  * Set reference_source to "[ATTACHED_PHOTO]"
  * In identity_lock, set subject_id to "REF_ATTACHED_01" and consistency_adherence_score to "Exact"
- If the prompt references multiple images or aspects, define a structured sub-object with unique IDs:
  "reference_dependencies": {
    "primary_reference": {
      "id": "REF_ATTACHED_01",
      "source": "[ATTACHED_PHOTO]",
      "directive": "Mandatory use of uploaded image for character consistency",
      "applied_elements": ["facial_identity", "features", "hair", "outfit"]
    }
  }
  and refer to "REF_ATTACHED_01" or "[ATTACHED_PHOTO]" throughout the JSON.
Granularity: Never say "a crowd of people." Instead, list distinct individuals as discrete objects with complete visual attributes.
Micro-Details: You must catalog microscopic surface elements: skin pores, micro-scratches, fabric grain, atmospheric dust, and specular highlights.
Null Values: If a field is not applicable, set it to null rather than omitting the key."""

def parse_chat_response(body_text: str) -> str:
    body_text = body_text.strip()
    
    # 1. Try standard JSON response
    try:
        data = json.loads(body_text)
        if "choices" in data and len(data["choices"]) > 0:
            c = data["choices"][0]
            if "message" in c and "content" in c["message"]:
                return c["message"]["content"]
            if "delta" in c and "content" in c["delta"]:
                return c["delta"]["content"]
    except Exception:
        pass

    # 2. Try Server-Sent Events (SSE) stream chunks: data: {...}
    collected_text = []
    for line in body_text.splitlines():
        line = line.strip()
        if not line or line.startswith(":"):
            continue
        if line.startswith("data:"):
            chunk_data = line[5:].strip()
            if chunk_data == "[DONE]":
                continue
            try:
                chunk_obj = json.loads(chunk_data)
                if "choices" in chunk_obj and len(chunk_obj["choices"]) > 0:
                    delta = chunk_obj["choices"][0].get("delta", {})
                    content_piece = delta.get("content", "")
                    if content_piece:
                        collected_text.append(content_piece)
                    else:
                        msg = chunk_obj["choices"][0].get("message", {})
                        if msg.get("content"):
                            collected_text.append(msg["content"])
            except Exception:
                continue

    if collected_text:
        return "".join(collected_text)

    # 3. Fallback: return as-is
    return body_text

def clean_json_response(content: str) -> str:
    content = content.strip()
    # 1. Remove <think> ... </think> tags from thinking models (DeepSeek-R1, etc.)
    content = re.sub(r"<think>[\s\S]*?</think>", "", content, flags=re.IGNORECASE).strip()

    # 2. Clean markdown code fences ```json ... ``` or ``` ... ```
    content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
    content = re.sub(r"\s*```$", "", content)
    content = content.strip()

    # 3. Extract outer-most JSON object { ... }
    s = content.find('{')
    e = content.rfind('}')
    if s != -1 and e != -1 and e > s:
        content = content[s:e+1]

    return content

REF_KEYWORDS_PATTERNS = [
    r'(?i)ảnh\s*(?:tham\s*chiếu|mẫu|đính\s*kèm|gốc|tải\s*lên)',
    r'(?i)hình\s*(?:tham\s*chiếu|mẫu|đính\s*kèm)',
    r'(?i)bức\s*ảnh\s*(?:tham\s*chiếu|mẫu)',
    r'(?i)reference\s*(?:image|photo|picture|file|source|face|character)',
    r'(?i)ref\s*(?:image|photo)',
    r'(?i)input\s*image',
    r'(?i)source\s*image',
    r'(?i)attached\s*image',
    r'(?i)face\s*reference',
    r'(?i)character\s*reference',
    r'(?i)--cref\b',
    r'(?i)--sref\b',
]

IMAGE_FILENAME_RE = re.compile(r'(?i)\b[\w\.-]+\.(?:png|jpe?g|webp|gif)\b')
IMAGE_REF_KEYS_RE = re.compile(
    r'(?i)(primary_subject_reference|identity_reference|outfit_reference|reference.*image|ref.*image|image.*ref|source.*image|input.*image|sample.*image|subject.*ref|reference.*photo|reference.*file|reference.*source|reference_match|character_reference|face_reference)'
)

def find_all_image_filenames(obj: Any, raw_text: str = "") -> List[str]:
    filenames = []
    if raw_text:
        for m in IMAGE_FILENAME_RE.finditer(raw_text):
            fn = m.group(0)
            if not fn.startswith("http") and fn not in filenames:
                filenames.append(fn)

    def walk(val: Any):
        if isinstance(val, str):
            for m in IMAGE_FILENAME_RE.finditer(val):
                fn = m.group(0)
                if not fn.startswith("http") and fn not in filenames:
                    filenames.append(fn)
        elif isinstance(val, dict):
            for v in val.values():
                walk(v)
        elif isinstance(val, list):
            for item in val:
                walk(item)

    walk(obj)
    return filenames

def sanitize_text_reference_images(text: str) -> str:
    """Replaces filenames and placeholder phrases in raw prompt text with [ATTACHED_PHOTO]."""
    if not text:
        return text
    res = IMAGE_FILENAME_RE.sub("[ATTACHED_PHOTO]", text)
    res = res.replace("Ảnh tham chiếu tải lên", "[ATTACHED_PHOTO]")
    res = re.sub(r'(?i)\b(?:linked\s*to\s*)?ref_subject(?:_\d+)?\b', 'REF_ATTACHED_01', res)
    return res

def normalize_reference_image_in_json(parsed_json: Any, raw_text: str = "") -> Tuple[Any, bool]:
    """
    Kiểm tra xem trong văn bản gốc hoặc JSON có đề cập đến ảnh tham chiếu không.
    Nếu có, hoặc nếu ảnh tham chiếu đang là tên tệp (ví dụ: image_0.png, image.png, input.jpg),
    chuẩn hóa nó thành token chuẩn [ATTACHED_PHOTO] và thiết lập cấu trúc ràng buộc:
    - 'reference_image_dependency': 'Mandatory use of uploaded image for character consistency'
    - 'identity_reference': '[ATTACHED_PHOTO]'
    - 'outfit_reference': '[ATTACHED_PHOTO]'
    - Đặt ID rõ ràng cho từng ảnh tham chiếu ('reference_dependencies') để tránh nhầm lẫn.
    """
    if not isinstance(parsed_json, dict):
        return parsed_json, False

    text_to_check = (raw_text or "").strip()
    distinct_fns = find_all_image_filenames(parsed_json, text_to_check)

    if len(distinct_fns) > 1:
        fn_to_token = {fn: f"[ATTACHED_PHOTO_{i+1}]" for i, fn in enumerate(distinct_fns)}
        fn_to_id = {fn: f"REF_ATTACHED_{i+1:02d}" for i, fn in enumerate(distinct_fns)}
    elif len(distinct_fns) == 1:
        fn_to_token = {distinct_fns[0]: "[ATTACHED_PHOTO]"}
        fn_to_id = {distinct_fns[0]: "REF_ATTACHED_01"}
    else:
        fn_to_token = {}
        fn_to_id = {}

    has_ref_in_text = any(re.search(pat, text_to_check) for pat in REF_KEYWORDS_PATTERNS)
    has_filename_in_text = bool(distinct_fns)
    found_ref_in_json = False

    def sanitize_val(key_name: str, val: Any) -> Any:
        nonlocal found_ref_in_json
        if isinstance(val, str):
            is_ref_key = bool(IMAGE_REF_KEYS_RE.search(key_name))
            has_fn = bool(IMAGE_FILENAME_RE.search(val))
            has_ref_kw = any(re.search(pat, val) for pat in REF_KEYWORDS_PATTERNS)
            has_ref_subject = bool(re.search(r'(?i)ref_subject', val))

            if is_ref_key or has_fn or has_ref_kw or has_ref_subject:
                found_ref_in_json = True

                # Specific mapped filenames first
                for fn, token in fn_to_token.items():
                    if fn in val:
                        val = val.replace(fn, token)

                # Check for ref_subject placeholder (e.g. "Linked to ref_subject_01", "ref_subject_01")
                if has_ref_subject:
                    if len(val.strip().split()) <= 4:
                        return "REF_ATTACHED_01"
                    val = re.sub(r'(?i)\b(?:linked\s*to\s*)?ref_subject(?:_\d+)?\b', 'REF_ATTACHED_01', val)

                # Clean any remaining image filenames
                if IMAGE_FILENAME_RE.search(val):
                    if len(val.strip().split()) <= 2:
                        return "[ATTACHED_PHOTO]"
                    val = IMAGE_FILENAME_RE.sub("[ATTACHED_PHOTO]", val)

                # Clean 'Ảnh tham chiếu tải lên'
                if "Ảnh tham chiếu tải lên" in val:
                    if len(val.strip().split()) <= 5:
                        return "[ATTACHED_PHOTO]"
                    val = val.replace("Ảnh tham chiếu tải lên", "[ATTACHED_PHOTO]")

                if is_ref_key:
                    clean_v = val.strip().lower()
                    if clean_v in ("ref_subject_01", "image.png", "image_0.png", "input.jpg", "ref.png", "photo.jpg", "face.jpg", "null", "none", ""):
                        return "[ATTACHED_PHOTO]"
                    if has_ref_kw and len(val.strip().split()) <= 5:
                        return "[ATTACHED_PHOTO]"

                return val

        elif isinstance(val, dict):
            return {k: sanitize_val(k, v) for k, v in val.items()}
        elif isinstance(val, list):
            return [sanitize_val(key_name, item) for item in val]
        return val

    sanitized = {k: sanitize_val(k, v) for k, v in parsed_json.items()}
    has_ref = has_ref_in_text or has_filename_in_text or found_ref_in_json

    if has_ref:
        # 1. Update project_directives if present
        if "project_directives" in sanitized and isinstance(sanitized["project_directives"], dict):
            pdir = sanitized["project_directives"]
            pdir["primary_subject_reference"] = "[ATTACHED_PHOTO]"
            pdir["reference_image_dependency"] = "Mandatory use of uploaded image for character consistency"
            pdir["identity_reference"] = "[ATTACHED_PHOTO]"
            pdir["outfit_reference"] = "[ATTACHED_PHOTO]"

        # 2. Update root reference fields
        if "primary_subject_reference" in sanitized:
            sanitized["primary_subject_reference"] = "[ATTACHED_PHOTO]"
        if "reference_image" in sanitized:
            sanitized["reference_image"] = "[ATTACHED_PHOTO]"

        # 3. Add structured reference_dependencies with unique IDs
        if len(distinct_fns) > 1:
            ref_deps = {}
            for i, fn in enumerate(distinct_fns):
                ref_id = fn_to_id[fn]
                ref_deps[ref_id] = {
                    "id": ref_id,
                    "source": fn_to_token[fn],
                    "dependency_type": "Mandatory use of uploaded image for character consistency" if i == 0 else "Mandatory use of uploaded image",
                    "role": "primary_character_identity" if i == 0 else f"reference_subject_{i+1}"
                }
            sanitized["reference_dependencies"] = ref_deps
        else:
            sanitized["reference_dependencies"] = {
                "primary_reference": {
                    "id": "REF_ATTACHED_01",
                    "source": "[ATTACHED_PHOTO]",
                    "dependency_type": "Mandatory use of uploaded image for character consistency",
                    "applied_elements": ["facial_identity", "facial_features", "hair", "skin_texture", "outfit"]
                }
            }

        # 4. Standard reference_image_analysis
        if "reference_image_analysis" not in sanitized or not isinstance(sanitized["reference_image_analysis"], dict):
            sanitized["reference_image_analysis"] = {}

        ref_analysis = sanitized["reference_image_analysis"]
        ref_analysis["reference_provided"] = True
        ref_analysis["reference_source"] = "[ATTACHED_PHOTO]"

        if "identity_lock" not in ref_analysis or not isinstance(ref_analysis["identity_lock"], dict):
            ref_analysis["identity_lock"] = {}

        id_lock = ref_analysis["identity_lock"]
        id_lock["subject_id"] = "REF_ATTACHED_01"
        id_lock["consistency_adherence_score"] = "Exact"

    return sanitized, has_ref

def call_ai_convert_to_json(raw_text: str, provider: str = None, reference_image_base64: str = None) -> Tuple[bool, Any, str]:
    cfg = get_ai_config()
    active_provider = "openai"

    api_key = cfg["api_key"]
    base_url = cfg["base_url"]
    model_name = cfg["model_name"]
    timeout = cfg.get("timeout", 300)
    use_stream = cfg.get("stream", True)

    if not api_key:
        return False, None, "Chưa cấu hình AI_API_KEY trong tệp .env. Vui lòng kiểm tra lại tệp .env."

    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    user_content = []
    user_content.append({"type": "text", "text": f"Analyze and convert this visual information into a comprehensive, deeply structured, high-fidelity JSON object retaining 100% of all details, parameters, rules, and sub-panel breakdowns. Context/raw prompt (if any):\n\n{raw_text}"})

    if reference_image_base64:
        # Standard OpenAI vision payload
        b64_pure = reference_image_base64
        mime_type = "image/png"
        if reference_image_base64.startswith("data:"):
            hdr, b64_pure = reference_image_base64.split(",", 1)
            if "image/jpeg" in hdr or "image/jpg" in hdr:
                mime_type = "image/jpeg"
            elif "image/webp" in hdr:
                mime_type = "image/webp"

        user_content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{mime_type};base64,{b64_pure}"
            }
        })

    payload = {
        "model": model_name or "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.2,
        "stream": use_stream
    }

    # Custom SSL context for proxies / internal routers
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        req = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            if use_stream:
                # Process Server-Sent Events (SSE) stream chunks line-by-line
                chunks = []
                for raw_line in resp:
                    line = raw_line.decode("utf-8", errors="ignore").strip()
                    if not line or line.startswith(":"):
                        continue
                    if line.startswith("data:"):
                        chunk_data = line[5:].strip()
                        if chunk_data == "[DONE]":
                            break
                        try:
                            chunk_obj = json.loads(chunk_data)
                            choices = chunk_obj.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content_piece = delta.get("content") or delta.get("text") or ""
                                if content_piece:
                                    chunks.append(content_piece)
                                else:
                                    msg = choices[0].get("message", {})
                                    if msg.get("content"):
                                        chunks.append(msg["content"])
                        except Exception:
                            continue
                raw_response = "".join(chunks).strip()
            else:
                body = resp.read().decode("utf-8", errors="ignore")
                raw_response = parse_chat_response(body).strip()

            if not raw_response:
                return False, None, "Mô hình AI không trả về nội dung nào."

            cleaned_content = clean_json_response(raw_response)

            try:
                parsed_json = json.loads(cleaned_content)
            except json.JSONDecodeError as jde:
                # Attempt to fix common trailing comma errors
                fixed_content = re.sub(r",\s*([\]}])", r"\1", cleaned_content)
                parsed_json = json.loads(fixed_content)

            if not isinstance(parsed_json, (dict, list)):
                return False, None, f"Dữ liệu trả về không phải là JSON object hợp lệ: {raw_response[:200]}"

            if isinstance(parsed_json, dict):
                parsed_json, _ = normalize_reference_image_in_json(parsed_json, raw_text)
            elif isinstance(parsed_json, list):
                parsed_json = [normalize_reference_image_in_json(item, raw_text)[0] if isinstance(item, dict) else item for item in parsed_json]

            return True, parsed_json, "Thành công"

    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        return False, None, f"Lỗi HTTP {e.code} từ nhà cung cấp AI: {err_msg[:300]}"
    except (urllib.error.URLError, TimeoutError) as e:
        err_str = str(e)
        if "timed out" in err_str.lower() or isinstance(e, TimeoutError):
            return False, None, f"Quá thời gian chờ (Timeout {timeout}s) khi kết nối tới AI. Vui lòng tăng AI_TIMEOUT trong .env hoặc thử lại."
        return False, None, f"Lỗi kết nối tới nhà cung cấp AI: {err_str}"
    except json.JSONDecodeError as e:
        return False, None, f"Không thể giải mã JSON từ kết quả AI: {str(e)}"
    except Exception as e:
        return False, None, f"Lỗi xử lý gọi AI: {str(e)}"
