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
    provider = os.getenv("AI_PROVIDER", "openai").strip().lower()
    base_url = os.getenv("AI_BASE_URL", "https://api.openai.com/v1").strip().strip('"').strip("'").rstrip("/")
    api_key = os.getenv("AI_API_KEY", "").strip().strip('"').strip("'")
    chat_model = (os.getenv("AI_CHAT_MODEL") or os.getenv("AI_MODEL_NAME", "gpt-4o-mini")).strip().strip('"').strip("'")
    image_model = (os.getenv("AI_IMAGE_MODEL") or chat_model).strip().strip('"').strip("'")
    
    # Gemini Direct Official API
    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip().strip('"').strip("'")
    gemini_chat_model = (os.getenv("GEMINI_CHAT_MODEL") or "gemini-2.0-flash").strip().strip('"').strip("'")
    gemini_image_model = (os.getenv("GEMINI_IMAGE_MODEL") or "imagen-3.0-generate-002").strip().strip('"').strip("'")

    timeout = int(os.getenv("AI_TIMEOUT", "300"))
    stream = os.getenv("AI_STREAM", "True").lower() in ("true", "1", "yes")
    return {
        "provider": provider,  # 'openai' or 'gemini'
        "base_url": base_url,
        "api_key": api_key,
        "chat_model": chat_model,
        "model_name": chat_model,  # Giữ alias tương thích
        "image_model": image_model,
        "gemini_api_key": gemini_api_key,
        "gemini_chat_model": gemini_chat_model,
        "gemini_image_model": gemini_image_model,
        "timeout": timeout,
        "stream": stream
    }

# Ensure required directories exist
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
