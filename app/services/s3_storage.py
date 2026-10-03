"""S3-compatible storage adapter for reference images, media uploads, KOC gallery, and DB migration."""

import base64
import hashlib
import mimetypes
import os
import shutil
import sqlite3
import ssl
import tempfile
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse, unquote, parse_qs

from app.config import DATA_DIR, IMAGES_DIR, THUMBNAILS_DIR, get_ai_config

# In-memory cache for presigned URLs: key -> (presigned_url, expire_timestamp)
_PRESIGNED_CACHE: Dict[str, Tuple[str, float]] = {}
DEFAULT_PRESIGNED_EXPIRES = 86400  # 24 hours


def get_or_download_thumbnail(url_or_key: str, cfg: Optional[dict] = None) -> Optional[Path]:
    """Lấy đường dẫn ảnh/video thumbnail từ thư mục cục bộ (DATA_DIR/thumbnails).
    Nếu chưa có, tải từ S3 (hoặc URL), lưu vào thư mục và trả về Path.
    Từ lần sau, trực tiếp phục vụ tệp từ đĩa cục bộ.
    """
    if not url_or_key or not isinstance(url_or_key, str):
        return None

    raw_str = url_or_key.strip()
    if not raw_str or raw_str.startswith("data:"):
        return None

    # Nếu truyền vào dạng /api/media/proxy?url=...
    if "/api/media/proxy" in raw_str:
        try:
            parsed = urlparse(raw_str)
            qs = parse_qs(parsed.query)
            target = qs.get("url", [""])[0]
            if target:
                raw_str = target.strip()
        except Exception:
            pass

    THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)
    cfg = cfg or get_ai_config()

    # Xác định tên file cache ổn định
    parsed = urlparse(raw_str)
    clean_path = unquote(parsed.path.lstrip("/"))
    basename = Path(clean_path).name

    ext = Path(basename).suffix.lower() if Path(basename).suffix else ".jpg"
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".mov", ".webm"}:
        ext = ".jpg"

    # Nếu basename đã là chuỗi hash md5 hợp lệ (32 ký tự hex)
    stem = Path(basename).stem
    if len(stem) >= 32 and all(c in "0123456789abcdefABCDEF_-" for c in stem):
        cache_filename = f"{stem}{ext}"
    else:
        url_hash = hashlib.md5(raw_str.split("?")[0].encode("utf-8")).hexdigest()
        cache_filename = f"{url_hash}{ext}"

    cache_path = THUMBNAILS_DIR / cache_filename

    # 1. Nếu đã có trong thư mục thumbnails -> dùng ngay lập tức
    if cache_path.exists() and cache_path.stat().st_size > 0:
        return cache_path

    # 2. Kiểm tra nếu có sẵn trong IMAGES_DIR
    if (IMAGES_DIR / basename).exists() and (IMAGES_DIR / basename).stat().st_size > 0:
        try:
            shutil.copy2(IMAGES_DIR / basename, cache_path)
            return cache_path
        except Exception:
            return IMAGES_DIR / basename

    # 3. Tải từ S3 hoặc URL ngoài
    bucket = cfg.get("s3_bucket", "")
    key = ""
    if raw_str.startswith(("http://", "https://")):
        if is_s3_url(raw_str, cfg):
            if bucket and clean_path.startswith(f"{bucket}/"):
                key = clean_path[len(bucket) + 1:]
            else:
                key = clean_path
    else:
        cleaned = raw_str.lstrip("/")
        if cleaned.startswith("images/"):
            cleaned = cleaned[len("images/"):]
        prefix = (cfg.get("s3_key_prefix") or "ai_prompts_database").strip("/")
        key = f"{prefix}/{cleaned}" if prefix and "/" not in cleaned else cleaned

    # Tải qua boto3 direct nếu có key S3
    if key and is_configured(cfg):
        try:
            client = _get_s3_client(cfg)
            resp = client.get_object(Bucket=bucket, Key=key)
            data = resp["Body"].read()
            cache_path.write_bytes(data)
            return cache_path
        except Exception as e:
            pass

    # Tải qua HTTP request (presigned URL hoặc URL công khai)
    try:
        download_url = get_presigned_url(raw_str, cfg=cfg) if is_s3_url(raw_str, cfg) else raw_str
        req = urllib.request.Request(download_url, headers={"User-Agent": "Mozilla/5.0"})
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
            data = resp.read()
            cache_path.write_bytes(data)
            return cache_path
    except Exception as e:
        print(f"[!] Lỗi tải media proxy cho {raw_str}: {e}")
        return None


def resolve_ai_media_url(url_or_source: str, cfg: Optional[dict] = None) -> str:
    """Đảm bảo URL gửi qua AI luôn là link S3 presigned 24h.
    Áp dụng cho cả ảnh và video tham chiếu.
    """
    if not url_or_source or not isinstance(url_or_source, str):
        return ""

    raw_str = url_or_source.strip()
    if not raw_str:
        return ""

    cfg = cfg or get_ai_config()

    # Nếu là link proxy UI /api/media/proxy?url=...
    if "/api/media/proxy" in raw_str:
        try:
            parsed = urlparse(raw_str)
            qs = parse_qs(parsed.query)
            target = qs.get("url", [""])[0]
            if target:
                raw_str = target.strip()
        except Exception:
            pass

    # Nếu là data URI hoặc file cục bộ -> upload lên S3 lấy link presigned 24h
    if raw_str.startswith("data:") or (not raw_str.startswith(("http://", "https://")) and os.path.exists(raw_str)):
        if is_configured(cfg):
            try:
                return upload_reference_image(raw_str, cfg=cfg)
            except Exception as e:
                print(f"[!] Warning uploading reference to S3: {e}")

    # Nếu là link S3 -> sinh presigned URL 24h
    if is_s3_url(raw_str, cfg) or not raw_str.startswith(("http://", "https://")):
        return get_presigned_url(raw_str, expires_in=DEFAULT_PRESIGNED_EXPIRES, cfg=cfg)

    return raw_str


def get_presigned_url(url_or_key: str, expires_in: int = DEFAULT_PRESIGNED_EXPIRES, cfg: Optional[dict] = None) -> str:
    """Tạo presigned URL 24h cho các đối tượng S3 trong bucket private.

    Tự động trích xuất key từ direct S3 URL hoặc relative path, và ký lại nếu cần.
    Giữ nguyên các URL ngoại vi (CDN ngoài) hoặc data URI.
    """
    if not url_or_key or not isinstance(url_or_key, str):
        return ""

    url_str = url_or_key.strip()
    if not url_str or url_str.startswith("data:") or url_str.startswith("/media/"):
        return url_str

    cfg = cfg or get_ai_config()
    if not is_configured(cfg):
        return url_str

    bucket = cfg.get("s3_bucket", "")
    if not bucket:
        return url_str

    # Trích xuất S3 object key
    key = ""
    if url_str.startswith(("http://", "https://")):
        if not is_s3_url(url_str, cfg):
            return url_str
        parsed = urlparse(url_str)
        path = unquote(parsed.path.lstrip("/"))
        if bucket and path.startswith(f"{bucket}/"):
            key = path[len(bucket) + 1:]
        else:
            key = path
    else:
        cleaned = url_str.lstrip("/")
        if cleaned.startswith("images/"):
            cleaned = cleaned[len("images/"):]
        prefix = (cfg.get("s3_key_prefix") or "ai_prompts_database").strip("/")
        if "/" in cleaned:
            key = cleaned
        else:
            key = f"{prefix}/{cleaned}" if prefix else cleaned

    if not key:
        return url_str

    # Kiểm tra cache (tự động làm mới trước khi hết hạn 1 giờ)
    now = time.time()
    cached = _PRESIGNED_CACHE.get(key)
    if cached and (cached[1] - now > 3600):
        return cached[0]

    try:
        client = _get_s3_client(cfg)
        presigned = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in,
        )
        _PRESIGNED_CACHE[key] = (presigned, now + expires_in)
        return presigned
    except Exception as e:
        print(f"[!] Warning generating presigned URL for {key}: {e}")
        return url_str


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
        ExpiresIn=DEFAULT_PRESIGNED_EXPIRES,  # 24 hours
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

    # Return presigned URL (valid 24h) so external AI providers can always access it
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": cfg["s3_bucket"], "Key": key},
        ExpiresIn=DEFAULT_PRESIGNED_EXPIRES,
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
