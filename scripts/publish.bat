@echo off
REM ========================================================
REM   PUBLISH - Xuất prompts_feed.json và đẩy lên GitHub
REM ========================================================
cd /d "%~dp0\.."
title AI Prompt Studio - Publish Feed

echo ==================================================
echo    PUBLISH FEED - AI PROMPT STUDIO
echo ==================================================
echo.

set "PY_CMD="
if exist ".venv\Scripts\python.exe" (
    set "PY_CMD=.venv\Scripts\python.exe"
    goto RUN
)
if exist "venv\Scripts\python.exe" (
    set "PY_CMD=venv\Scripts\python.exe"
    goto RUN
)
where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "PY_CMD=python"
    goto RUN
)
echo [ERROR] Khong tim thay Python!
pause
exit /b 1

:RUN
echo [1/3] Trich xuat prompts_feed.json tu database...
%PY_CMD% -c "
import json, hashlib, sqlite3, os
from datetime import datetime, timezone
from pathlib import Path

db_path = Path('data/prompts.db')
if not db_path.exists():
    print('[ERROR] Khong tim thay data/prompts.db')
    exit(1)

conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row

# Read version
ver = '1.0.0'
vf = Path('.version')
if vf.exists():
    ver = vf.read_text().strip()

prompts = []
for row in conn.execute('SELECT * FROM prompts ORDER BY original_index'):
    r = dict(row)
    pid = r['id']

    # Parse JSON fields
    parsed = {}
    try:
        parsed = json.loads(r.get('parsed_json', '{}'))
    except:
        pass

    # Get tags
    tags = [t['tag'] for t in conn.execute('SELECT tag FROM prompt_tags WHERE prompt_id = ?', (pid,)).fetchall()]

    # Get images
    images = [{'url': i['url'], 'order_index': i['order_index']}
              for i in conn.execute('SELECT url, order_index FROM images WHERE prompt_id = ? ORDER BY order_index', (pid,)).fetchall()
              if i['url']]

    # Build hash
    h = r.get('hash', '')
    if not h:
        payload = json.dumps({'title': r['title'], 'parsed_json': parsed}, sort_keys=True, ensure_ascii=False)
        h = hashlib.sha256(payload.encode()).hexdigest()

    now = r.get('published_at', '') or datetime.now(timezone.utc).isoformat()

    prompts.append({
        'id': pid,
        'title': r.get('title', ''),
        'note': r.get('note', ''),
        'category': r.get('category', 'image'),
        'prompt_type': r.get('prompt_type', 'json'),
        'raw_content': r.get('raw_content', ''),
        'parsed_json': parsed,
        'original_index': r.get('original_index', 0),
        'tags': tags,
        'images': images,
        'hash': h,
        'published_at': now,
    })

feed = {
    'latest_app_version': ver,
    'installer_url': '',
    'published_at': datetime.now(timezone.utc).isoformat(),
    'prompts': prompts,
}

out = Path('prompts_feed.json')
out.write_text(json.dumps(feed, indent=2, ensure_ascii=False), encoding='utf-8')
print(f'[OK] Da xuat {len(prompts)} prompts vao {out}')
conn.close()
"

if %ERRORLEVEL% neq 0 (
    echo [ERROR] Trich xuat that bai!
    pause
    exit /b 1
)

echo.
echo [2/3] Git add + commit...
git add prompts_feed.json
git commit -m "Update prompts_feed.json"

echo.
echo [3/3] Git push...
git push origin main

echo.
echo ==================================================
echo   PUBLISH HOAN TAT THANH CONG!
echo ==================================================
echo.
pause
