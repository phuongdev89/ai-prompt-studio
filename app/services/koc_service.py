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

    # 2. Sibling directory: <workspace_parent>/koc_management/list.py
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
    """Return summary list of all KOC characters."""
    data = get_cached_koc_data(refresh=refresh)
    results = []
    for name, images in sorted(data.items(), key=lambda x: x[0]):
        first_img = images[0] if images else None
        results.append({
            "name": name,
            "count": len(images),
            "cover_path": first_img["path"] if first_img else None,
            "cover_url": f"/api/koc/image?path={quote(first_img['path'])}" if first_img else None,
        })
    return results


def get_images_for_koc(koc_name: str, refresh: bool = False) -> List[Dict[str, Any]]:
    """Return all images for a given KOC name with accessible web URLs."""
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
        results.append({
            "name": img.get("name") or Path(path_str).name,
            "path": path_str,
            "rel_path": img.get("rel_path", ""),
            "caption": img.get("caption", ""),
            "id": img.get("id", ""),
            "media_type": img.get("media_type", "image"),
            "url": f"/api/koc/image?path={quote(path_str)}" if path_str else None,
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
