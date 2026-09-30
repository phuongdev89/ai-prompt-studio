import os
import sys
import socket
from pathlib import Path

# Paths — frozen exe vs dev
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
    _INTERNAL = BASE_DIR / "_internal"
    APP_DIR = _INTERNAL / "app"
    STATIC_DIR = APP_DIR / "static"
    TEMPLATES_DIR = APP_DIR / "templates"
    DATA_DIR = BASE_DIR / "data"
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
    APP_DIR = BASE_DIR / "app"
    STATIC_DIR = APP_DIR / "static"
    TEMPLATES_DIR = APP_DIR / "templates"
    DATA_DIR = BASE_DIR / "data"

DB_PATH = DATA_DIR / "prompts.db"
JSON_DATA_PATH = DATA_DIR / "cleaned_prompts.json"
IMAGES_DIR = DATA_DIR / "images"
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
    "setup_done": False,
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
    "SETUP_DONE": "setup_done",
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
    return values


def get_ai_config() -> dict:
    """Load AI config from .env, merged with defaults."""
    saved = _read_env_file()
    merged = {**_DEFAULT_CONFIG, **saved}

    for k in ("provider", "base_url", "api_key", "chat_url", "chat_api_key",
              "image_url", "image_api_key", "video_url", "video_api_key",
              "model", "chat_model", "image_model", "image_type", "video_model",
              "s3_endpoint_url", "s3_region", "s3_bucket", "s3_access_key_id",
              "s3_secret_access_key", "s3_key_prefix"):
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
    elif merged.get("base_url"):
        merged["base_url"] = merged["base_url"].rstrip("/")

    if not merged.get("api_key"):
        merged["api_key"] = merged.get("image_api_key") or merged.get("chat_api_key") or ""

    if merged.get("s3_endpoint_url"):
        merged["s3_endpoint_url"] = merged["s3_endpoint_url"].rstrip("/")

    # Chat models
    raw_chat = merged.get("chat_model") or merged.get("model") or "ag/gemini-3.8-flash-high"
    merged["raw_chat_models"] = raw_chat
    chat_models_list = [m.strip() for m in raw_chat.split(",") if m.strip()]
    merged["chat_models"] = chat_models_list if chat_models_list else [raw_chat or "ag/gemini-3.8-flash-high"]
    merged["default_chat_model"] = merged["chat_models"][0]
    merged["chat_model"] = merged["default_chat_model"]
    merged["model"] = merged["default_chat_model"]
    merged["model_name"] = merged["default_chat_model"]

    # Image models
    raw_img = merged.get("image_model") or "cx/gpt-5.6-sol-image"
    merged["raw_image_models"] = raw_img
    models_list = [m.strip() for m in raw_img.split(",") if m.strip()]
    merged["image_models"] = models_list if models_list else [raw_img or "cx/gpt-5.6-sol-image"]
    merged["default_image_model"] = merged["image_models"][0]
    merged["image_model"] = merged["default_image_model"]

    # Video models
    raw_vid = merged.get("video_model") or "grok-imagine-video"
    merged["raw_video_models"] = raw_vid
    vid_models_list = [m.strip() for m in raw_vid.split(",") if m.strip()]
    merged["video_models"] = vid_models_list if vid_models_list else ["zpro-payg/grok-imagine-video", "grok-imagine-video"]
    merged["default_video_model"] = merged["video_models"][0]
    merged["video_model"] = merged["default_video_model"]

    return merged


def save_ai_config(new_config: dict) -> None:
    raise RuntimeError("Cấu hình chỉ được đọc từ file .env. Không thể sửa trên web.")


def is_setup_done() -> bool:
    cfg = get_ai_config()
    return bool(cfg.get("setup_done") or cfg.get("api_key"))


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
