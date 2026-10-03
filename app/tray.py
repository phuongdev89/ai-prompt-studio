#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI Prompt Studio - System Tray Management Module.
Quản lý biểu tượng khay hệ thống (pystray), kiểm tra đơn thực thể (Single Instance),
và vòng đời Web Server (Uvicorn).
"""

import os
import sys
import time
import socket
import signal
import atexit
import random
import ctypes
import threading
import webbrowser
from pathlib import Path
from typing import Optional

import pystray
from pystray import MenuItem as item, Menu
from PIL import Image, ImageDraw
import uvicorn

# Đảm bảo stdout/stderr an toàn khi chạy ở chế độ ẩn (windowless)
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

if getattr(sys, "frozen", False):
    ROOT_DIR = Path(sys.executable).resolve().parent
else:
    ROOT_DIR = Path(__file__).resolve().parent.parent

CACHE_DIR = ROOT_DIR / ".cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE_PATH = CACHE_DIR / "server.log"
URL_FILE_PATH = CACHE_DIR / "server.url"
ICON_PATH = ROOT_DIR / "assets" / "icon.png"

MUTEX_NAME = r"Local\AIPromptStudio_SingleInstance"
ERROR_ALREADY_EXISTS = 183


def log_message(msg: str):
    """Ghi log vào file .cache/server.log."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] [TRAY] {msg}"
    try:
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass


def create_default_icon_image(size: int = 64) -> Image.Image:
    """Tạo icon mặc định sắc nét bằng Pillow (RGBA)."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(
        [2, 2, size - 3, size - 3],
        radius=14,
        fill=(16, 185, 129, 255),
        outline=(52, 211, 153, 255),
        width=2,
    )
    center = size // 2
    draw.polygon(
        [
            (center, 12),
            (center + 6, 26),
            (size - 12, center),
            (center + 6, center + 6),
            (center, size - 12),
            (center - 6, center + 6),
            (12, center),
            (center - 6, 26),
        ],
        fill=(255, 255, 255, 255),
    )
    return img


def load_icon_image() -> Image.Image:
    """Nạp icon từ assets/icon.ico hoặc icon.png."""
    candidates = [
        ROOT_DIR / "assets" / "icon.ico",
        ROOT_DIR / "assets" / "icon.png",
        ROOT_DIR / "_internal" / "assets" / "icon.ico",
        ROOT_DIR / "_internal" / "assets" / "icon.png",
        ROOT_DIR / "app" / "static" / "favicon.png",
        ROOT_DIR / "app" / "static" / "favicon.ico",
        ROOT_DIR / "_internal" / "app" / "static" / "favicon.png",
        ROOT_DIR / "_internal" / "app" / "static" / "favicon.ico",
    ]
    for p in candidates:
        if p.exists():
            try:
                return Image.open(p)
            except Exception:
                pass

    icon_img = create_default_icon_image()
    try:
        ICON_PATH.parent.mkdir(parents=True, exist_ok=True)
        icon_img.save(ICON_PATH)
    except Exception:
        pass
    return icon_img


def is_port_available(port: int, host: str = "127.0.0.1") -> bool:
    """Kiểm tra cổng mạng có khả dụng không."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def find_free_port(host: str = "127.0.0.1") -> int:
    """Cấp một cổng ngẫu nhiên trống từ hệ điều hành mỗi khi chạy."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return s.getsockname()[1]


class TrayApp:
    """Quản lý System Tray Icon và Uvicorn Server."""

    def __init__(self, mutex_handle=None):
        self._mutex = mutex_handle
        self.host = "127.0.0.1"
        self.port = find_free_port(host=self.host)
        self.server: Optional[uvicorn.Server] = None
        self.server_thread: Optional[threading.Thread] = None
        self.icon: Optional[pystray.Icon] = None
        self._lock = threading.Lock()
        self._is_restarting = False

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def start_server(self, reuse_port: bool = True):
        """Khởi động Uvicorn server trong thread ngầm."""
        with self._lock:
            if not reuse_port or not self.port or not is_port_available(self.port, self.host):
                self.port = find_free_port(host=self.host)

            log_message(f"Khởi động server tại {self.url}...")
            try:
                from app.db.database import ensure_database
                from app.main import app

                ensure_database()

                config = uvicorn.Config(
                    app,
                    host=self.host,
                    port=self.port,
                    log_level="warning",
                )
                self.server = uvicorn.Server(config)
                self.server_thread = threading.Thread(target=self.server.run, daemon=True)
                self.server_thread.start()

                # Lưu URL vào file để instance sau có thể đọc và mở web
                try:
                    URL_FILE_PATH.write_text(self.url, encoding="utf-8")
                except Exception:
                    pass

                if self.icon:
                    self.icon.title = f"AI Prompt Studio ({self.url})"
            except Exception as e:
                import traceback
                log_message(f"Lỗi khởi động server: {e}\n{traceback.format_exc()}")

    def stop_server(self):
        """Dừng Uvicorn server."""
        with self._lock:
            if self.server:
                log_message("Dừng server...")
                self.server.should_exit = True
                if self.server_thread and self.server_thread.is_alive():
                    self.server_thread.join(timeout=3.0)
                self.server = None
                self.server_thread = None

            try:
                URL_FILE_PATH.unlink(missing_ok=True)
            except Exception:
                pass

    def restart_server(self):
        """Khởi động lại server."""
        if self._is_restarting:
            return
        self._is_restarting = True

        def _do_restart():
            try:
                log_message("Khởi động lại server...")
                if self.icon:
                    try:
                        self.icon.notify("Đang khởi động lại server...", "AI Prompt Studio")
                    except Exception:
                        pass
                self.stop_server()
                time.sleep(0.5)
                self.start_server(reuse_port=True)
                time.sleep(0.5)
                self.open_browser()
            finally:
                self._is_restarting = False

        threading.Thread(target=_do_restart, daemon=True).start()

    def open_browser(self):
        """Mở giao diện web trên trình duyệt mặc định."""
        try:
            webbrowser.open(self.url)
        except Exception as e:
            log_message(f"Không thể mở trình duyệt: {e}")

    def open_log_file(self):
        """Mở file server.log."""
        try:
            if LOG_FILE_PATH.exists():
                os.startfile(str(LOG_FILE_PATH))
        except Exception as e:
            log_message(f"Không thể mở log: {e}")

    def open_env_file(self):
        """Mở tệp .env mặc định bằng Notepad của Windows."""
        from app.config import ENV_PATH, BASE_DIR
        import subprocess, shutil
        try:
            if not ENV_PATH.exists():
                example = BASE_DIR / ".env.example"
                if example.exists():
                    shutil.copyfile(example, ENV_PATH)
                else:
                    ENV_PATH.write_text("SETUP_DONE=false\nAFFILIATE_ROOT=\n", encoding="utf-8")
            subprocess.Popen(["notepad.exe", str(ENV_PATH)])
            log_message(f"Đã mở Notepad chỉnh sửa {ENV_PATH}")
        except Exception as e:
            log_message(f"Không thể mở file .env bằng Notepad: {e}")

    def trigger_backup(self):
        """Sao lưu database ngay lập tức từ tray icon."""
        from app.config import backup_database, get_backup_dir
        bk_dir = get_backup_dir()
        if not bk_dir:
            log_message("Chưa thiết lập AFFILIATE_ROOT trong file .env để sao lưu!")
            if self.icon:
                try:
                    self.icon.notify("Chưa thiết lập AFFILIATE_ROOT trong .env!", "AI Prompt Studio")
                except Exception:
                    pass
            return

        bk = backup_database()
        if bk:
            log_message(f"Đã sao lưu database thành công: {bk}")
            if self.icon:
                try:
                    self.icon.notify(f"Đã sao lưu thành công tại:\n{bk.name}", "Sao Lưu Database")
                except Exception:
                    pass
        else:
            log_message("Sao lưu database thất bại!")
            if self.icon:
                try:
                    self.icon.notify("Không tìm thấy database hoặc lỗi sao lưu.", "Lỗi Sao Lưu")
                except Exception:
                    pass

    def open_app_dir(self):
        """Mở thư mục cài đặt ứng dụng."""
        from app.config import BASE_DIR
        try:
            os.startfile(str(BASE_DIR))
        except Exception as e:
            log_message(f"Không thể mở thư mục cài đặt: {e}")

    def quit(self):
        """Thoát hoàn toàn ứng dụng và tự động sao lưu database."""
        log_message("Thoát AI Prompt Studio...")
        try:
            from app.config import backup_database
            bk = backup_database()
            if bk:
                log_message(f"Đã tự động sao lưu database trước khi thoát: {bk}")
        except Exception as e:
            log_message(f"Lỗi sao lưu database khi thoát: {e}")

        self.stop_server()
        if self.icon:
            self.icon.stop()
        if self._mutex:
            try:
                ctypes.windll.kernel32.CloseHandle(self._mutex)
            except Exception:
                pass
            self._mutex = None
        os._exit(0)

    def run(self):
        """Vòng lặp chính của Tray App."""
        atexit.register(self.stop_server)

        def handle_signal(sig, frame):
            self.quit()

        try:
            signal.signal(signal.SIGINT, handle_signal)
            signal.signal(signal.SIGTERM, handle_signal)
        except Exception:
            pass

        self.start_server(reuse_port=False)

        # Tự động mở trình duyệt sau khi server chạy
        def auto_open():
            time.sleep(1.0)
            self.open_browser()

        threading.Thread(target=auto_open, daemon=True).start()

        image = load_icon_image()
        menu = Menu(
            item("🌐 Mở Giao Diện Web", lambda icon, item: self.open_browser(), default=True),
            item("⚙️ Cấu hình .env", lambda icon, item: self.open_env_file()),
            item("💾 Sao Lưu Database", lambda icon, item: self.trigger_backup()),
            item("📁 Thư Mục Cài Đặt", lambda icon, item: self.open_app_dir()),
            item("🔄 Khởi Động Lại", lambda icon, item: self.restart_server()),
            item("📄 Xem Log", lambda icon, item: self.open_log_file()),
            Menu.SEPARATOR,
            item("❌ Thoát", lambda icon, item: self.quit()),
        )

        self.icon = pystray.Icon(
            name="ai_prompt_studio",
            icon=image,
            title=f"AI Prompt Studio ({self.url})",
            menu=menu,
        )
        self.icon.run()


def run_tray_app():
    """Kiểm tra Single Instance trước khi chạy."""
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_bool

    mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        if mutex:
            kernel32.CloseHandle(mutex)
        # Đã có phiên bản đang chạy -> mở web và thoát
        target_url = "http://127.0.0.1:8000"
        for _ in range(15):
            if URL_FILE_PATH.exists():
                try:
                    saved = URL_FILE_PATH.read_text(encoding="utf-8").strip()
                    if saved.startswith("http"):
                        target_url = saved
                        break
                except Exception:
                    pass
            time.sleep(0.1)
        webbrowser.open(target_url)
        sys.exit(0)

    app = TrayApp(mutex_handle=mutex)
    app.run()
