import sys
import os
import time
import threading
import webbrowser
import argparse
import socket
import random
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
from app.config import HOST, PORT, DB_PATH
from app.db.database import ensure_database

def is_port_free(host: str, port: int) -> bool:
    """Kiểm tra xem port trên host có đang khả dụng không."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass

def find_available_port(host: str, preferred_port: int, max_attempts: int = 500) -> int:
    """
    Nếu preferred_port đang bận, tự động chọn ngẫu nhiên các port khác
    cho tới khi tìm thấy port còn trống.
    """
    if is_port_free(host, preferred_port):
        return preferred_port

    print(f"[!] Cảnh báo: Port {preferred_port} đang bị chiếm dụng!")
    print(f"[*] Đang tự động tìm kiếm một port ngẫu nhiên còn trống...")

    tested_ports = {preferred_port}
    for _ in range(max_attempts):
        candidate = random.randint(8001, 65535)
        if candidate in tested_ports:
            continue
        tested_ports.add(candidate)
        if is_port_free(host, candidate):
            print(f"[+] Đã chọn port ngẫu nhiên khả dụng: {candidate}")
            return candidate

    # Fallback cho OS tự cấp phát port nếu thử nhiều lần không được
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((host, 0))
    assigned_port = s.getsockname()[1]
    s.close()
    print(f"[+] Đã cấp phát port ngẫu nhiên từ hệ thống: {assigned_port}")
    return assigned_port

def open_browser_delayed(url: str, delay: float = 1.2):
    def _open():
        time.sleep(delay)
        print(f"[*] Đang mở trình duyệt tại {url} ...")
        webbrowser.open(url)
    threading.Thread(target=_open, daemon=True).start()

def main():
    parser = argparse.ArgumentParser(description="AI Prompt Studio - Web Server")
    parser.add_argument("--host", type=str, default=HOST, help=f"Host (mặc định: {HOST})")
    parser.add_argument("--port", type=int, default=PORT, help=f"Port (mặc định: {PORT})")
    parser.add_argument("--reload", action="store_true", default=True, help="Bật chế độ Auto-reload (mặc định: True)")
    parser.add_argument("--no-reload", dest="reload", action="store_false", help="Tắt chế độ Auto-reload")
    parser.add_argument("--no-browser", action="store_true", help="Không tự động mở trình duyệt")

    args = parser.parse_args()

    # Tìm port khả dụng nếu port ban đầu bị chiếm dụng
    active_port = find_available_port(args.host, args.port)

    browser_host = "127.0.0.1" if args.host in ("0.0.0.0", "") else args.host
    url = f"http://{browser_host}:{active_port}"

    print("==================================================")
    print("       🚀 AI PROMPT STUDIO - WEB SERVER")
    print("==================================================")
    print(f" - Cơ sở dữ liệu : {DB_PATH}")
    print(f" - Địa chỉ Web   : {url}")
    print(f" - Auto-reload   : {args.reload}")
    print("--------------------------------------------------")

    # Ensure database is initialized and migrated
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

