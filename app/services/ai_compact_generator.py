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
3. YÊU CẦU ẢNH THAM CHIẾU (NẾU PROMPT GỐC CÓ ẢNH THAM CHIẾU HOẶC ĐƯỢC CHỈ ĐỊNH):
   - BẮT BUỘC phải đưa yêu cầu ảnh tham chiếu vào câu lệnh tối giản sử dụng chính xác token `[ATTACHED_PHOTO]`.
   - Cú pháp đề xuất:
     + Định dạng Midjourney: Thêm thông số `--cref [ATTACHED_PHOTO]` (hoặc `--cw 100`).
     + Định dạng câu văn mô tả: "Subject facial identity and appearance strictly matching [ATTACHED_PHOTO]" hoặc "Preserve facial identity and features from [ATTACHED_PHOTO]".
   - TUYỆT ĐỐI KHÔNG dùng tên tệp giả lập như image_0.png, image_1.jpg, <IMAGE 0>, hay cụm từ chung chung. Luôn dùng chính xác token `[ATTACHED_PHOTO]`.
4. NGÔN NGỮ & PHONG CÁCH:
   - Nếu prompt gốc dùng tiếng Anh (đặc biệt là prompt vẽ ảnh AI), hãy viết prompt tối giản bằng tiếng Anh mạch lạc, các từ khóa phân cách bằng dấu phẩy hoặc câu văn ngắn chuẩn phong cách Midjourney / Flux.
   - Nếu prompt gốc là tiếng Việt, giữ nguyên tiếng Việt súc tích, chỉn chu.
5. ĐỊNH DẠNG ĐẦU RA - CỰC KỲ QUAN TRỌNG:
   - CHỈ XUẤT RA DUY NHẤT CÂU LỆNH PROMPT TỐI GIẢN ĐỂ NGƯỜI DÙNG COPY CHẠY NGAY.
   - TUYỆT ĐỐI KHÔNG thêm bất kỳ câu giải thích nào (KHÔNG thêm "Lý do:", KHÔNG thêm "Bỏ:", KHÔNG thêm nhận xét, KHÔNG chào hỏi).
   - KHÔNG bọc trong markdown code block (không dùng ```).
"""

def is_reference_required(prompt: Optional[Dict[str, Any]] = None, text: str = "") -> bool:
    """
    Xác định xem prompt có bắt buộc phải sử dụng ảnh tham chiếu hay không.
    """
    if prompt:
        if bool(prompt.get("requires_reference")):
            return True
        if (prompt.get("category") or "").strip().lower() == "image":
            return True

    check_text = text or ""
    if prompt:
        check_text += " " + (prompt.get("prompt_code") or "") + " " + (prompt.get("raw_content") or "") + " " + (prompt.get("original_raw_content") or "")
        if prompt.get("parsed_json"):
            try:
                check_text += " " + json.dumps(prompt.get("parsed_json"), ensure_ascii=False)
            except Exception:
                pass

    check_lower = check_text.lower()
    ref_indicators = [
        "[attached_photo]",
        "reference_image_dependency",
        "primary_subject_reference",
        "reference_dependencies",
        "facial_extraction_details",
        "ảnh tham chiếu",
        "anh tham chieu",
        "ảnh mẫu",
        "anh mau",
        "input source image",
        "uploaded input source",
        "uploaded image",
        "--cref",
    ]
    return any(indicator in check_lower for indicator in ref_indicators)

def sanitize_compact_reference_tokens(text: str) -> str:
    """
    Chuẩn hóa mọi token hoặc tên tệp ảnh tham chiếu thành [ATTACHED_PHOTO].
    """
    if not text:
        return ""
    text = re.sub(r'(?i)<image[\s_]*\d+>', '[ATTACHED_PHOTO]', text)
    text = re.sub(r'(?i)\b(?:image|img|photo)[\s_]*\d+\.(?:png|jpg|jpeg|webp)\b', '[ATTACHED_PHOTO]', text)
    text = re.sub(r'(?i)ảnh\s*tham\s*chiếu(?:\s*tải\s*lên)?', '[ATTACHED_PHOTO]', text)
    return text

def truncate_preserving_token(text: str, token: str = "[ATTACHED_PHOTO]", max_len: int = 1000) -> str:
    """
    Cắt ngắn văn bản đảm bảo <= max_len ký tự và không làm mất token bắt buộc.
    """
    if len(text) <= max_len:
        return text

    if token not in text:
        return text[:max_len - 3].rsplit(" ", 1)[0] + "..."

    parts = text.split(token)
    suffix = token + parts[-1]

    allowed_prefix_len = max_len - len(suffix) - 4
    if allowed_prefix_len > 50:
        prefix = text[:allowed_prefix_len].rsplit(" ", 1)[0] + "..."
        return f"{prefix} {suffix}"
    else:
        base = text.replace(token, "").strip()
        trimmed_base = base[:max_len - len(token) - 5].rsplit(" ", 1)[0] + "..."
        return f"{trimmed_base} {token}"

def ensure_reference_in_compact_prompt(text: str, requires_reference: bool = True) -> str:
    """
    Nếu prompt bắt buộc có ảnh tham chiếu, đảm bảo [ATTACHED_PHOTO] xuất hiện chuẩn xác và độ dài <= 1000 ký tự.
    """
    if not requires_reference or not text:
        return text

    cleaned = sanitize_compact_reference_tokens(text)

    if "[ATTACHED_PHOTO]" in cleaned:
        if len(cleaned) <= 1000:
            return cleaned
        return truncate_preserving_token(cleaned, "[ATTACHED_PHOTO]", 1000)

    # Nếu chưa có token, tự động bổ sung theo định dạng phù hợp
    if "--ar" in cleaned or "--v" in cleaned or "--s" in cleaned or "--cref" in cleaned:
        if "--cref" in cleaned:
            cleaned = re.sub(r'--cref\s+[^\s]+', '--cref [ATTACHED_PHOTO]', cleaned)
        else:
            cleaned = f"{cleaned.rstrip()} --cref [ATTACHED_PHOTO]"
    else:
        is_vietnamese = any(c in cleaned for c in "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ")
        if is_vietnamese:
            cleaned = f"{cleaned.rstrip()} (Tham chiếu nhận diện chủ thể: [ATTACHED_PHOTO])"
        else:
            cleaned = f"{cleaned.rstrip()} Reference: Strict consistency matching [ATTACHED_PHOTO]."

    if len(cleaned) > 1000:
        cleaned = truncate_preserving_token(cleaned, "[ATTACHED_PHOTO]", 1000)

    return cleaned

def call_ai_generate_compact_prompt(
    prompt_text: str,
    category: str = "image",
    requires_reference: bool = False
) -> Tuple[bool, str, str]:
    """
    Gọi AI sinh prompt tối giản dưới 1000 ký tự.
    Tự động tích hợp và bảo toàn token [ATTACHED_PHOTO] nếu requires_reference=True.
    Trả về (success, compact_prompt, message).
    """
    clean_text = (prompt_text or "").strip()
    if not clean_text:
        return False, "", "Nội dung prompt trống."

    cfg = get_ai_config()
    api_key = (cfg.get("chat_api_key") or cfg.get("api_key", "")).strip()
    base_url = (cfg.get("chat_url") or cfg.get("base_url") or "https://9router.phuonganh.io.vn/v1").strip()
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

    ref_instruction = ""
    if requires_reference:
        ref_instruction = (
            "\n* YÊU CẦU ĐẶC BIỆT BẮT BUỘC: Prompt này BẮT BUỘC sử dụng ảnh tham chiếu. "
            "Trong câu lệnh tối giản, bạn BẮT BUỘC phải đưa chỉ thị tham chiếu ảnh vào (ví dụ: 'subject identity strictly matching [ATTACHED_PHOTO]' hoặc '--cref [ATTACHED_PHOTO]') "
            "sử dụng chính xác token [ATTACHED_PHOTO].\n"
        )

    user_instruction = (
        f"Dưới đây là câu lệnh prompt gốc (Category: {category}).{ref_instruction}\n"
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

            # 4. Đảm bảo ảnh tham chiếu chuẩn xác
            if requires_reference:
                compact_text = ensure_reference_in_compact_prompt(compact_text, requires_reference=True)
            else:
                compact_text = sanitize_compact_reference_tokens(compact_text)

            # 5. Đảm bảo nghiêm ngặt <= 1000 ký tự
            if len(compact_text) > 1000:
                compact_text = truncate_preserving_token(compact_text, "[ATTACHED_PHOTO]", 1000)

            return True, compact_text, "Thành công"

    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        return False, "", f"Lỗi HTTP {e.code} từ AI: {err_msg[:200]}"
    except Exception as e:
        return False, "", f"Lỗi kết nối AI: {str(e)}"
