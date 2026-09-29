#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI Prompt Studio - System Tray Management Module.
Chứa lớp TrayApp quản lý biểu tượng khay hệ thống (pystray) và vòng đời Web Server Subprocess.
"""

import os
import sys
import time
import socket
import signal
import atexit
import random
import threading
import subprocess
import webbrowser
from pathlib import Path
from typing import Optional

import pystray
from pystray import MenuItem as item, Menu
from PIL import Image, ImageDraw

# Đảm bảo stdout/stderr không bị lỗi khi chạy ở chế độ ẩn không có console (windowless)
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent

# Thư mục cache và file log
CACHE_DIR = ROOT_DIR / ".cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE_PATH = CACHE_DIR / "server.log"
ICON_PATH = ROOT_DIR / "assets" / "icon.png"


def log_message(msg: str):
    """Ghi log vào file .cache/server.log và in ra console nếu có."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] [TRAY] {msg}"
    try:
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass
    try:
        if sys.stdout and not sys.stdout.closed:
            print(formatted)
    except Exception:
        pass


def create_default_icon_image(size: int = 64) -> Image.Image:
    """Tạo icon mặc định sắc nét bằng Pillow (RGBA)."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Nền bo góc mềm mại màu ngọc bích / emerald
    draw.rounded_rectangle(
        [2, 2, size - 3, size - 3],
        radius=14,
        fill=(16, 185, 129, 255),
        outline=(52, 211, 153, 255),
        width=2,
    )
    # Biểu tượng tia sáng / AI ở giữa
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
    """Nạp ảnh icon từ tệp tĩnh assets/icon.png hoặc tự tạo nếu chưa có."""
    candidates = [
        ICON_PATH,
        ROOT_DIR / "assets" / "icon.ico",
        ROOT_DIR / "app" / "static" / "favicon.png",
        ROOT_DIR / "app" / "static" / "favicon.ico",
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
    """Kiểm tra xem một cổng mạng có khả dụng (trống) không."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def find_random_free_port(
    min_port: int = 8000, max_port: int = 9999, host: str = "127.0.0.1"
) -> int:
    """Ưu tiên cổng 8000, nếu đã bị chiếm thì tìm một cổng ngẫu nhiên khả dụng trong dải."""
    if is_port_available(8000, host):
        return 8000

    ports = list(range(min_port, max_port + 1))
    random.shuffle(ports)
    for port in ports[:50]:
        if is_port_available(port, host):
            return port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return s.getsockname()[1]


def terminate_process(proc: Optional[subprocess.Popen]):
    """Tắt sạch sẽ một tiến trình con trên Windows (bao gồm cả cây tiến trình con)."""
    if not proc:
        return
    if proc.poll() is not None:
        return
    try:
        # Dùng taskkill /F /T trên Windows để dọn dẹp toàn bộ process tree
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except Exception:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def get_python_exe() -> Path:
    """Xác định đường dẫn python.exe phù hợp."""
    venv_py = ROOT_DIR / ".venv" / "Scripts" / "python.exe"
    if venv_py.exists():
        return venv_py
    venv_py2 = ROOT_DIR / "venv" / "Scripts" / "python.exe"
    if venv_py2.exists():
        return venv_py2

    cur = Path(sys.executable)
    if cur.name.lower() == "pythonw.exe":
        sibling = cur.parent / "python.exe"
        if sibling.exists():
            return sibling
    return cur


class TrayApp:
    """Quản lý System Tray Icon và điều khiển vòng đời Uvicorn Server Subprocess."""

    def __init__(self):
        self.host = "127.0.0.1"
        self.port = find_random_free_port(host=self.host)
        self.server_process: Optional[subprocess.Popen] = None
        self.icon: Optional[pystray.Icon] = None
        self._lock = threading.Lock()
        self._is_restarting = False

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def start_server(self, reuse_port: bool = True):
        """Khởi động Uvicorn server trong một tiến trình con (Subprocess) hoàn toàn ẩn."""
        with self._lock:
            # Nếu cần dùng lại port cũ (ví dụ khi Restart)
            if reuse_port and self.port:
                start_wait = time.time()
                while time.time() - start_wait < 3.0:
                    if is_port_available(self.port, self.host):
                        break
                    time.sleep(0.2)
                if not is_port_available(self.port, self.host):
                    self.port = find_random_free_port(host=self.host)
            else:
                self.port = find_random_free_port(host=self.host)

            env = os.environ.copy()
            root_dir_str = str(ROOT_DIR.resolve())
            if "PYTHONPATH" in env:
                env["PYTHONPATH"] = f"{root_dir_str}{os.pathsep}{env['PYTHONPATH']}"
            else:
                env["PYTHONPATH"] = root_dir_str

            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUTF8"] = "1"

            py_exe = get_python_exe()
            cmd = [
                str(py_exe),
                str(ROOT_DIR / "run.py"),
                "--host",
                self.host,
                "--port",
                str(self.port),
                "--no-browser",
            ]

            log_message(f"🚀 AI Prompt Studio đang khởi động tại: {self.url} (Port: {self.port})")

            # Thiết lập ẩn hoàn toàn cửa sổ console cho tiến trình con trên Windows
            startupinfo = None
            creationflags = 0
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # SW_HIDE
                creationflags = subprocess.CREATE_NO_WINDOW

            try:
                log_file = open(LOG_FILE_PATH, "a", encoding="utf-8", errors="replace")
                log_file.write(f"\n--- KHỞI ĐỘNG SERVER MỚI [{time.strftime('%Y-%m-%d %H:%M:%S')}] TẠI {self.url} ---\n")
                log_file.flush()
                self.server_process = subprocess.Popen(
                    cmd,
                    cwd=str(ROOT_DIR),
                    env=env,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    startupinfo=startupinfo,
                    creationflags=creationflags,
                )
            except Exception as e:
                log_message(f"Lỗi khởi động server: {e}")

            if self.icon:
                self.icon.title = f"AI Prompt Studio ({self.url})"

    def stop_server(self):
        """Dừng Uvicorn server subprocess và giải phóng cổng mạng."""
        with self._lock:
            if self.server_process:
                pid = self.server_process.pid
                log_message(f"🛑 Đang dừng server (PID: {pid})...")
                terminate_process(self.server_process)
                self.server_process = None
                log_message("Đã dừng server thành công.")

    def restart_server(self):
        """Khởi động lại server để nạp 100% mã nguồn Python/Frontend mới nhất."""
        if self._is_restarting:
            return
        self._is_restarting = True

        def _do_restart():
            try:
                log_message("🔄 ĐANG KHỞI ĐỘNG LẠI SERVER ĐỂ NẠP CODE MỚI...")

                if self.icon:
                    try:
                        self.icon.notify(
                            "Đang nạp lại mã nguồn mới nhất...",
                            "AI Prompt Studio - Restarting",
                        )
                    except Exception:
                        pass

                self.stop_server()
                time.sleep(0.5)
                self.start_server(reuse_port=True)

                # Mở lại trình duyệt sau khi server khởi động
                time.sleep(1.2)
                self.open_browser()

                if self.icon:
                    try:
                        self.icon.notify(
                            f"Đã cập nhật code mới và khởi động lại tại:\n{self.url}",
                            "Khởi Động Lại Thành Công",
                        )
                    except Exception:
                        pass

                log_message(f"✅ Đã khởi động lại thành công tại: {self.url}")
            finally:
                self._is_restarting = False

        threading.Thread(target=_do_restart, daemon=True).start()

    def open_browser(self):
        """Mở trình duyệt web tới trang quản trị."""
        try:
            webbrowser.open(self.url)
        except Exception as e:
            log_message(f"Không thể mở trình duyệt: {e}")

    def open_log_file(self):
        """Mở tệp tin server.log bằng ứng dụng mặc định (Notepad)."""
        try:
            if LOG_FILE_PATH.exists():
                os.startfile(str(LOG_FILE_PATH))
        except Exception as e:
            log_message(f"Không thể mở file log: {e}")

    def quit(self):
        """Thoát hoàn toàn ứng dụng."""
        log_message("❌ Đang tắt AI Prompt Studio...")
        self.stop_server()
        if self.icon:
            self.icon.stop()
        log_message("Tạm biệt!")
        os._exit(0)

    def run(self):
        """Chạy vòng lặp chính của Tray Application."""
        atexit.register(self.stop_server)

        def handle_signal(sig, frame):
            self.quit()

        try:
            signal.signal(signal.SIGINT, handle_signal)
            signal.signal(signal.SIGTERM, handle_signal)
        except Exception:
            pass

        # 1. Khởi động server subprocess
        self.start_server(reuse_port=False)

        # 2. Mở trình duyệt web tự động sau 1.2 giây
        def auto_open():
            time.sleep(1.2)
            self.open_browser()

        threading.Thread(target=auto_open, daemon=True).start()

        # 3. Khởi tạo Tray Icon & Menu ngữ cảnh
        image = load_icon_image()
        menu = Menu(
            item("🌐 Mở Giao Diện Web", lambda icon, item: self.open_browser(), default=True),
            item("🔄 Khởi Động Lại (Restart)", lambda icon, item: self.restart_server()),
            item("📄 Xem File Log (server.log)", lambda icon, item: self.open_log_file()),
            Menu.SEPARATOR,
            item("❌ Thoát (Quit)", lambda icon, item: self.quit()),
        )

        self.icon = pystray.Icon(
            name="ai_prompt_studio",
            icon=image,
            title=f"AI Prompt Studio ({self.url})",
            menu=menu,
        )

        # Chạy message loop của Windows tray icon (blocking main thread)
        self.icon.run()


def run_tray_app():
    """Hàm entry point chạy Tray App."""
    app = TrayApp()
    app.run()
