import json
import re
import ssl
import urllib.request
import urllib.error
from typing import Dict, Any, Tuple
from app.config import get_ai_config
from app.services.ai_converter import parse_chat_response, clean_json_response

VIDEO_SCRIPT_SYSTEM_PROMPT = """ROLE & OBJECTIVE:
Bạn là ScriptVision AI - Chuyên gia phân tích kịch bản video ngắn (TikTok, Reels, Shorts) và đạo diễn điện ảnh AI hàng đầu thế giới.
Nhiệm vụ của bạn là tiếp nhận văn bản thô, ý tưởng, hoặc câu lệnh video thô của người dùng và phân tích thành một kịch bản phân cảnh điện ảnh chi tiết, chặt chẽ, tối ưu cho các mô hình tạo video AI (Kling, Hailuo, Sora, Runway, Seedance).

QUY TẮC PHÂN TÍCH:
1. Nhận diện thể loại kịch bản:
   Ví dụ: "Nói lời đạo lý", "Biến hình / Lột xác", "KOC Review sản phẩm", "Tình huống hài hước / Hất nước đá", "POV Storytelling",...
2. Tách rõ từng phân cảnh (Cảnh 1, Cảnh 2, ...):
   - Phân tích số cảnh phù hợp theo cấu trúc kịch bản (thường 2-4 cảnh cho video ngắn 15s-60s).
3. Trong TỪNG CẢNH, BẮT BUỘC phân tích và trích xuất đủ các yếu tố:
   - scene_number: Thứ tự cảnh (1, 2, ...)
   - title: Tiêu đề cảnh (VD: "Giao diện nàng thơ nói lời đạo lý", "Cú chốt phũ phàng vỡ nát hình tượng")
   - dialogue: Lời thoại chính xác từng từ của nhân vật (để trong ngoặc kép). Nếu không thoại ghi "Không thoại".
   - action: Hành động và biểu cảm chi tiết của diễn viên (nụ cười, ánh mắt, khóe môi, chuyển động đầu, ngôn ngữ cơ thể, tương tác với đạo cụ).
   - camera: Góc máy điện ảnh chi tiết (tiêu cự lens, góc quay: Medium shot, Extreme close-up, Dolly zoom, Eye-level, Dutch angle, ánh sáng cinematic: soft warm light, dramatic rim light...).
   - prompt: Prompt video hoàn chỉnh tổng hợp cả 3 yếu tố trên (mô tả ngoại hình/nhân vật + hành động & biểu cảm sắc nét + góc máy điện ảnh + ánh sáng + không khí), sẵn sàng để copy paste 1 chạm vào các AI video generator.

ĐỊNH DẠNG ĐẦU RA (BẮT BUỘC):
Trả về duy nhất một khối mã JSON chuẩn trong ```json ... ```:
{
  "script_type": "Tên thể loại kịch bản (VD: Nói lời đạo lý)",
  "total_scenes": 2,
  "summary": "Tóm tắt ngắn gọn 1 câu về kịch bản",
  "scenes": [
    {
      "scene_number": 1,
      "title": "Giao diện nàng thơ nói lời đạo lý",
      "dialogue": "Những người lười biếng mà còn hay ra vẻ ta đây á, là những người đó họ có rất là nhiều ước mơ.",
      "action": "Mở đầu giữ nguyên nụ cười mỉm dịu dàng, mơ màng. Ánh mắt thanh tú nhìn thẳng ống kính đầy cuốn hút như đang tâm tình. Khẩu hình miệng nhép nhẹ nhàng, từ tốn. Khi nói đến 'rất là nhiều ước mơ', đôi mắt chớp nhẹ đầy vẻ trân trọng và thấu hiểu.",
      "camera": "Medium close-up, 50mm f/1.8 lens, eye-level, soft warm cinematic lighting, shallow depth of field",
      "prompt": "Cinematic medium close-up of a graceful Vietnamese female KOC speaking gently to the camera with a gentle warm smile, delicate eye contact, natural lip movement speaking with sincere and solemn expression, 50mm f/1.8 lens, soft golden hour lighting, 8k resolution"
    }
  ]
}
"""

def format_video_script_markdown(parsed_json: Dict[str, Any]) -> str:
    script_type = parsed_json.get("script_type") or "Video Phân Cảnh"
    total_scenes = parsed_json.get("total_scenes") or len(parsed_json.get("scenes", []))
    summary = parsed_json.get("summary") or ""
    scenes = parsed_json.get("scenes", [])

    lines = []
    lines.append(f"# Kịch bản: {script_type} ({total_scenes} cảnh)")
    if summary:
        lines.append(f"> {summary}\n")

    for s in scenes:
        num = s.get("scene_number", 1)
        title = s.get("title", f"Cảnh {num}")
        dialogue = s.get("dialogue", "")
        action = s.get("action", "")
        camera = s.get("camera", "")
        prompt = s.get("prompt", "")

        lines.append(f"## Cảnh {num}: {title}")
        if dialogue:
            lines.append(f"- **Lời thoại**: \"{dialogue}\"")
        if camera:
            lines.append(f"- **Góc máy điện ảnh**: {camera}")
        if action:
            lines.append(f"- **Hành động & Biểu cảm**: {action}")
        if prompt:
            lines.append(f"- **Prompt Video AI**: `{prompt}`")
        lines.append("")

    return "\n".join(lines).strip()

def call_ai_analyze_video_script(raw_text: str, provider: str = None) -> Tuple[bool, Any, str]:
    cfg = get_ai_config()

    api_key = cfg.get("api_key")
    base_url = cfg.get("base_url")
    model_name = cfg.get("model_name")
    timeout = cfg.get("timeout", 300)
    use_stream = cfg.get("stream", True)

    if not api_key:
        return False, None, "Chưa cấu hình AI_API_KEY trong tệp .env. Vui lòng kiểm tra lại tệp .env."

    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    user_prompt = (
        f"Hãy phân tích văn bản kịch bản / ý tưởng video sau đây thành kịch bản phân cảnh điện ảnh chi tiết theo đúng format JSON quy định:\n\n"
        f"{raw_text}"
    )

    payload = {
        "model": model_name or "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": VIDEO_SCRIPT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.3,
        "stream": use_stream
    }

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
            raw_body = response.read().decode("utf-8")
            content = parse_chat_response(raw_body)
            clean_str = clean_json_response(content)

            try:
                parsed_json = json.loads(clean_str)
                return True, parsed_json, "Phân tích kịch bản thành công"
            except Exception as e:
                return False, None, f"Không thể phân tích kết quả JSON từ AI: {e}\nNội dung AI trả về:\n{content[:500]}"

    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8") if e.fp else str(e)
        return False, None, f"Lỗi HTTP từ API AI ({e.code}): {err_msg}"
    except Exception as e:
        return False, None, f"Lỗi kết nối tới API AI: {str(e)}"
