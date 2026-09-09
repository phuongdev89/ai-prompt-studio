import sys
import os
import time
import threading
import webbrowser
import argparse
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add root directory to python path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

import uvicorn
from app.config import HOST, DB_PATH, find_free_port
from app.db.database import ensure_database

def open_browser_delayed(url: str, delay: float = 1.2):
    def _open():
        time.sleep(delay)
        print(f"[*] Đang mở trình duyệt tại {url} ...")
        webbrowser.open(url)
    threading.Thread(target=_open, daemon=True).start()

def main():
    parser = argparse.ArgumentParser(description="AI Prompt Studio - Web Server")
    parser.add_argument("--host", type=str, default=HOST, help=f"Host (mặc định: {HOST})")
    parser.add_argument("--port", type=int, default=0, help="Port (mặc định: random)")
    parser.add_argument("--reload", action="store_true", default=True, help="Bật chế độ Auto-reload (mặc định: True)")
    parser.add_argument("--no-reload", dest="reload", action="store_false", help="Tắt chế độ Auto-reload")
    parser.add_argument("--no-browser", action="store_true", help="Không tự động mở trình duyệt")

    args = parser.parse_args()

    active_port = args.port if args.port else find_free_port()

    browser_host = "127.0.0.1" if args.host in ("0.0.0.0", "") else args.host
    url = f"http://{browser_host}:{active_port}"

    print("==================================================")
    print("       AI PROMPT STUDIO - WEB SERVER")
    print("==================================================")
    print(f" - Cơ sở dữ liệu : {DB_PATH}")
    print(f" - Địa chỉ Web   : {url}")
    print(f" - Auto-reload   : {args.reload}")
    print("--------------------------------------------------")

    ensure_database()

    if not args.no_browser:
        open_browser_delayed(url)

    print(f"[*] Khởi động máy chủ tại {url} (Nhấn Ctrl+C để dừng)...")
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=active_port,
        reload=args.reload,
        log_level="info"
    )

if __name__ == "__main__":
    main()
