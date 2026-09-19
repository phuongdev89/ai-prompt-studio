import json
import re
import ssl
import urllib.request
import urllib.error
from typing import Dict, Any, Tuple
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
Reference Locking: If a reference image is provided, you MUST strictly lock the character identity (face geometry, hairline, eye structure, distinguishing skin markers). Set reference_image_analysis.reference_provided to true and map corresponding object nodes to the reference subject ID. If no reference is provided, set reference_provided to false and sub-fields to null.
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
    # 1. Remove <think> ... </think> tags from thinking models (DeepSeek-R1, Gemini Thinking, etc.)
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

def call_gemini_convert_to_json(raw_text: str, cfg: Dict[str, Any], reference_image_base64: str = None) -> Tuple[bool, Any, str]:
    api_key = cfg.get("gemini_api_key", "").strip()
    if not api_key:
        return False, None, "Chưa cấu hình GEMINI_API_KEY trong tệp .env. Vui lòng nhập API key của Google Gemini vào .env."

    model_name = cfg.get("gemini_chat_model", "gemini-2.0-flash")
    timeout = cfg.get("timeout", 300)
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

    # Prepare parts for user message
    user_parts = []
    user_parts.append({"text": f"Analyze and convert this visual information into a comprehensive, deeply structured, high-fidelity JSON object retaining 100% of all details, parameters, rules, and sub-panel breakdowns. Context/raw prompt (if any):\n\n{raw_text}"})

    if reference_image_base64:
        b64_pure = reference_image_base64
        mime_type = "image/png"
        if reference_image_base64.startswith("data:"):
            hdr, b64_pure = reference_image_base64.split(",", 1)
            if "image/jpeg" in hdr or "image/jpg" in hdr:
                mime_type = "image/jpeg"
            elif "image/webp" in hdr:
                mime_type = "image/webp"
        user_parts.append({
            "inline_data": {
                "mime_type": mime_type,
                "data": b64_pure
            }
        })

    payload = {
        "system_instruction": {
            "parts": [{"text": SYSTEM_PROMPT}]
        },
        "contents": [
            {
                "role": "user",
                "parts": user_parts
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            candidates = data.get("candidates", [])
            if not candidates:
                return False, None, "Google Gemini không trả về kết quả nào."
            
            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                return False, None, "Google Gemini phản hồi rỗng."
            
            raw_text_out = parts[0].get("text", "").strip()
            cleaned = clean_json_response(raw_text_out)
            parsed_json = json.loads(cleaned)
            return True, parsed_json, f"Chuyển đổi thành công qua Google Gemini ({model_name})"
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        return False, None, f"Lỗi HTTP {e.code} từ Google Gemini API: {err_msg[:300]}"
    except Exception as e:
        return False, None, f"Lỗi kết nối tới Google Gemini: {str(e)}"

def call_ai_convert_to_json(raw_text: str, provider: str = None, reference_image_base64: str = None) -> Tuple[bool, Any, str]:
    cfg = get_ai_config()
    active_provider = (provider or cfg.get("provider") or "openai").lower()

    if active_provider == "gemini":
        return call_gemini_convert_to_json(raw_text, cfg, reference_image_base64)

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
