import json
import re
from typing import Dict, Any, List, Tuple, Optional

LABEL_MAPPING = {
    "project_metadata": "Thông tin dự án / Metadata",
    "subject_identity_lock": "Khóa nhận diện / Identity Lock",
    "type": "Loại bố cục / Type",
    "layout": "Bố cục / Layout",
    "environment": "Môi trường & Không gian / Environment",
    "foreground_element": "Tiền cảnh / Foreground",
    "wardrobe": "Trang phục & Phụ kiện / Wardrobe",
    "poses_grid": "Lưới tư thế / Poses Grid",
    "anatomy_and_textures": "Giải phẫu & Bề mặt / Anatomy & Textures",
    "camera_settings": "Thông số máy ảnh / Camera Specs",
    "quality_specs": "Chất lượng / Quality Specs",
    "mandatory_output_criteria": "Tiêu chí kết quả / Mandatory Criteria",
    "skin": "Làn da / Skin",
    "lips": "Đôi môi / Lips",
    "eyes": "Đôi mắt / Eyes",
    "hair": "Kiểu tóc / Hair",
    "clothing": "Trang phục / Clothing",
    "outfit": "Trang phục / Outfit",
    "pose": "Tư thế / Pose",
    "expression": "Biểu cảm / Expression",
    "camera": "Máy ảnh / Camera",
    "lens": "Ống kính / Lens",
    "lighting": "Ánh sáng / Lighting",
    "background": "Bối cảnh / Background",
    "setting": "Không gian / Setting",
    "atmosphere": "Bầu không khí / Atmosphere",
    "style": "Phong cách / Style",
    "negative_prompt": "Prompt phủ định / Negative Prompt",
    "aspect_ratio": "Tỉ lệ / Aspect Ratio",
    "gender": "Giới tính / Gender",
    "age": "Độ tuổi / Age",
    "face": "Gương mặt / Face",
    "description": "Mô tả / Description",
    "energy": "Năng lượng / Energy",
    "mood": "Tâm trạng / Mood",
    "aesthetic": "Thẩm mỹ / Aesthetic",
    "genre": "Thể loại / Genre",
    "quality": "Chất lượng / Quality",
    "resolution": "Độ phân giải / Resolution",
    "focus": "Tiêu cự / Focus",
    "instructions": "Hướng dẫn trích xuất / Instructions"
}

def format_label(key: str, full_path: str = "") -> str:
    key_lower = key.lower()
    for k_sub, v_label in LABEL_MAPPING.items():
        if k_sub == key_lower or k_sub in key_lower:
            return v_label
    return key.replace("_", " ").title()

def extract_flat_fields(data_obj: Any, prefix: str = "") -> List[Dict[str, Any]]:
    fields = []
    if isinstance(data_obj, dict):
        for k, v in data_obj.items():
            full_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, (str, int, float, bool)):
                fields.append({
                    "path": full_key,
                    "key": k,
                    "label": format_label(k, full_key),
                    "value": str(v),
                    "type": "textarea" if len(str(v)) > 60 else "text",
                    "is_list": False
                })
            elif isinstance(v, list):
                if all(isinstance(x, (str, int, float)) for x in v):
                    fields.append({
                        "path": full_key,
                        "key": k,
                        "label": format_label(k, full_key),
                        "value": ", ".join(str(x) for x in v),
                        "type": "textarea" if len(", ".join(str(x) for x in v)) > 60 else "text",
                        "is_list": True
                    })
                else:
                    for i, item in enumerate(v):
                        fields.extend(extract_flat_fields(item, f"{full_key}[{i}]"))
            elif isinstance(v, dict):
                fields.extend(extract_flat_fields(v, full_key))
    return fields

def parse_incoming_prompt(raw_content: str, raw_media: Optional[str] = None) -> Dict[str, Any]:
    content = (raw_content or "").strip()
    
    # Extract images / videos
    media_list = []
    if raw_media:
        # Split by comma or newline
        lines = re.split(r'[\r\n,]+', raw_media.strip())
        for l in lines:
            cleaned = l.strip()
            if cleaned:
                media_list.append(cleaned)

    # Check if JSON
    s = content.find('{')
    e = content.rfind('}')
    
    parsed_json = None
    prompt_type = "text"
    prompt_code = content
    
    if s != -1 and e != -1 and e > s:
        raw_json_str = content[s:e+1]
        try:
            parsed_json = json.loads(raw_json_str)
            prompt_type = "json"
            prompt_code = json.dumps(parsed_json, indent=2, ensure_ascii=False)
        except Exception:
            fixed_json = re.sub(r',\s*([\}\]])', r'\1', raw_json_str)
            try:
                parsed_json = json.loads(fixed_json)
                prompt_type = "json"
                prompt_code = json.dumps(parsed_json, indent=2, ensure_ascii=False)
            except Exception:
                pass

    # Extract title
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    raw_title = lines[0] if lines else "Prompt Mới"
    if parsed_json and isinstance(parsed_json, dict):
        if "title" in parsed_json and isinstance(parsed_json["title"], str):
            raw_title = parsed_json["title"]
        elif "prompt" in parsed_json and isinstance(parsed_json["prompt"], str):
            raw_title = parsed_json["prompt"][:60]
        elif "subject" in parsed_json and isinstance(parsed_json["subject"], str):
            raw_title = parsed_json["subject"][:60]
            
    title = re.sub(r'^(câu lệnh|chia sẻ câu lệnh|bộ câu lệnh|prompt|lưu lại|trả câu lệnh)\s*[-:]*\s*', '', raw_title, flags=re.IGNORECASE).strip()
    if not title:
        title = raw_title

    # Extract dynamic fields
    if parsed_json:
        fields = extract_flat_fields(parsed_json)
    else:
        fields = [
            {"path": "title", "key": "title", "label": "Tiêu đề Prompt", "value": title, "type": "text", "is_list": False},
            {"path": "prompt_content", "key": "prompt_content", "label": "Nội dung câu lệnh (Prompt)", "value": content, "type": "textarea", "is_list": False}
        ]

    return {
        "title": title,
        "raw_title": raw_title,
        "prompt_type": prompt_type,
        "parsed_json": parsed_json,
        "prompt_code": prompt_code,
        "raw_content": content,
        "images": media_list,
        "fields": fields
    }
