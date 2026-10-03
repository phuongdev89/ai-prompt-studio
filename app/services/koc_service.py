"""Service to interact with koc_management to list KOCs, their photos, and serve media."""

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

logger = logging.getLogger(__name__)

# In-memory cache for KOC data
_CACHE: Dict[str, Any] = {
    "data": None,
    "timestamp": 0.0,
}
CACHE_TTL = 60.0  # seconds


def find_koc_script() -> Tuple[Path, Path]:
    """Locate koc_management/list.py and appropriate python executable.
    
    Returns:
        (python_executable, list_script_path)
    """
    script_candidates = []

    # 1. Environment variable if set
    env_path = os.environ.get("KOC_MANAGEMENT_PATH")
    if env_path:
        p = Path(env_path)
        if p.is_file() and p.name == "list.py":
            script_candidates.append(p)
        elif p.is_dir():
            script_candidates.append(p / "list.py")

    # 2. AFFILIATE_ROOT from .env
    from app.config import get_affiliate_root
    aff_root = get_affiliate_root()
    if aff_root:
        script_candidates.append(aff_root / "koc_management" / "list.py")
        script_candidates.append(aff_root / "04_Tools" / "koc_management" / "list.py")

    # 3. Sibling directory: <workspace_parent>/koc_management/list.py
    current_file = Path(__file__).resolve()
    # app/services/koc_service.py -> app/services -> app -> ai_prompts_database -> 04_Tools
    tools_dir = current_file.parent.parent.parent.parent
    sibling_script = tools_dir / "koc_management" / "list.py"
    script_candidates.append(sibling_script)

    # 3. Working directory fallbacks
    script_candidates.append(Path.cwd().parent / "koc_management" / "list.py")
    script_candidates.append(Path("D:/Affiliate/04_Tools/koc_management/list.py"))

    script_path = None
    for cand in script_candidates:
        try:
            resolved = cand.resolve()
            if resolved.is_file():
                script_path = resolved
                break
        except Exception:
            continue

    if not script_path or not script_path.is_file():
        raise FileNotFoundError(
            f"Không tìm thấy file list.py của koc_management. Đã kiểm tra: {[str(c) for c in script_candidates]}"
        )

    # Determine Python executable (prefer venv of koc_management if available)
    koc_dir = script_path.parent
    venv_python_win = koc_dir / ".venv" / "Scripts" / "python.exe"
    venv_python_unix = koc_dir / ".venv" / "bin" / "python"

    if venv_python_win.is_file():
        python_exe = venv_python_win
    elif venv_python_unix.is_file():
        python_exe = venv_python_unix
    else:
        python_exe = Path(sys.executable)

    return python_exe, script_path


def run_koc_list_script(rescan: bool = False, koc_name: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
    """Execute list.py script in koc_management and parse JSON output."""
    python_exe, script_path = find_koc_script()
    koc_dir = script_path.parent

    cmd = [str(python_exe), str(script_path), "--json"]
    if rescan:
        cmd.append("-r")
    if koc_name:
        cmd.append(koc_name)

    logger.info("Running koc_management list.py: %s (cwd=%s)", cmd, koc_dir)
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(koc_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Gọi script list.py bị timeout sau 30 giây") from exc
    except Exception as exc:
        raise RuntimeError(f"Lỗi khi thực thi script list.py: {exc}") from exc

    if proc.returncode != 0:
        err_msg = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError(f"Script list.py trả về mã lỗi {proc.returncode}: {err_msg}")

    stdout_text = proc.stdout.strip()
    if not stdout_text:
        return {}

    try:
        data = json.loads(stdout_text)
        if isinstance(data, dict):
            return data
        return {}
    except Exception as exc:
        raise RuntimeError(f"Dữ liệu JSON trả về từ list.py không hợp lệ: {exc}. Đầu ra: {stdout_text[:200]}") from exc


def get_cached_koc_data(refresh: bool = False) -> Dict[str, List[Dict[str, Any]]]:
    """Get full KOC data using in-memory cache."""
    global _CACHE
    now = time.time()
    if not refresh and _CACHE["data"] is not None and (now - _CACHE["timestamp"] < CACHE_TTL):
        return _CACHE["data"]

    data = run_koc_list_script(rescan=refresh)
    _CACHE["data"] = data
    _CACHE["timestamp"] = now
    return data


def get_koc_names_and_counts(refresh: bool = False) -> List[Dict[str, Any]]:
    """Return summary list of all KOC characters with count and fast thumbnail cover."""
    data = get_cached_koc_data(refresh=refresh)
    results = []
    for name, images in sorted(data.items(), key=lambda x: x[0]):
        first_img = images[0] if images else None
        first_path = (first_img.get("path") or first_img.get("image") or "") if first_img else None
        first_thumb = (first_img.get("thumb") or first_img.get("thumb_url") or first_img.get("thumb_path")) if first_img else None

        # Cover URL: prioritize thumbnail for fast loading (30KB-80KB), fall back to original url/path
        from app.services.s3_storage import get_presigned_url
        raw_cover = first_thumb or (first_img.get("url") or first_img.get("presigned_url") if first_img else None)
        if not raw_cover and first_path:
            cover_url = f"/api/koc/image?path={quote(first_path)}"
        elif raw_cover and raw_cover.startswith(("http://", "https://")):
            cover_url = f"/api/media/proxy?url={quote(raw_cover)}"
        else:
            cover_url = raw_cover or ""

        raw_thumb = first_thumb or raw_cover
        if not raw_thumb and first_path:
            final_thumb = cover_url
        elif raw_thumb and raw_thumb.startswith(("http://", "https://")):
            final_thumb = f"/api/media/proxy?url={quote(raw_thumb)}"
        else:
            final_thumb = raw_thumb or cover_url

        results.append({
            "name": name,
            "count": len(images),
            "cover_path": first_path,
            "cover_thumb": final_thumb,
            "cover_url": cover_url,
        })
    return results


def get_images_for_koc(koc_name: str, refresh: bool = False) -> List[Dict[str, Any]]:
    """Return all images for a given KOC name with accessible web URLs.
    Supports S3 Sync Mirror output: presigned_url, local_path, s3_path, s3_key,
    and automatic thumbnail fields: thumb, thumb_url, thumb_rel_path.
    """
    data = get_cached_koc_data(refresh=refresh)

    # Try exact match, then case-insensitive match
    images = data.get(koc_name)
    if images is None:
        for k, v in data.items():
            if k.lower() == koc_name.lower():
                images = v
                break
    images = images or []

    results = []
    for img in images:
        path_str = img.get("path") or img.get("image") or ""
        presigned = img.get("presigned_url") or ""
        if not presigned and path_str.startswith(("http://", "https://")):
            presigned = path_str

        # Web URL for original full-resolution image (prioritize presigned S3 URL)
        web_url = img.get("url") or presigned
        if not web_url and path_str:
            web_url = f"/api/koc/image?path={quote(path_str)}"

        # Thumbnail URL: prioritize thumb/thumb_url from koc_management (30KB-80KB vs 2-5MB)
        thumb_str = img.get("thumb") or img.get("thumb_url") or img.get("thumb_path") or ""
        thumb_presigned = img.get("thumb_presigned_url") or ""
        if not thumb_presigned and thumb_str.startswith(("http://", "https://")):
            thumb_presigned = thumb_str

        thumb_web_url = img.get("thumb_url") or thumb_presigned or thumb_str
        if not thumb_web_url:
            thumb_local = img.get("thumb_local_path") or ""
            if thumb_local:
                thumb_web_url = f"/api/koc/image?path={quote(thumb_local)}"
            else:
                thumb_web_url = web_url

        results.append({
            "name": img.get("name") or Path(path_str).name,
            "path": path_str,
            "image": img.get("image") or path_str,
            "url": web_url,
            "presigned_url": presigned or web_url,
            "s3_url": presigned or web_url,
            "local_path": img.get("local_path") or (path_str if not path_str.startswith(("http://", "https://")) else ""),
            "s3_path": img.get("s3_path") or "",
            "s3_key": img.get("s3_key") or "",
            "rel_path": img.get("rel_path", ""),
            "thumb": thumb_web_url,
            "thumb_url": thumb_web_url,
            "thumb_path": img.get("thumb_path") or thumb_web_url,
            "thumb_rel_path": img.get("thumb_rel_path", ""),
            "thumb_local_path": img.get("thumb_local_path", ""),
            "thumb_s3_key": img.get("thumb_s3_key", ""),
            "thumb_s3_path": img.get("thumb_s3_path", ""),
            "caption": img.get("caption", ""),
            "id": img.get("id", ""),
            "media_type": img.get("media_type", "image"),
        })
    return results


def validate_image_path(path_str: str) -> Path:
    """Validate that path exists and is an image file for serving."""
    if not path_str:
        raise ValueError("Đường dẫn ảnh không được để trống")
    p = Path(path_str).resolve()
    if not p.is_file():
        raise FileNotFoundError(f"Tệp không tồn tại: {p}")
    valid_exts = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".bmp"}
    if p.suffix.lower() not in valid_exts:
        raise ValueError(f"Định dạng tệp không được hỗ trợ: {p.suffix}")
    return p


def find_koc_character_dir(koc_name: Optional[str] = None, ref_path: Optional[str] = None) -> Path:
    """Find the target directory on local disk where the KOC assets/reference file reside.

    1. If ref_path is provided and points to a local file/directory, returns that directory.
    2. Otherwise searches AI_CHARACTER_DIR (D:\\Affiliate\\01_Brand_Assets\\AI_Character)
       for a subfolder matching koc_name.
    3. Falls back to AI_CHARACTER_DIR / koc_name.
    """
    # 1. If ref_path points to an existing local file or directory
    if ref_path and not ref_path.startswith(("http://", "https://")):
        try:
            cand = Path(ref_path).resolve()
            if cand.is_file():
                parent = cand.parent
                if parent.name.lower() == "thumbs":
                    parent = parent.parent
                return parent
            if cand.is_dir():
                return cand
        except Exception:
            pass

    # 2. Determine base AI_CHARACTER_DIR
    env_dir = os.environ.get("AI_CHARACTER_DIR")
    candidates = []
    if env_dir:
        candidates.append(Path(env_dir))
    candidates.append(Path(r"D:\Affiliate\01_Brand_Assets\AI_Character"))
    tools_dir = Path(__file__).resolve().parent.parent.parent.parent
    candidates.append(tools_dir / "01_Brand_Assets" / "AI_Character")

    ai_char_dir = None
    for cand in candidates:
        try:
            if cand.is_dir():
                ai_char_dir = cand.resolve()
                break
        except Exception:
            continue

    if not ai_char_dir:
        ai_char_dir = Path(r"D:\Affiliate\01_Brand_Assets\AI_Character")
        ai_char_dir.mkdir(parents=True, exist_ok=True)

    # 3. Check if ref_path matches something inside ai_char_dir
    if ref_path and not ref_path.startswith(("http://", "https://")):
        clean_ref = ref_path.replace("\\", "/").strip("/")
        cand_in_base = ai_char_dir / clean_ref
        try:
            if cand_in_base.is_file():
                parent = cand_in_base.parent
                if parent.name.lower() == "thumbs":
                    parent = parent.parent
                return parent
            if cand_in_base.is_dir():
                return cand_in_base
        except Exception:
            pass

    # 4. Search matching subfolder for koc_name
    if koc_name:
        koc_name_clean = koc_name.strip()
        for item in ai_char_dir.iterdir():
            if item.is_dir() and item.name.lower() == koc_name_clean.lower():
                return item
        target = ai_char_dir / koc_name_clean
        target.mkdir(parents=True, exist_ok=True)
        return target

    return ai_char_dir


def save_image_to_koc_local(
    image_data: str,
    koc_name: Optional[str] = None,
    ref_path: Optional[str] = None,
    prompt_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Save an image directly to the local KOC directory alongside the reference file.
    Does NOT upload to S3.
    """
    from app.services.s3_storage import _read_image
    import mimetypes
    import re
    from datetime import datetime

    if not image_data or not str(image_data).strip():
        raise ValueError("Dữ liệu ảnh không được để trống")

    # 1. Read and decode image bytes
    content_bytes, mime = _read_image(str(image_data).strip())
    if not content_bytes:
        raise ValueError("Không thể trích xuất dữ liệu ảnh")

    # 2. Determine target folder (alongside reference file)
    target_dir = find_koc_character_dir(koc_name=koc_name, ref_path=ref_path)
    target_dir.mkdir(parents=True, exist_ok=True)

    # 3. Determine file extension
    ext = mimetypes.guess_extension(mime) or ".png"
    if ext == ".jpe":
        ext = ".jpg"

    # 4. Generate filename based on reference image or KOC name
    stem = ""
    if ref_path:
        ref_clean = ref_path.split("?")[0].replace("\\", "/").rstrip("/")
        cand_stem = Path(ref_clean).stem
        if cand_stem and cand_stem.lower() not in ("image", "input_file_0"):
            stem = cand_stem

    if not stem and koc_name:
        stem = re.sub(r'[^a-zA-Z0-9_\-]', '_', koc_name.strip().lower()).strip('_')

    if not stem:
        stem = f"koc_gen_{prompt_id}" if prompt_id else "koc_ai"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{stem}_ai_{timestamp}{ext}"

    dest_path = target_dir / filename
    counter = 1
    while dest_path.exists():
        filename = f"{stem}_ai_{timestamp}_{counter}{ext}"
        dest_path = target_dir / filename
        counter += 1

    dest_path.write_bytes(content_bytes)

    # Invalidate KOC list cache
    global _CACHE
    _CACHE["timestamp"] = 0.0

    return {
        "status": "success",
        "saved_path": str(dest_path),
        "filename": filename,
        "directory": str(target_dir),
        "file_size": len(content_bytes),
        "koc_name": koc_name or target_dir.name,
        "message": f"Đã lưu ảnh vào thư mục KOC: {filename}",
    }

