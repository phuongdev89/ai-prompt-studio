import os
import sys
import time
import sqlite3
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, Optional
from app.config import IMAGES_DIR, DB_PATH
from app.db.database import get_db

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,video/*,*/*;q=0.8",
    "Accept-Language": "vi,en-US;q=0.9,en;q=0.8",
    "Referer": "https://www.facebook.com/"
}

def detect_extension(url: str, content_type: Optional[str] = None) -> str:
    url_lower = url.lower().split("?")[0]
    if content_type:
        ct = content_type.lower()
        if "video/mp4" in ct or "mp4" in ct:
            return ".mp4"
        if "video/webm" in ct or "webm" in ct:
            return ".webm"
        if "image/png" in ct:
            return ".png"
        if "image/webp" in ct:
            return ".webp"
        if "image/gif" in ct:
            return ".gif"
        if "image/jpeg" in ct or "image/jpg" in ct:
            return ".jpg"

    for ext in [".mp4", ".webm", ".png", ".webp", ".gif", ".jpeg", ".jpg"]:
        if url_lower.endswith(ext):
            return ext
    return ".jpg"

def download_media_file(image_id: int, prompt_id: str, url: str, base_filename: Optional[str] = None, timeout: int = 15) -> Dict[str, Any]:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    
    if not url or not url.startswith("http"):
        return {"id": image_id, "status": "failed", "size": 0, "error": "Invalid URL"}

    req = urllib.request.Request(url, headers=HEADERS)

    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                content = response.read()
                if len(content) == 0:
                    raise ValueError("Empty body")
                
                content_type = response.headers.get("Content-Type", "")
                ext = detect_extension(url, content_type)
                
                if base_filename:
                    # Remove existing extension if any and append detected
                    stem = Path(base_filename).stem
                    filename = f"{stem}{ext}"
                else:
                    filename = f"{prompt_id}_img_{image_id}{ext}"

                target_path = IMAGES_DIR / filename
                with open(target_path, "wb") as f:
                    f.write(content)

                local_path = f"images/{filename}"
                file_size = len(content)

                # Update database
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE images
                        SET status = 'downloaded', local_path = ?, filename = ?, file_size = ?
                        WHERE id = ?
                    """, (local_path, filename, file_size, image_id))
                    conn.commit()

                return {
                    "id": image_id,
                    "status": "downloaded",
                    "local_path": local_path,
                    "filename": filename,
                    "file_size": file_size,
                    "error": None
                }
        except Exception as e:
            if attempt == 1:
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE images SET status = 'failed' WHERE id = ?", (image_id,))
                    conn.commit()
                return {
                    "id": image_id,
                    "status": "failed",
                    "local_path": None,
                    "filename": base_filename,
                    "file_size": 0,
                    "error": str(e)
                }
            time.sleep(1)

def download_prompt_images_now(prompt_id: str):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, prompt_id, url, filename, status FROM images WHERE prompt_id = ?", (prompt_id,))
        rows = cursor.fetchall()

    for r in rows:
        img_id = r["id"]
        url = r["url"]
        filename = r.get("filename") or f"{prompt_id}_img_{img_id}.jpg"
        download_media_file(img_id, prompt_id, url, filename)
