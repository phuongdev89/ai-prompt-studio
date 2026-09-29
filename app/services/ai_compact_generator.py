import json
import re
import ssl
import urllib.request
import urllib.error
from typing import Dict, Any, Tuple, Optional
from app.config import get_ai_config
from app.services.ai_converter import parse_chat_response

SYSTEM_PROMPT_COMPACT_PROMPT = """Bạn là chuyên gia Prompt Engineering hàng đầu thế giới.
Nhiệm vụ: Chuyển đổi câu lệnh prompt đầu vào (văn bản dài, kịch bản, hoặc cấu trúc JSON) thành một câu lệnh prompt DUY NHẤT, TỐI GIẢN, SÚC TÍCH, CÔ ĐỌNG DƯỚI 1000 KÝ TỰ.

QUY TẮC BẮT BUỘC:
1. ĐỘ DÀI: Tổng số ký tự TUYỆT ĐỐI PHẢI DƯỚI 1000 KÝ TỰ (lý tưởng trong khoảng 400 - 850 ký tự).
2. GIỮ NGUYÊN BẢN CHẤT CỐT LÕI:
   - Với prompt tạo ảnh (Midjourney / Stable Diffusion / Flux / DALL-E): Giữ nhân vật/chủ thể chính, trang phục, bối cảnh, ánh sáng, góc máy, bảng màu, phong cách nghệ thuật và mood quan trọng nhất. Loại bỏ các key JSON rườm rà, các mô tả thừa thãi lặp lại.
   - Với prompt nội dung/video (Content): Giữ chủ đề chính, mục tiêu, đối tượng người xem, giọng văn (tone of voice), và cấu trúc cốt lõi.
3. NGÔN NGỮ & PHONG CÁCH:
   - Nếu prompt gốc dùng tiếng Anh (đặc biệt là prompt vẽ ảnh AI), hãy viết prompt tối giản bằng tiếng Anh mạch lạc, các từ khóa phân cách bằng dấu phẩy hoặc câu văn ngắn chuẩn phong cách Midjourney / Flux.
   - Nếu prompt gốc là tiếng Việt, giữ nguyên tiếng Việt súc tích, chỉn chu.
4. ĐỊNH DẠNG ĐẦU RA - CỰC KỲ QUAN TRỌNG:
   - CHỈ XUẤT RA DUY NHẤT CÂU LỆNH PROMPT TỐI GIẢN ĐỂ NGƯỜI DÙNG COPY CHẠY NGAY.
   - TUYỆT ĐỐI KHÔNG thêm bất kỳ câu giải thích nào (KHÔNG thêm "Lý do:", KHÔNG thêm "Bỏ:", KHÔNG thêm nhận xét, KHÔNG chào hỏi).
   - KHÔNG bọc trong markdown code block (không dùng ```).
"""

def call_ai_generate_compact_prompt(
    prompt_text: str,
    category: str = "image"
) -> Tuple[bool, str, str]:
    """
    Gọi AI sinh prompt tối giản dưới 1000 ký tự.
    Trả về (success, compact_prompt, message).
    """
    clean_text = (prompt_text or "").strip()
    if not clean_text:
        return False, "", "Nội dung prompt trống."

    cfg = get_ai_config()
    api_key = cfg.get("api_key", "").strip()
    base_url = cfg.get("base_url", "https://api.openai.com/v1").strip()
    model_name = cfg.get("chat_model") or cfg.get("model_name") or "gpt-4o-mini"
    timeout = cfg.get("timeout", 180)
    use_stream = cfg.get("stream", True)

    if not api_key:
        return False, "", "Chưa cấu hình AI_API_KEY trong tệp .env."

    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    user_instruction = (
        f"Dưới đây là câu lệnh prompt gốc (Category: {category}).\n"
        f"Hãy chuyển đổi và tối giản nó thành prompt siêu cô đọng, chất lượng cao với độ dài tối đa 1000 ký tự:\n\n"
        f"{clean_text}"
    )

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_COMPACT_PROMPT},
            {"role": "user", "content": user_instruction}
        ],
        "temperature": 0.4,
        "max_tokens": 700,
        "stream": use_stream
    }

    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(endpoint, data=req_data, headers=headers, method="POST")

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            resp_body = resp.read().decode("utf-8", errors="ignore")
            compact_text = parse_chat_response(resp_body).strip()
            if not compact_text:
                return False, "", "AI không trả về nội dung."

            # 1. Loại bỏ thinking tags <think>...</think>
            compact_text = re.sub(r"<think>[\s\S]*?</think>", "", compact_text, flags=re.IGNORECASE).strip()

            # 2. Loại bỏ code block markdown nếu có
            compact_text = re.sub(r"^```(?:prompt|text|markdown|json)?\s*", "", compact_text, flags=re.IGNORECASE)
            compact_text = re.sub(r"\s*```$", "", compact_text)
            compact_text = compact_text.strip()

            # 3. Loại bỏ phần giải thích/nhận xét thừa nếu AI tự ý thêm ở cuối
            compact_text = re.sub(r"(?i)\n+(?:lý do|giải thích|lưu ý|ghi chú|note|explanation|bỏ):\s*[\s\S]*$", "", compact_text).strip()

            # 4. Đảm bảo nghiêm ngặt <= 1000 ký tự
            if len(compact_text) > 1000:
                compact_text = compact_text[:997].rsplit(" ", 1)[0] + "..."

            return True, compact_text, "Thành công"

    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        return False, "", f"Lỗi HTTP {e.code} từ AI: {err_msg[:200]}"
    except Exception as e:
        return False, "", f"Lỗi kết nối AI: {str(e)}"
