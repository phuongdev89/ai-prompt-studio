import json
import re
from typing import Dict, Any, List, Tuple, Optional

from app.services.label_mapping import LABEL_MAPPING, format_label, format_field_label, detect_primary_fields

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
        fields = detect_primary_fields(fields)
    else:
        fields = [
            {"path": "title", "key": "title", "label": "Tiêu đề Prompt", "value": title, "type": "text", "is_list": False, "is_primary": True},
            {"path": "prompt_content", "key": "prompt_content", "label": "Nội dung câu lệnh (Prompt)", "value": content, "type": "textarea", "is_list": False, "is_primary": True}
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
