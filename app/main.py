import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from app.config import STATIC_DIR, IMAGES_DIR, TEMPLATES_DIR, DEBUG
from app.db.database import ensure_database
from app.api import api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure SQLite database and tables exist
    ensure_database()
    yield

app = FastAPI(
    title="AI Prompt Studio",
    description="Web Server quản lý và tùy biến bộ Prompt AI đa năng",
    version="1.0.0",
    lifespan=lifespan,
    debug=DEBUG
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
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/media", StaticFiles(directory=str(IMAGES_DIR)), name="media")

# Include REST API
app.include_router(api_router)

# Serve SPA UI
@app.api_route("/", methods=["GET", "POST", "HEAD"], response_class=HTMLResponse)
@app.api_route("/index.html", methods=["GET", "POST", "HEAD"], response_class=HTMLResponse)
async def serve_index(request: Request):
    index_file = TEMPLATES_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return HTMLResponse("<h1>AI Prompt Studio is running. index.html not found in templates.</h1>")

@app.get("/health")
async def health_check():
    return {"status": "ok", "app": "AI Prompt Studio"}

# SPA routes for tab & prompt URL handling
@app.get("/{category}", response_class=HTMLResponse)
@app.get("/{category}/{prompt_id}", response_class=HTMLResponse)
async def serve_spa_route(category: str, prompt_id: str = None):
    # Avoid intercepting API, static, media or system endpoints
    if category in ["api", "static", "media", "docs", "redoc", "openapi.json", "health", "favicon.ico"]:
        raise HTTPException(status_code=404, detail="Not Found")
    index_file = TEMPLATES_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return HTMLResponse("<h1>AI Prompt Studio is running. index.html not found in templates.</h1>")
