import json
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_FILE = DATA_DIR / "raw" / "facebook_posts.json"

def inspect(source_file=RAW_FILE):
    if not source_file.exists():
        print(f"File not found: {source_file}")
        return

    with open(source_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"Total raw items: {len(data)}")

    categories = {
        'json_structured': [],
        'text_structured': [],
        'not_prompt': []
    }

    for idx, item in enumerate(data):
        content = item.get('content', '').strip()
        imgs = item.get('image', [])

        if not content:
            categories['not_prompt'].append((idx, 'EMPTY CONTENT', ''))
            continue

        s_idx = content.find('{')
        e_idx = content.rfind('}')
        
        is_json_prompt = False
        parsed_json = None
        if s_idx != -1 and e_idx != -1 and e_idx > s_idx:
            json_str = content[s_idx:e_idx+1]
            try:
                parsed = json.loads(json_str)
                if isinstance(parsed, dict) and any(k in parsed for k in ['type', 'layout', 'subject', 'camera', 'style', 'background', 'the_vibe', 'prompt', 'positive_prompt', 'Scene_1', 'scene_1', 'character', 'setting']):
                    is_json_prompt = True
                    parsed_json = parsed
            except Exception:
                pass

        if is_json_prompt:
            categories['json_structured'].append((idx, content.split('\n')[0][:80], parsed_json))
            continue

        text_prompt_signals = [
            'positive prompt', 'prompt:', 'prompt :', 'prompt bối cảnh', 'prompt nhân vật',
            'prompt biểu cảm', 'câu lệnh:', 'câu lệnh :', 'câu lệnh koc ai', 'lời thoại chính xác',
            '--ar ', '--v ', 'hyperrealistic', 'photorealistic', 'masterpiece', '8k resolution',
            'shot on 35mm', 'dslr photo', 'close-up shot', 'cinematic lighting', 'lora:'
        ]
        
        has_prompt_signal = any(sig in content.lower() for sig in text_prompt_signals)
        
        non_prompt_phrases = [
            'đang gây chú ý tại trung quốc', 'nữ ai gây sốc', 'quy trình tạo video koc ai tự động - test giọng',
            'có thể bạn chưa biết - video koc ai này đạt', 'mình đã dành 2h xây dựng',
            'mẹo nhỏ để hoàn thành thử thách', 'tổng hợp các dạng series', 'xin chào mọi người, em là châu'
        ]
        is_explicit_non_prompt = any(phrase in content.lower() for phrase in non_prompt_phrases)
        
        if has_prompt_signal and not is_explicit_non_prompt and len(content) > 120:
            categories['text_structured'].append((idx, content.split('\n')[0][:80], content))
        else:
            categories['not_prompt'].append((idx, content.split('\n')[0][:80], content[:200]))

    print(f"JSON structured prompts: {len(categories['json_structured'])}")
    print(f"Text structured prompts: {len(categories['text_structured'])}")
    print(f"Non-prompt posts: {len(categories['not_prompt'])}")

if __name__ == '__main__':
    inspect()
