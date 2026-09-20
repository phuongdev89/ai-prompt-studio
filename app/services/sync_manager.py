"""
Sync Manager — kéo prompts_feed.json từ GitHub, INSERT OR IGNORE theo hash.
Tải ảnh mẫu ngầm. Kiểm tra phiên bản phần mềm mới.
"""
import json
import hashlib
import os
import threading
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import URLError

from app.config import DATA_DIR, IMAGES_DIR
from app.db.database import get_db

# ponytail: hardcode GitHub raw URL; upgrade to env/config when multi-repo needed
FEED_URL = os.getenv(
    "SYNC_FEED_URL",
    "https://raw.githubusercontent.com/phuongdev89/ai-prompt-studio/main/prompts_feed.json",
)


def _fetch_json(url: str, timeout: int = 30) -> dict:
    req = Request(url, headers={"User-Agent": "AI-Prompt-Studio/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_last_synced() -> str:
    with get_db() as conn:
        row = conn.execute(
            "SELECT value FROM sync_meta WHERE key = 'last_synced_at'"
        ).fetchone()
        return row["value"] if row else ""


def set_last_synced(ts: str):
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO sync_meta (key, value) VALUES ('last_synced_at', ?)",
            (ts,),
        )
        conn.commit()


def check_update() -> dict:
    """Kiểm tra có bản cập nhật data/code mới không.
    Returns: {has_data: bool, new_count: int, has_app_update: bool, latest_version: str, installer_url: str}
    """
    try:
        feed = _fetch_json(FEED_URL)
    except (URLError, Exception) as e:
        return {"error": str(e)}

    last_synced = get_last_synced()

    # Count new prompts since last sync
    new_prompts = [
        p for p in feed.get("prompts", [])
        if p.get("published_at", "") > last_synced
    ]

    from app import __version__
    latest_ver = feed.get("latest_app_version", __version__)
    has_app_update = latest_ver > __version__

    return {
        "has_data": len(new_prompts) > 0,
        "new_count": len(new_prompts),
        "has_app_update": has_app_update,
        "latest_version": latest_ver,
        "installer_url": feed.get("installer_url", ""),
    }


def pull_data() -> dict:
    """Kéo dữ liệu mới từ feed, INSERT OR IGNORE theo hash."""
    try:
        feed = _fetch_json(FEED_URL)
    except (URLError, Exception) as e:
        return {"error": str(e), "inserted": 0}

    last_synced = get_last_synced()
    new_prompts = [
        p for p in feed.get("prompts", [])
        if p.get("published_at", "") > last_synced
    ]

    if not new_prompts:
        return {"inserted": 0, "message": "Đã cập nhật mới nhất."}

    inserted = 0
    image_urls = []

    with get_db() as conn:
        cursor = conn.cursor()
        for p in new_prompts:
            h = p.get("hash") or hashlib.sha256(
                json.dumps(p, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()

            # Skip if hash exists
            if cursor.execute("SELECT 1 FROM prompts WHERE hash = ?", (h,)).fetchone():
                continue

            prompt_id = p.get("id", f"sync_{h[:12]}")
            # Ensure unique id
            if cursor.execute("SELECT 1 FROM prompts WHERE id = ?", (prompt_id,)).fetchone():
                prompt_id = f"{prompt_id}_{h[:8]}"

            parsed = p.get("parsed_json", {})
            prompt_code = json.dumps(parsed, indent=2, ensure_ascii=False) if isinstance(parsed, dict) else str(parsed)

            cursor.execute("""
                INSERT INTO prompts (id, original_index, title, raw_title, prompt_type,
                    raw_content, prompt_code, parsed_json, category, note, hash, published_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                prompt_id,
                p.get("original_index", 0),
                p.get("title", ""),
                p.get("title", ""),
                p.get("prompt_type", "json"),
                p.get("raw_content", prompt_code),
                prompt_code,
                prompt_code,
                p.get("category", "image"),
                p.get("note", ""),
                h,
                p.get("published_at", ""),
            ))

            # Insert fields
            from app.services.parser import extract_flat_fields
            if isinstance(parsed, dict):
                for idx, f in enumerate(extract_flat_fields(parsed)):
                    cursor.execute("""
                        INSERT INTO prompt_fields (prompt_id, field_path, field_key, label, field_value, field_type, is_list, is_primary)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        prompt_id, f.get("path", ""), f.get("key", ""),
                        f.get("label", ""), str(f.get("value", "")),
                        f.get("type", "text"), 1 if f.get("is_list") else 0,
                        1 if idx < 4 else 0,
                    ))

            # Insert tags
            for tag in p.get("tags", []):
                cursor.execute(
                    "INSERT OR IGNORE INTO prompt_tags (prompt_id, tag) VALUES (?, ?)",
                    (prompt_id, tag),
                )

            # Collect image URLs for background download
            for img in p.get("images", []):
                url = img.get("url", "")
                if url:
                    image_urls.append((prompt_id, url, img.get("order_index", 0)))

            inserted += 1

        conn.commit()

    # Update last_synced_at
    now = datetime.now(timezone.utc).isoformat()
    max_pub = max((p.get("published_at", "") for p in new_prompts), default=now)
    set_last_synced(max_pub or now)

    # Download images in background
    if image_urls:
        threading.Thread(target=_download_images_bg, args=(image_urls,), daemon=True).start()

    return {"inserted": inserted, "images_queued": len(image_urls)}


def _download_images_bg(image_urls: list):
    """Tải ảnh ngầm, lưu vào data/images/ và cập nhật DB."""
    from app.services.downloader import download_media_file
    pending = []
    with get_db() as conn:
        cursor = conn.cursor()
        for prompt_id, url, order_idx in image_urls:
            cursor.execute("""
                INSERT INTO images (prompt_id, url, status, order_index)
                VALUES (?, ?, 'pending', ?)
            """, (prompt_id, url, order_idx))
            pending.append((cursor.lastrowid, prompt_id, url))
        conn.commit()

    # The downloader updates each existing row using its own connection.
    # Commit and release the write transaction before invoking it.
    for image_id, prompt_id, url in pending:
        try:
            download_media_file(image_id, prompt_id, url)
        except Exception:
            with get_db() as conn:
                conn.execute("UPDATE images SET status = 'failed' WHERE id = ?", (image_id,))
                conn.commit()
