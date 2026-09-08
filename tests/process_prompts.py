import json
import re
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.services.label_mapping import LABEL_MAPPING, format_label, format_field_label

DATA_DIR = BASE_DIR / "data"
RAW_DATA_FILE = DATA_DIR / "raw" / "facebook_posts.json"
BACKUP_FILE = DATA_DIR / "raw" / "facebook_posts.backup.json"

def is_svg_image(img_str):
    if not isinstance(img_str, str):
        return False
    s = img_str.strip().lower()
    if 'data:image/svg' in s or 'image/svg+xml' in s:
        return True
    if s.endswith('.svg') or '.svg?' in s or '.svg#' in s:
        return True
    if s.startswith('<svg') or '%3csvg' in s or 'xmlns=\'http://www.w3.org/2000/svg\'' in s:
        return True
    return False

def filter_images(image_list):
    if not isinstance(image_list, list):
        return []
    return [img for img in image_list if isinstance(img, str) and img.strip() and not is_svg_image(img)]

def extract_flat_fields(data_obj, prefix=""):
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
                    "type": "textarea" if len(str(v)) > 60 else "text"
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



def clean_dataset(source_file=None, output_file=None):
    if source_file is None:
        source_file = BACKUP_FILE if BACKUP_FILE.exists() else RAW_DATA_FILE
    if output_file is None:
        output_file = DATA_DIR / "cleaned_prompts.json"

    with open(source_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    cleaned_items = []
    filtered_raw_posts = []
    
    total_svg_removed = 0
    total_real_images = 0

    for idx, item in enumerate(data):
        content = item.get('content', '').strip()
        raw_images = item.get('image', [])
        videos = item.get('video', [])
        
        if not content:
            continue
            
        images = filter_images(raw_images)
        total_svg_removed += (len(raw_images) - len(images))
        total_real_images += len(images)
            
        lines = [l.strip() for l in content.split('\n') if l.strip()]
        raw_title = lines[0] if lines else f"Prompt #{idx+1}"
        title = re.sub(r'^(câu lệnh|chia sẻ câu lệnh|bộ câu lệnh|prompt|lưu lại|trả câu lệnh)\s*[-:]*\s*', '', raw_title, flags=re.IGNORECASE).strip()
        if not title:
            title = raw_title
            
        # JSON detection
        s = content.find('{')
        e = content.rfind('}')
        
        parsed_json = None
        is_prompt = False
        prompt_type = "text"
        
        if s != -1 and e != -1 and e > s:
            raw_json = content[s:e+1]
            try:
                parsed_json = json.loads(raw_json)
                is_prompt = True
                prompt_type = "json"
            except Exception:
                fixed_json = re.sub(r',\s*([\}\]])', r'\1', raw_json)
                try:
                    parsed_json = json.loads(fixed_json)
                    is_prompt = True
                    prompt_type = "json"
                except Exception:
                    if any(k in raw_json.lower() for k in ['"type"', '"subject"', '"camera"', '"style"', '"prompt"', '"composition"', '"negative_prompt"', '"facial_extraction_details"', '"generation_parameters"']):
                        is_prompt = True
                        prompt_type = "json_raw"

        if not is_prompt:
            lower = content.lower()
            prompt_markers = [
                'prompt:', 'prompt :', 'positive prompt', 'negative prompt',
                'câu lệnh:', 'câu lệnh :', 'lời thoại chính xác', 'prompt biểu cảm',
                '--ar ', '8k,', 'photorealistic', 'masterpiece,', 'cinematic lighting',
                'shot on 35mm', 'dslr photo', 'lora:', 'cảnh 1:', 'cảnh 2:', 'scene 1:'
            ]
            has_marker = any(m in lower for m in prompt_markers)
            
            non_prompt_markers = [
                'đang gây chú ý tại trung quốc', 'nữ ai gây sốc khi hét giá',
                'mẹo nhỏ để hoàn thành thử thách', 'tổng hợp các dạng series',
                'xin chào mọi người, em là châu', 'có thể bạn chưa biết - video koc ai này đạt',
                'mình đã dành 2h xây dựng để bạn có thể', 'đầu tư gì cũng toang',
                'chủ đề xây kênh này đang hót', 'chào mọi người đi em', 'hôm nay đi tiệc',
                'thông báo mới ạ', 'nếu năm 2026 rồi mà bạn vẫn'
            ]
            is_reject = any(m in lower for m in non_prompt_markers)
            
            if has_marker and not is_reject and len(content) > 100:
                is_prompt = True
                prompt_type = "text"

        if is_prompt:
            flat_fields = []
            if parsed_json:
                flat_fields = extract_flat_fields(parsed_json)
            else:
                flat_fields = [
                    {"path": "title", "key": "title", "label": "Tiêu đề Prompt", "value": title, "type": "text"},
                    {"path": "prompt_content", "key": "prompt_content", "label": "Nội dung câu lệnh (Prompt)", "value": content, "type": "textarea"}
                ]
                
            cleaned_items.append({
                "id": f"prompt_{len(cleaned_items) + 1}",
                "original_index": idx,
                "title": title,
                "raw_title": raw_title,
                "prompt_type": prompt_type,
                "parsed_json": parsed_json,
                "raw_content": content,
                "prompt_code": json.dumps(parsed_json, indent=2, ensure_ascii=False) if parsed_json else (content[s:e+1] if s != -1 and e != -1 and e > s else content),
                "images": images,
                "videos": videos,
                "fields": flat_fields
            })

            filtered_raw_posts.append({
                "content": content,
                "image": images,
                "video": videos
            })
            
    print(f"Total raw posts processed: {len(data)}")
    print(f"Valid prompt items: {len(cleaned_items)}")
    print(f"Total SVG images filtered out: {total_svg_removed}")
    print(f"Total real images preserved: {total_real_images}")

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(cleaned_items, f, ensure_ascii=False, indent=2)
    print(f"Saved {output_file} successfully.")

    return cleaned_items

if __name__ == '__main__':
    clean_dataset()
