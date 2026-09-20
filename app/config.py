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
    "model": "gpt-4o-mini",
    "chat_model": "gpt-4o-mini",
    "image_model": "cx/gpt-5.6-sol-image",
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
    "AI_MODEL": "model",
    "AI_CHAT_MODEL": "chat_model",
    "AI_IMAGE_MODEL": "image_model",
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

    for k in ("provider", "base_url", "api_key", "model", "chat_model", "image_model",
              "s3_endpoint_url", "s3_region", "s3_bucket", "s3_access_key_id",
              "s3_secret_access_key", "s3_key_prefix"):
        if isinstance(merged.get(k), str):
            merged[k] = merged[k].strip().strip('"').strip("'")

    if merged.get("base_url"):
        merged["base_url"] = merged["base_url"].rstrip("/")
    if merged.get("s3_endpoint_url"):
        merged["s3_endpoint_url"] = merged["s3_endpoint_url"].rstrip("/")

    if not merged.get("chat_model"):
        merged["chat_model"] = merged.get("model", "gpt-4o-mini")
    if not merged.get("image_model"):
        merged["image_model"] = merged.get("chat_model") or merged.get("model", "gpt-4o-mini")
    merged["model_name"] = merged["chat_model"]
    return merged


def save_ai_config(cfg: dict):
    raise RuntimeError("Cấu hình chỉ được đọc từ file .env. Không thể sửa trên web.")


def is_setup_done() -> bool:
    cfg = get_ai_config()
    return bool(cfg.get("setup_done") or cfg.get("api_key"))


# Ensure required directories exist
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
