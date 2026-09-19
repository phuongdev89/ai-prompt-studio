import json
import ssl
import re
import urllib.request
import urllib.error
from typing import Dict, Any, Tuple, List, Optional, Set
from app.config import get_ai_config
from app.services.label_mapping import detect_primary_fields

SYSTEM_PROMPT_PRIMARY_SUGGESTER = """Bạn là một Chuyên gia Cấp cao về Prompt Engineering và Tối ưu hóa Tham số AI (AI Parameter Form Architect).
Nhiệm vụ của bạn là phân tích một câu lệnh prompt và danh sách các trường thuộc tính (fields) của nó, sau đó chọn ra các "THUỘC TÍNH CHÍNH" (Primary Attributes) mà người dùng cần tương tác trực tiếp.

TIÊU CHÍ XÁC ĐỊNH THUỘC TÍNH CHÍNH:
1. Những trường người sử dụng CẦN TRUYỀN NỘI DUNG VÀO (User Inputs):
   - Nhập chủ đề (topic), tên sản phẩm (product_name), đối tượng mục tiêu (target_audience), nỗi đau (pain_point), giải pháp (solution), câu hook, lời kêu gọi hành động (CTA)...
   - Đối tượng chụp/vẽ (subject/character/description), trang phục (outfit/wardrobe), tư thế (pose), biểu cảm (expression), bối cảnh/địa điểm (location/setting/environment)...
   - Đặc biệt ưu tiên các trường nằm trong các nhóm biến như input_parameters, dynamic_input_variables hoặc các trường có giá trị mẫu dạng placeholder: [tên sản phẩm], <chủ đề>, {từ khóa}...
2. Những trường người sử dụng PHẢI LỰA CHỌN GIÁ TRỊ (User Choices / Select Options):
   - Tỉ lệ khung hình (aspect_ratio), góc máy (camera_angle), ánh sáng (lighting), phong cách nghệ thuật (style / aesthetic / genre), nền tảng mục tiêu (platform / target_platform), tông điệu (tone_of_voice), bố cục (layout)...

TUYỆT ĐỐI KHÔNG ĐƯỢC CHỌN:
- Các trường kỹ thuật / cấu hình cố định mà người dùng thông thường không thay đổi: instructions, reference_instructions, anti_patterns, negative_prompt, render_engine, version, iso, shutter_speed, focal_length, sensor, print_readiness...
- Các phân cảnh lặp lại chi tiết trong storyboard hoặc shot list (như panel_2, panel_3, ... panel_25).

SỐ LƯỢNG TRƯỜNG CHỌN:
- Chọn từ 3 đến 8 trường cốt lõi và hữu ích nhất để người dùng tinh chỉnh nhanh trên giao diện.

ĐỊNH DẠNG TRẢ VỀ:
BẮT BUỘC chỉ trả về DUY NHẤT một khối JSON hợp lệ theo định dạng sau (không giải thích thêm):
{
  "selected_field_ids": [123, 456, 789]
}
"""

def call_ai_suggest_primary_fields(
    prompt: Dict[str, Any],
    fields: List[Dict[str, Any]],
    provider: Optional[str] = None
) -> Tuple[bool, List[Dict[str, Any]], str]:
    """
    Gọi AI phân tích ngữ cảnh prompt và danh sách fields để gợi ý các thuộc tính chính.
    Nếu AI gọi thành công -> đánh dấu theo AI.
    Nếu AI lỗi/timeout -> fallback mượt mà sang bộ quy tắc thuật toán (heuristic).
    Trả về (success, fields_with_is_primary_updated, message).
    """
    if not fields:
        return True, fields, "Prompt không có trường tham số nào."

    cfg = get_ai_config()
    active_provider = (provider or cfg.get("provider") or "openai").strip().lower()

    # Chuẩn bị danh sách trường ứng viên gọn gàng
    candidate_fields = []
    for f in fields:
        val_str = str(f.get("value") or "")
        candidate_fields.append({
            "id": f.get("id"),
            "key": f.get("key"),
            "label": f.get("label"),
            "path": f.get("path"),
            "value": val_str[:120] if len(val_str) > 120 else val_str
        })

    user_message = f"""PROMPT CẦN PHÂN TÍCH:
- ID: {prompt.get('id')}
- Tiêu đề: {prompt.get('title')}
- Danh mục: {prompt.get('category', 'image')}
- Nội dung tóm tắt: {str(prompt.get('prompt_code') or prompt.get('raw_content') or '')[:300]}

DANH SÁCH TẤT CẢ CÁC TRƯỜNG THAM SỐ ({len(fields)} trường):
{json.dumps(candidate_fields, ensure_ascii=False, indent=2)}
"""

    selected_ids: Optional[Set[int]] = None
    ai_source_name = ""

    # 1. Thử gọi AI trực tiếp
    try:
        ai_text, ai_source_name = _call_openai_suggester(user_message, cfg)

        if ai_text:
            selected_ids = _parse_ai_selected_ids(ai_text, fields)
    except Exception as e:
        print(f"[!] AI Primary Suggester error: {e}. Falling back to rule-based algorithm.")

    # 2. Nếu AI trả về kết quả hợp lệ
    if selected_ids and len(selected_ids) > 0:
        for f in fields:
            f["is_primary"] = bool(f.get("id") in selected_ids)
        return True, fields, f"AI ({ai_source_name}) đã phân tích ngữ cảnh & đánh dấu {len(selected_ids)} thuộc tính chính! ⭐"

    # 3. Fallback sang thuật toán quy tắc cục bộ nếu AI không phản hồi
    fallback_fields = detect_primary_fields(fields, category=prompt.get("category", "image"), min_primary=3, max_primary=8)
    primary_count = sum(1 for f in fallback_fields if f.get("is_primary"))
    return True, fallback_fields, f"Hệ thống đã phân tích cấu trúc & đánh dấu {primary_count} thuộc tính chính! ⭐"

def _call_openai_suggester(user_content: str, cfg: Dict[str, Any]) -> Tuple[str, str]:
    api_key = cfg.get("api_key", "").strip()
    base_url = cfg.get("base_url", "https://api.openai.com/v1").strip()
    model_name = cfg.get("chat_model") or cfg.get("model_name") or "gpt-4o-mini"
    timeout = min(cfg.get("timeout", 60), 60)

    if not api_key:
        raise ValueError("Chưa cấu hình AI_API_KEY trong tệp .env")

    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_PRIMARY_SUGGESTER},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.2,
        "stream": False
    }

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers
    )
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="ignore"))
        choices = data.get("choices", [])
        if not choices:
            raise ValueError("Mô hình AI phản hồi rỗng")
        content = choices[0].get("message", {}).get("content", "").strip()
        return content, model_name


def _parse_ai_selected_ids(ai_text: str, fields: List[Dict[str, Any]]) -> Optional[Set[int]]:
    """
    Bóc tách danh sách ID hoặc PATH được AI chọn từ phản hồi văn bản.
    """
    if not ai_text:
        return None

    clean_text = ai_text.strip()
    # Loại bỏ code block markdown ```json ... ```
    clean_text = re.sub(r'^```(?:json)?\s*', '', clean_text, flags=re.MULTILINE)
    clean_text = re.sub(r'```\s*$', '', clean_text, flags=re.MULTILINE)
    clean_text = clean_text.strip()

    valid_field_ids = {f["id"]: f for f in fields if "id" in f}
    valid_paths = {str(f.get("path") or "").lower(): f["id"] for f in fields if "id" in f and f.get("path")}

    selected: Set[int] = set()

    # Thử parse JSON
    try:
        parsed = json.loads(clean_text)
        if isinstance(parsed, dict):
            # Nhận selected_field_ids hoặc primary_fields hoặc ids
            raw_ids = parsed.get("selected_field_ids") or parsed.get("ids") or parsed.get("selected_ids") or parsed.get("primary_field_ids")
            if isinstance(raw_ids, list):
                for item in raw_ids:
                    if isinstance(item, int) and item in valid_field_ids:
                        selected.add(item)
                    elif isinstance(item, str) and item.isdigit() and int(item) in valid_field_ids:
                        selected.add(int(item))

            # Hoặc nhận selected_paths
            raw_paths = parsed.get("selected_paths") or parsed.get("paths")
            if isinstance(raw_paths, list):
                for p in raw_paths:
                    p_lower = str(p).strip().lower()
                    if p_lower in valid_paths:
                        selected.add(valid_paths[p_lower])
        elif isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, int) and item in valid_field_ids:
                    selected.add(item)
                elif isinstance(item, str) and item.isdigit() and int(item) in valid_field_ids:
                    selected.add(int(item))
                elif isinstance(item, str) and item.lower() in valid_paths:
                    selected.add(valid_paths[item.lower()])
    except Exception:
        # Dùng regex tìm mảng số nguyên
        matches = re.findall(r'\b\d{4,6}\b', clean_text)
        for m in matches:
            mid = int(m)
            if mid in valid_field_ids:
                selected.add(mid)

    return selected if len(selected) > 0 else None
