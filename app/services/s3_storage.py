"""S3-compatible storage adapter for reference images, media uploads, KOC gallery, and DB migration."""

import base64
import hashlib
import mimetypes
import os
import shutil
import sqlite3
import tempfile
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from app.config import DATA_DIR, IMAGES_DIR, get_ai_config


def is_configured(cfg: Optional[dict] = None) -> bool:
    cfg = cfg or get_ai_config()
    return bool(
        cfg.get("s3_enabled")
        and cfg.get("s3_endpoint_url")
        and cfg.get("s3_bucket")
        and cfg.get("s3_access_key_id")
        and cfg.get("s3_secret_access_key")
    )


def compute_md5(data: bytes) -> str:
    """Compute MD5 hash hex string of raw bytes."""
    return hashlib.md5(data).hexdigest()


def is_s3_url(url: str, cfg: Optional[dict] = None) -> bool:
    """Check if a given URL is already hosted on S3 / Backblaze B2."""
    if not url or not isinstance(url, str):
        return False
    u = url.strip().lower()
    if not (u.startswith("http://") or u.startswith("https://")):
        return False
    cfg = cfg or get_ai_config()
    bucket = (cfg.get("s3_bucket") or "").lower()
    endpoint = (cfg.get("s3_endpoint_url") or "").lower()
    if bucket and bucket in u:
        return True
    if endpoint and endpoint.replace("https://", "").replace("http://", "") in u:
        return True
    return any(host in u for host in ("backblazeb2.com", "amazonaws.com", "r2.cloudflarestorage.com"))


def _get_s3_client(cfg: Optional[dict] = None):
    cfg = cfg or get_ai_config()
    if not is_configured(cfg):
        raise RuntimeError("Chưa cấu hình đầy đủ S3-compatible storage (.env)")
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError("Thiếu thư viện boto3. Hãy cài dependencies của ứng dụng.") from exc

    return boto3.client(
        "s3",
        endpoint_url=cfg["s3_endpoint_url"],
        region_name=cfg.get("s3_region") or "auto",
        aws_access_key_id=cfg["s3_access_key_id"],
        aws_secret_access_key=cfg["s3_secret_access_key"],
    )


def _read_image(source: str, timeout: int = 30) -> Tuple[bytes, str]:
    """Read image/media bytes and mime type from data URI, URL, or local file path."""
    source = (source or "").strip()
    if source.startswith("data:"):
        header, encoded = source.split(",", 1)
        mime = header.split(";", 1)[0][5:] or "image/png"
        return base64.b64decode(encoded), mime

    if source.startswith(("http://", "https://")):
        request = urllib.request.Request(source, headers={"User-Agent": "AI-Prompt-Studio/1.0"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get_content_type() or "image/png"
            return response.read(), content_type

    # Local file path
    try:
        p = Path(source)
        if not p.is_file():
            # Try resolving relative to DATA_DIR or IMAGES_DIR
            if (DATA_DIR / source).is_file():
                p = DATA_DIR / source
            elif (IMAGES_DIR / source).is_file():
                p = IMAGES_DIR / source
            elif (IMAGES_DIR / Path(source).name).is_file():
                p = IMAGES_DIR / Path(source).name

        if p.is_file():
            mime, _ = mimetypes.guess_type(str(p))
            mime = mime or "image/jpeg"
            return p.read_bytes(), mime
    except Exception:
        pass

    raise ValueError("Ảnh/tệp tham chiếu phải là data URI, URL HTTP(S) hoặc đường dẫn tệp tin hợp lệ")


def upload_content_to_s3(
    content: bytes,
    filename: str = "",
    mime: str = "",
    prefix: str = "",
    cfg: Optional[dict] = None,
) -> Dict[str, Any]:
    """Upload raw bytes to S3 using MD5 hash for filename."""
    cfg = cfg or get_ai_config()
    client = _get_s3_client(cfg)

    md5_hex = compute_md5(content)
    ext = Path(filename).suffix.lower() if filename else (mimetypes.guess_extension(mime) or ".jpg")
    if ext == ".jpe":
        ext = ".jpg"
    elif not ext:
        ext = ".jpg"

    md5_filename = f"{md5_hex}{ext}"
    clean_prefix = (prefix or cfg.get("s3_key_prefix") or "ai_prompts_database").strip("/")
    key = f"{clean_prefix}/{md5_filename}" if clean_prefix else md5_filename

    if not mime:
        mime, _ = mimetypes.guess_type(md5_filename)
        mime = mime or "image/jpeg"

    client.put_object(Bucket=cfg["s3_bucket"], Key=key, Body=content, ContentType=mime)

    endpoint_clean = cfg["s3_endpoint_url"].rstrip("/")
    direct_url = f"{endpoint_clean}/{cfg['s3_bucket']}/{key}"
    presigned_url = client.generate_presigned_url(
        "get_object",
        Params={"Bucket": cfg["s3_bucket"], "Key": key},
        ExpiresIn=604800,  # 7 days
    )

    return {
        "status": "success",
        "url": direct_url,
        "presigned_url": presigned_url,
        "key": key,
        "filename": md5_filename,
        "md5": md5_hex,
        "size": len(content),
    }


def upload_reference_image(source: str, cfg: Optional[dict] = None, is_koc: bool = False) -> str:
    """Upload an image to S3 for reference prompt usage.

    - If source is already an S3 link: returns it immediately without re-uploading.
    - If is_koc and source is a local path:
        1. Copies file to temp directory.
        2. Renames to md5_file.
        3. Uploads to S3 under subfolder 'draft' (S3_KOC_PREFIX/draft/md5_file).
        4. Returns the accessible S3 URL.
    - Otherwise uploads to S3_KEY_PREFIX/draft/md5_file.
    """
    cfg = cfg or get_ai_config()

    # 1. If already S3 URL, return directly
    if is_s3_url(source, cfg):
        return source

    client = _get_s3_client(cfg)
    content, mime = _read_image(source, timeout=int(cfg.get("timeout") or 30))
    md5_hex = compute_md5(content)

    ext = mimetypes.guess_extension(mime) or ".jpg"
    if ext == ".jpe":
        ext = ".jpg"
    # Check if original path has extension
    try:
        orig_ext = Path(source).suffix.lower()
        if orig_ext in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".mov"}:
            ext = orig_ext
    except Exception:
        pass

    md5_filename = f"{md5_hex}{ext}"

    if is_koc:
        # Copy to temp directory with md5 filename
        temp_dir = Path(tempfile.gettempdir()) / "koc_draft"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_file = temp_dir / md5_filename
        try:
            temp_file.write_bytes(content)
        except Exception as e:
            print(f"[!] Warning copying to temp directory: {e}")

        # Upload to S3 with subfolder 'draft' under S3_KOC_PREFIX
        koc_prefix = (cfg.get("s3_koc_prefix") or "koc_management").strip("/")
        key = f"{koc_prefix}/draft/{md5_filename}"
    else:
        key_prefix = (cfg.get("s3_key_prefix") or "ai_prompts_database").strip("/")
        key = f"{key_prefix}/draft/{md5_filename}"

    client.put_object(Bucket=cfg["s3_bucket"], Key=key, Body=content, ContentType=mime)

    # Return presigned URL (valid 7 days) so external AI providers can always access it
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": cfg["s3_bucket"], "Key": key},
        ExpiresIn=604800,
    )


def save_koc_gallery_image(source: str, koc_name: str = "", cfg: Optional[dict] = None) -> Dict[str, Any]:
    """Save an image into KOC gallery on S3 using S3_KOC_PREFIX from .env and MD5 filename."""
    cfg = cfg or get_ai_config()
    content, mime = _read_image(source, timeout=int(cfg.get("timeout") or 30))
    koc_prefix = (cfg.get("s3_koc_prefix") or "koc_management").strip("/")
    prefix = f"{koc_prefix}/gallery"
    res = upload_content_to_s3(content=content, filename="", mime=mime, prefix=prefix, cfg=cfg)
    res["koc_name"] = koc_name or ""
    res["message"] = "Đã lưu ảnh vào KOC gallery trên S3 thành công!"
    return res


def migrate_all_db_images_to_s3(cfg: Optional[dict] = None) -> Dict[str, Any]:
    """Upload all images currently in DB to S3, always using md5_file for filename.
    Updates the SQLite records with the new S3 URLs and md5 filenames.
    """
    from concurrent.futures import ThreadPoolExecutor

    cfg = cfg or get_ai_config()
    if not is_configured(cfg):
        raise RuntimeError("Chưa cấu hình S3-compatible storage (.env)")

    client = _get_s3_client(cfg)
    db_path = DATA_DIR / "prompts.db"
    if not db_path.exists():
        raise FileNotFoundError(f"Database không tồn tại tại {db_path}")

    prefix = (cfg.get("s3_key_prefix") or "ai_prompts_database").strip("/")
    endpoint_clean = cfg["s3_endpoint_url"].rstrip("/")
    bucket = cfg["s3_bucket"]

    conn = sqlite3.connect(str(db_path), timeout=60)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT id, prompt_id, url, local_path, filename FROM images")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    total = len(rows)

    def upload_worker(row):
        img_id = row["id"]
        current_url = row["url"] or ""
        local_rel = row["local_path"] or ""
        orig_filename = row["filename"] or ""

        if is_s3_url(current_url, cfg):
            return {"id": img_id, "status": "skipped"}

        file_path = None
        for c in [
            IMAGES_DIR / orig_filename if orig_filename else None,
            IMAGES_DIR / Path(local_rel).name if local_rel else None,
            DATA_DIR / local_rel if local_rel else None,
        ]:
            if c and c.is_file():
                file_path = c
                break

        if not file_path:
            return {"id": img_id, "status": "error", "error": f"Không tìm thấy file trên đĩa ({orig_filename or local_rel})"}

        try:
            content = file_path.read_bytes()
            md5_hex = compute_md5(content)
            ext = file_path.suffix.lower() or ".jpg"
            if ext == ".jpe":
                ext = ".jpg"
            md5_filename = f"{md5_hex}{ext}"
            key = f"{prefix}/{md5_filename}" if prefix else md5_filename
            mime, _ = mimetypes.guess_type(str(file_path))
            mime = mime or "image/jpeg"

            client.put_object(Bucket=bucket, Key=key, Body=content, ContentType=mime)
            direct_url = f"{endpoint_clean}/{bucket}/{key}"

            md5_local_path = IMAGES_DIR / md5_filename
            if not md5_local_path.exists():
                try:
                    shutil.copy2(file_path, md5_local_path)
                except Exception:
                    pass

            new_local_rel = f"images/{md5_filename}"
            return {
                "id": img_id,
                "status": "uploaded",
                "url": direct_url,
                "filename": md5_filename,
                "local_path": new_local_rel,
            }
        except Exception as e:
            return {"id": img_id, "status": "error", "error": str(e)}

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(upload_worker, rows))

    conn = sqlite3.connect(str(db_path), timeout=60)
    cur = conn.cursor()
    uploaded = 0
    skipped = 0
    errors = 0
    details = []

    for res in results:
        if res["status"] == "uploaded":
            cur.execute(
                "UPDATE images SET url = ?, filename = ?, local_path = ? WHERE id = ?",
                (res["url"], res["filename"], res["local_path"], res["id"])
            )
            uploaded += 1
        elif res["status"] == "skipped":
            skipped += 1
        else:
            errors += 1
            details.append(res)

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "total": total,
        "uploaded": uploaded,
        "skipped": skipped,
        "errors": errors,
        "error_details": details[:20],
    }
