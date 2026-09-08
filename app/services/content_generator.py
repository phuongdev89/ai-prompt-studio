import json
import ssl
import urllib.request
import urllib.error
from typing import Dict, Any, Tuple, Optional
from app.config import get_ai_config

SYSTEM_PROMPT_CONTENT_GENERATOR = """Bạn là một Chuyên gia Sáng tạo Nội dung AI (Senior AI Content Creator / Copywriter).
Nhiệm vụ của bạn là: Dựa trên câu lệnh prompt và các thông số được cung cấp, hãy viết và tạo ra nội dung (content) hoàn chỉnh, chất lượng cao, đúng định dạng, thu hút và đáp ứng xuất sắc mục tiêu.

YÊU CẦU:
1. Nếu prompt là kịch bản video: Hãy viết rõ phân cảnh, thời lượng, lời thoại, hành động, biểu cảm, âm thanh và góc quay.
2. Nếu prompt là bài viết SEO / Blog: Hãy viết cấu trúc chuẩn với H1, H2, H3, mở bài thu hút, luận điểm mạch lạc và kết bài có Call-to-action (CTA).
3. Nếu prompt là bài đăng mạng xã hội / quảng cáo: Hãy tối ưu hook mở đầu, câu chữ ngắn gọn, giàu cảm xúc, có hashtag và kêu gọi hành động rõ ràng.
4. Trả về định dạng Markdown rõ ràng, đẹp mắt, có tiêu đề và gạch đầu dòng trực quan.
5. Không giải thích dông dài về cách bạn làm, hãy tập trung vào xuất bản trực tiếp toàn bộ nội dung thành phẩm.
"""

def call_ai_generate_content(
    prompt_text: Optional[str] = None,
    provider: Optional[str] = None,
    extra_instruction: Optional[str] = None,
    prompt: Optional[str] = None
) -> Tuple[bool, str, str]:
    """
    Gửi prompt tới AI (OpenAI hoặc Google Gemini) để sinh nội dung content.
    Trả về (success, generated_content, message).
    """
    actual_prompt = (prompt_text or prompt or "").strip()
    cfg = get_ai_config()
    active_provider = (provider or cfg.get("provider") or "openai").strip().lower()

    user_message = f"Dưới đây là câu lệnh prompt nội dung cần bạn thực hiện:\n\n```\n{actual_prompt}\n```"
    if extra_instruction and extra_instruction.strip():
        user_message += f"\n\nYêu cầu bổ sung từ người dùng:\n{extra_instruction.strip()}"

    if active_provider == "gemini":
        return _call_gemini_content(user_message, cfg)
    else:
        return _call_openai_content(user_message, cfg)

def _call_gemini_content(user_content: str, cfg: Dict[str, Any]) -> Tuple[bool, str, str]:
    api_key = cfg.get("gemini_api_key", "").strip()
    model_name = cfg.get("gemini_chat_model", "gemini-2.0-flash") or "gemini-2.0-flash"
    timeout = cfg.get("timeout", 120)

    if not api_key:
        return False, "", "Chưa cấu hình GEMINI_API_KEY trong tệp .env."

    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    payload = {
        "system_instruction": {
            "parts": [{"text": SYSTEM_PROMPT_CONTENT_GENERATOR}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_content}]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 4096
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
                return False, "", "Google Gemini không trả về nội dung nào."

            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                return False, "", "Google Gemini phản hồi rỗng."

            text_out = parts[0].get("text", "").strip()
            return True, text_out, f"Tạo content thành công qua Google Gemini ({model_name})"
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        return False, "", f"Lỗi HTTP {e.code} từ Google Gemini API: {err_msg[:300]}"
    except Exception as e:
        return False, "", f"Lỗi kết nối tới Google Gemini: {str(e)}"

def _call_openai_content(user_content: str, cfg: Dict[str, Any]) -> Tuple[bool, str, str]:
    api_key = cfg.get("api_key", "").strip()
    base_url = cfg.get("base_url", "https://api.openai.com/v1").strip()
    model_name = cfg.get("chat_model") or cfg.get("model_name") or "gpt-4o-mini"
    timeout = cfg.get("timeout", 180)

    if not api_key:
        return False, "", "Chưa cấu hình AI_API_KEY trong tệp .env. Vui lòng kiểm tra lại tệp .env."

    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_CONTENT_GENERATOR},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.7,
        "stream": False
    }

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers
        )
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            choices = data.get("choices", [])
            if not choices:
                return False, "", "Không nhận được phản hồi từ mô hình AI."

            content = choices[0].get("message", {}).get("content", "").strip()
            return True, content, f"Tạo content thành công qua AI ({model_name})"
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        return False, "", f"Lỗi HTTP {e.code} từ AI API: {err_msg[:300]}"
    except Exception as e:
        return False, "", f"Lỗi kết nối tới AI Provider: {str(e)}"
