import os
import sys
import socket
from pathlib import Path
from typing import Optional

# Paths — frozen exe vs dev
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
    _INTERNAL = BASE_DIR / "_internal"
    APP_DIR = _INTERNAL / "app"
    STATIC_DIR = APP_DIR / "static"
    TEMPLATES_DIR = APP_DIR / "templates"
    DATA_DIR = BASE_DIR / "data"
    _INTERNAL_DATA = _INTERNAL / "data"
    JSON_DATA_PATH = DATA_DIR / "cleaned_prompts.json" if (DATA_DIR / "cleaned_prompts.json").exists() else _INTERNAL_DATA / "cleaned_prompts.json"
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
    _INTERNAL = BASE_DIR
    APP_DIR = BASE_DIR / "app"
    STATIC_DIR = APP_DIR / "static"
    TEMPLATES_DIR = APP_DIR / "templates"
    DATA_DIR = BASE_DIR / "data"
    JSON_DATA_PATH = DATA_DIR / "cleaned_prompts.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "prompts.db"
IMAGES_DIR = DATA_DIR / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
THUMBNAILS_DIR = DATA_DIR / "thumbnails"
THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)

ENV_PATH = BASE_DIR / ".env"

# Server — always random port, localhost only
HOST = "127.0.0.1"
DEBUG = not getattr(sys, "frozen", False)


def find_free_port() -> int:
    """OS cấp port trống."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


# ============================================================
#  Config persistence — .env file at project root
# ============================================================

_DEFAULT_CONFIG = {
    "provider": "openai",
    "base_url": "https://api.openai.com/v1",
    "api_key": "",
    "chat_url": "https://9router.phuonganh.io.vn/v1",
    "chat_api_key": "",
    "image_url": "https://9router.phuonganh.io.vn/v1",
    "image_api_key": "",
    "video_url": "https://api.zpro.io.vn/v1",
    "video_api_key": "",
    "model": "gpt-4o-mini",
    "chat_model": "gpt-4o-mini",
    "image_model": "cx/gpt-5.6-sol-image",
    "image_type": "edit",
    "video_model": "zpro-payg/grok-imagine-video",
    "image_reference_support": False,
    "timeout": 300,
    "stream": True,
    "s3_enabled": False,
    "s3_endpoint_url": "",
    "s3_region": "auto",
    "s3_bucket": "",
    "s3_access_key_id": "",
    "s3_secret_access_key": "",
    "s3_key_prefix": "references",
    "s3_koc_prefix": "koc_management",
    "setup_done": False,
    "affiliate_root": "",
}


_ENV_KEY_MAP = {
    "AI_PROVIDER": "provider",
    "AI_BASE_URL": "base_url",
    "AI_API_KEY": "api_key",
    "AI_CHAT_URL": "chat_url",
    "AI_CHAT_KEY": "chat_api_key",
    "AI_IMAGE_URL": "image_url",
    "AI_IMAGE_KEY": "image_api_key",
    "AI_VIDEO_URL": "video_url",
    "AI_VIDEO_KEY": "video_api_key",
    "AI_MODEL": "model",
    "AI_CHAT_MODEL": "chat_model",
    "AI_IMAGE_MODEL": "image_model",
    "AI_IMAGE_TYPE": "image_type",
    "AI_VIDEO_MODEL": "video_model",
    "AI_IMAGE_REFERENCE_SUPPORT": "image_reference_support",
    "AI_TIMEOUT": "timeout",
    "AI_STREAM": "stream",
    "S3_ENABLED": "s3_enabled",
    "S3_ENDPOINT_URL": "s3_endpoint_url",
    "S3_REGION": "s3_region",
    "S3_BUCKET": "s3_bucket",
    "S3_ACCESS_KEY_ID": "s3_access_key_id",
    "S3_SECRET_ACCESS_KEY": "s3_secret_access_key",
    "S3_KEY_PREFIX": "s3_key_prefix",
    "S3_KOC_PREFIX": "s3_koc_prefix",
    "SETUP_DONE": "setup_done",
    "AFFILIATE_ROOT": "affiliate_root",
}

_BOOL_KEYS = {"image_reference_support", "stream", "s3_enabled", "setup_done"}
_INT_KEYS = {"timeout"}


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _coerce_env_value(key: str, value: str):
    if key in _BOOL_KEYS:
        return _parse_bool(value)
    if key in _INT_KEYS:
        try:
            return int(value)
        except ValueError:
            return _DEFAULT_CONFIG[key]
    return value.strip()


def _read_env_file() -> dict:
    if not ENV_PATH.exists():
        return {}

    values = {}
    try:
        for raw_line in ENV_PATH.read_text("utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            env_key, value = line.split("=", 1)
            env_key = env_key.strip()
            config_key = _ENV_KEY_MAP.get(env_key)
            if not config_key:
                continue
            value = value.strip().strip('"').strip("'")
            values[config_key] = _coerce_env_value(config_key, value)
    except Exception:
        pass
    return values


def get_bundled_db_path() -> Optional[Path]:
    """Tìm file prompts.db gốc đi kèm nếu có (không ship mặc định)."""
    candidates = [
        BASE_DIR / "data" / "prompts.db",
        _INTERNAL / "data" / "prompts.db",
    ]
    for p in candidates:
        if p.exists() and p.resolve() != DB_PATH.resolve():
            return p
    return None


def get_affiliate_root() -> Optional[Path]:
    """Lấy thư mục gốc AFFILIATE_ROOT từ file .env nếu có."""
    saved = _read_env_file()
    aff_root = saved.get("affiliate_root", "").strip()
    if aff_root:
        return Path(aff_root)
    return None


def get_backup_dir() -> Optional[Path]:
    """Thư mục sao lưu database: $AFFILIATE_ROOT/05_Storage/03_Tool_Backups/ai_prompts_database."""
    root = get_affiliate_root()
    if root:
        return root / "05_Storage" / "03_Tool_Backups" / "ai_prompts_database"
    return None


def backup_database() -> Optional[Path]:
    """
    Tạo bản sao lưu database kèm timestamp đầy đủ vào thư mục:
    $AFFILIATE_ROOT/05_Storage/03_Tool_Backups/ai_prompts_database/prompts_backup_YYYYMMDD_HHMMSS.db
    """
    import shutil
    import datetime

    if not DB_PATH.exists():
        return None

    bk_dir = get_backup_dir()
    if not bk_dir:
        return None

    try:
        bk_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dest_file = bk_dir / f"prompts_backup_{timestamp}.db"
        shutil.copy2(DB_PATH, dest_file)
        return dest_file
    except Exception as e:
        print(f"[!] Lỗi khi sao lưu database: {e}")
        return None


def get_ai_config() -> dict:
    """Load AI config from .env, merged with defaults."""
    saved = _read_env_file()
    merged = {**_DEFAULT_CONFIG, **saved}

    for k in ("provider", "base_url", "api_key", "chat_url", "chat_api_key",
              "image_url", "image_api_key", "video_url", "video_api_key",
              "model", "chat_model", "image_model", "image_type", "video_model",
              "s3_endpoint_url", "s3_region", "s3_bucket", "s3_access_key_id",
              "s3_secret_access_key", "s3_key_prefix", "s3_koc_prefix", "affiliate_root"):
        if isinstance(merged.get(k), str):
            merged[k] = merged[k].strip().strip('"').strip("'")

    if merged.get("image_url"):
        merged["image_url"] = merged["image_url"].rstrip("/")
    if merged.get("chat_url"):
        merged["chat_url"] = merged["chat_url"].rstrip("/")
    if merged.get("video_url"):
        merged["video_url"] = merged["video_url"].rstrip("/")

    # Đồng bộ base_url và api_key ưu tiên theo image / chat
    if merged.get("image_url"):
        merged["base_url"] = merged["image_url"]
    elif merged.get("chat_url"):
        merged["base_url"] = merged["chat_url"]

    if merged.get("image_api_key"):
        merged["api_key"] = merged["image_api_key"]
    elif merged.get("chat_api_key"):
        merged["api_key"] = merged["chat_api_key"]

    raw_img = merged.get("image_model", "")
    img_models_list = [m.strip() for m in raw_img.split(",") if m.strip()]
    merged["image_models"] = img_models_list if img_models_list else ["cx/gpt-5.6-sol-image"]
    merged["default_image_model"] = merged["image_models"][0]
    merged["image_model"] = merged["default_image_model"]

    raw_vid = merged.get("video_model", "")
    vid_models_list = [m.strip() for m in raw_vid.split(",") if m.strip()]
    merged["video_models"] = vid_models_list if vid_models_list else ["zpro-payg/grok-imagine-video", "grok-imagine-video"]
    merged["default_video_model"] = merged["video_models"][0]
    merged["video_model"] = merged["default_video_model"]

    return merged


def save_ai_config(new_config: dict) -> None:
    raise RuntimeError("Cấu hình chỉ được đọc từ file .env. Không thể sửa trên web.")


def is_setup_done() -> bool:
    """Trả về True khi đã cấu hình SETUP_DONE và AFFILIATE_ROOT."""
    cfg = get_ai_config()
    setup_done = bool(cfg.get("setup_done", False))
    affiliate_root = bool(cfg.get("affiliate_root", "").strip())
    return setup_done and affiliate_root


def get_video_models() -> list:
    cfg = get_ai_config()
    return cfg.get("video_models", ["zpro-payg/grok-imagine-video", "grok-imagine-video"])


def get_image_models() -> list:
    cfg = get_ai_config()
    return cfg.get("image_models", ["cx/gpt-5.6-sol-image"])


# Ensure required directories exist
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
