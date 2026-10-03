import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from app.config import PUBLIC_DIR, STATIC_DIR, IMAGES_DIR, TEMPLATES_DIR, DEBUG
from app.db.database import ensure_database
from app.api import api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure SQLite database and tables exist
    ensure_database()
    yield

TAGS_METADATA = [
    {
        "name": "prompts",
        "description": "Quản lý cơ sở dữ liệu câu lệnh prompt: tra cứu, thêm mới, cập nhật, xóa, gắn tags, rút gọn và phân tích."
    },
    {
        "name": "ai",
        "description": "Các tác vụ tích hợp AI: sinh nội dung, tạo ảnh, render video, trích xuất JSON VisionStruct và trợ lý tìm kiếm."
    },
    {
        "name": "koc",
        "description": "Quản lý thư viện hình ảnh và nhân vật KOC AI chuyên nghiệp."
    },
    {
        "name": "s3",
        "description": "Dịch vụ đồng bộ lưu trữ đám mây S3 / Cloud Storage cho tài sản số."
    },
    {
        "name": "system",
        "description": "Cấu hình hệ thống, kiểm tra sức khỏe và thao tác tệp."
    }
]

app = FastAPI(
    title="AI Prompt Studio API",
    description="""
### Hệ sinh thái Quản lý & Tùy biến Câu lệnh Prompt AI Đa Năng
Hỗ trợ cả giao diện đồ họa Web SPA và giao diện dòng lệnh Headless CLI (`aff-prompt`).
- **Core Database:** SQLite lưu trữ 400+ prompt tối ưu hóa cho hình ảnh, video storyboard và nội dung tiếp thị.
- **AI Integrations:** OpenAI, Midjourney, Kling, Veo, Gemini, Seedance.
- **Headless First:** Vận hành độc lập qua lệnh `aff-prompt` với định dạng `--json` tiêu chuẩn.
    """,
    version="1.1.0",
    lifespan=lifespan,
    debug=DEBUG,
    openapi_tags=TAGS_METADATA,
    openapi_url="/docs/api/openapi.json",
    docs_url="/docs/api/swagger",
    redoc_url="/docs/api/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Assets & Local Images
app.mount("/public", StaticFiles(directory=str(PUBLIC_DIR)), name="public")
app.mount("/static", StaticFiles(directory=str(PUBLIC_DIR)), name="static")
app.mount("/media", StaticFiles(directory=str(IMAGES_DIR)), name="media")
app.mount("/data/images", StaticFiles(directory=str(IMAGES_DIR)), name="data_images")

# Include REST API
app.include_router(api_router)

# API Documentation Redirects
@app.get("/docs/api", include_in_schema=False)
async def docs_api_hub():
    return RedirectResponse(url="/docs/api/swagger")

@app.get("/docs", include_in_schema=False)
async def redirect_old_docs():
    return RedirectResponse(url="/docs/api/swagger")

@app.get("/redoc", include_in_schema=False)
async def redirect_old_redoc():
    return RedirectResponse(url="/docs/api/redoc")

@app.get("/openapi.json", include_in_schema=False)
async def redirect_old_openapi():
    return RedirectResponse(url="/docs/api/openapi.json")

# Favicon direct route
@app.get("/favicon.ico", include_in_schema=False)
async def serve_favicon():
    favicon_file = PUBLIC_DIR / "favicon.ico"
    if favicon_file.exists():
        return FileResponse(str(favicon_file), media_type="image/x-icon")
    raise HTTPException(status_code=404, detail="Favicon not found")

# Serve SPA UI
@app.api_route("/", methods=["GET", "POST", "HEAD"], response_class=HTMLResponse, include_in_schema=False)
@app.api_route("/index.html", methods=["GET", "POST", "HEAD"], response_class=HTMLResponse, include_in_schema=False)
async def serve_index(request: Request):
    index_file = PUBLIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return HTMLResponse("<h1>AI Prompt Studio is running. index.html not found in public.</h1>")

@app.get("/health", tags=["system"])
async def health_check():
    return {"status": "ok", "app": "AI Prompt Studio"}

# SPA routes for tab & prompt URL handling
@app.get("/{category}", response_class=HTMLResponse, include_in_schema=False)
@app.get("/{category}/{prompt_id}", response_class=HTMLResponse, include_in_schema=False)
async def serve_spa_route(category: str, prompt_id: str = None):
    # Avoid intercepting API, static, media or system endpoints
    if category in ["api", "public", "static", "media", "docs", "redoc", "openapi.json", "health", "favicon.ico"]:
        raise HTTPException(status_code=404, detail="Not Found")
    index_file = PUBLIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return HTMLResponse("<h1>AI Prompt Studio is running. index.html not found in public.</h1>")
