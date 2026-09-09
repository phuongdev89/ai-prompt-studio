import os
import sys
import json
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
CONFIG_PATH = DATA_DIR / "config.json"

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
#  Config persistence — JSON file in data/config.json
# ============================================================

_DEFAULT_CONFIG = {
    "provider": "openai",       # 'openai' or 'gemini'
    "base_url": "https://api.openai.com/v1",
    "api_key": "",
    "model": "gpt-4o-mini",
    "gemini_api_key": "",
    "gemini_model": "gemini-2.5-flash",
    "timeout": 300,
    "stream": True,
    "setup_done": False,
}


def _load_config_file() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text("utf-8"))
        except Exception:
            pass
    return {}


def _save_config_file(cfg: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def get_ai_config() -> dict:
    """Load AI config from config.json, merged with defaults."""
    saved = _load_config_file()
    merged = {**_DEFAULT_CONFIG, **saved}

    # Strip whitespace from string values
    for k in ("provider", "base_url", "api_key", "model", "gemini_api_key", "gemini_model"):
        if isinstance(merged.get(k), str):
            merged[k] = merged[k].strip().strip('"').strip("'")

    if merged["provider"] == "openai" and merged.get("base_url"):
        merged["base_url"] = merged["base_url"].rstrip("/")

    # Backward compat aliases — single model for everything
    merged["chat_model"] = merged["model"]
    merged["model_name"] = merged["model"]
    merged["image_model"] = merged["model"]
    merged["gemini_chat_model"] = merged["gemini_model"]
    merged["gemini_image_model"] = merged["gemini_model"]
    return merged


def save_ai_config(cfg: dict):
    """Save AI config to config.json. Only persists known keys.
    Empty string for api_key/gemini_api_key means keep existing value."""
    current = _load_config_file()
    for k in _DEFAULT_CONFIG:
        if k in cfg:
            # Don't overwrite existing keys with empty string
            if k in ("api_key", "gemini_api_key") and not cfg[k]:
                continue
            current[k] = cfg[k]
    current["setup_done"] = True
    _save_config_file(current)


def is_setup_done() -> bool:
    cfg = _load_config_file()
    return cfg.get("setup_done", False)


# Ensure required directories exist
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
