import json
import re
import ssl
import urllib.request
import urllib.error
from typing import Dict, Any, Tuple
from app.config import get_ai_config
from app.services.parser import extract_flat_fields

SYSTEM_PROMPT = """You are a World-Class AI Prompt Engineering & Structured Data Architect.
Your mission is to analyze unstructured, raw prompt descriptions (in Vietnamese, English, or any language) for generative AI (Midjourney, Flux, Stable Diffusion, Sora, etc.) and convert them into a Rich, Deeply Hierarchical, High-Fidelity JSON Schema.

### CORE PRINCIPLES:
1. **DEEP HIERARCHICAL DECOMPOSITION (Bóc tách phân tầng sâu)**:
   - NEVER collapse or compress complex descriptions into a single flat string.
   - Dynamically create structured nested objects and sub-properties matching the domains described in the raw prompt (e.g., `project_metadata`, `layout`, `subject_identity_lock` or `subject`, `environment`, `wardrobe`, `poses_grid` or `poses`, `anatomy_and_textures`, `lighting`, `camera_settings`, `quality_specs`, `negative_prompt`, `mandatory_output_criteria`).
   - Break multiple items, tags, or options into clean JSON arrays (e.g., `genre_and_style: [...]`, `color_palette: [...]`, `negative_prompt: [...]`).
   - Deconstruct complex panels/shots into keyed sub-objects (e.g., `poses_grid: {"panel_1": "...", "panel_2": "..."}`).
   - Deconstruct technical camera/lighting into precise parameters (e.g., `focal_length`, `aperture`, `iso`, `shutter_speed`, `color_temperature`, etc.).

2. **100% DETAIL & FIDELITY RETENTION (Giữ trọn vẹn 100% chi tiết, không tóm tắt hay làm ngắn)**:
   - Preserve every nuance: exact numbers, anatomical constraints, optical physics, material textures, camera models, shutter speeds, Kelvins, negative rules, and composition instructions.
   - Translate accurately into professional AI prompt engineering terminology in English.

3. **DYNAMIC SCHEMA ADAPTABILITY**:
   - For grid/storyboard prompts: break down each panel explicitly in `poses_grid` / `layout`.
   - For character / portrait prompts: detail identity lock, anatomy, textures, expressions, wardrobe.
   - For cinematic / video / product prompts: structure camera movements, scene physics, lighting, and materials.
   - Always extract `aspect_ratio` if mentioned (e.g. "9:16", "16:9", "1:1", "4:5", etc.).
   - Always format `negative_prompt` as a clean, granular array of prohibited elements.

4. **OUTPUT FORMAT**:
   - Output ONLY 1 valid, parseable JSON object.
   - NO markdown formatting (no ```json ... ```), NO commentary."""

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

def call_gemini_convert_to_json(raw_text: str, cfg: Dict[str, Any]) -> Tuple[bool, Any, str]:
    api_key = cfg.get("gemini_api_key", "").strip()
    if not api_key:
        return False, None, "Chưa cấu hình GEMINI_API_KEY trong tệp .env. Vui lòng nhập API key của Google Gemini vào .env."

    model_name = cfg.get("gemini_chat_model", "gemini-2.0-flash")
    timeout = cfg.get("timeout", 300)
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

    payload = {
        "system_instruction": {
            "parts": [{"text": SYSTEM_PROMPT}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": f"Analyze and convert this raw prompt into a comprehensive, deeply structured, high-fidelity JSON object retaining 100% of all details, parameters, rules, and sub-panel breakdowns:\n\n{raw_text}"}]
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

def call_ai_convert_to_json(raw_text: str, provider: str = None) -> Tuple[bool, Any, str]:
    cfg = get_ai_config()
    active_provider = (provider or cfg.get("provider") or "openai").lower()
    
    if active_provider == "gemini":
        return call_gemini_convert_to_json(raw_text, cfg)

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

    payload = {
        "model": model_name or "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Analyze and convert this raw prompt into a comprehensive, deeply structured, high-fidelity JSON object retaining 100% of all details, parameters, rules, and sub-panel breakdowns:\n\n{raw_text}"}
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
