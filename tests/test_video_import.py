from app.services.video_generator import call_ai_generate_video, AVAILABLE_VIDEO_MODELS
from app.config import get_video_models, get_image_models, get_ai_config

assert callable(call_ai_generate_video), "call_ai_generate_video must be callable"
assert isinstance(AVAILABLE_VIDEO_MODELS, list), "AVAILABLE_VIDEO_MODELS must be a list"
assert isinstance(get_video_models(), list), "get_video_models must return list"
assert isinstance(get_image_models(), list), "get_image_models must return list"
print("OK: Video generator and config models imported successfully!")
