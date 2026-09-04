import os
from pathlib import Path
from dotenv import load_dotenv

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = BASE_DIR / "app"
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "prompts.db"
JSON_DATA_PATH = DATA_DIR / "cleaned_prompts.json"
IMAGES_DIR = DATA_DIR / "images"
STATIC_DIR = APP_DIR / "static"
TEMPLATES_DIR = APP_DIR / "templates"

# Server configuration
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", 8000))
DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")

# Dynamic AI Configuration Loader (re-reads .env on demand)
def get_ai_config():
    load_dotenv(BASE_DIR / ".env", override=True)
    base_url = os.getenv("AI_BASE_URL", "https://api.openai.com/v1").strip().strip('"').strip("'").rstrip("/")
    api_key = os.getenv("AI_API_KEY", "").strip().strip('"').strip("'")
    chat_model = (os.getenv("AI_CHAT_MODEL") or os.getenv("AI_MODEL_NAME", "gpt-4o-mini")).strip().strip('"').strip("'")
    image_model = (os.getenv("AI_IMAGE_MODEL") or chat_model).strip().strip('"').strip("'")
    timeout = int(os.getenv("AI_TIMEOUT", "300"))
    stream = os.getenv("AI_STREAM", "True").lower() in ("true", "1", "yes")
    return {
        "base_url": base_url,
        "api_key": api_key,
        "chat_model": chat_model,
        "model_name": chat_model,  # Giữ alias tương thích
        "image_model": image_model,
        "timeout": timeout,
        "stream": stream
    }

# Ensure required directories exist
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
