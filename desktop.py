"""
AI Prompt Studio - Desktop Application
Khoi dong FastAPI trong thread ngam, mo cua so pywebview.
Cau hinh chi doc tu file .env (khong co man hinh setup tren app).
"""
import sys
import os
import threading
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Root directory: frozen exe -> exe dir, dev -> script dir
if getattr(sys, "frozen", False):
    ROOT_DIR = Path(sys.executable).resolve().parent
else:
    ROOT_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(ROOT_DIR))
os.chdir(str(ROOT_DIR))

import uvicorn
import webview

# Global — server port, set once
_PORT = None


def start_server(port: int):
    """Chay FastAPI/Uvicorn trong thread ngam."""
    from app.db.database import ensure_database
    ensure_database()
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )



class Api:
    """Exposed to JS via window.pywebview.api"""
    def __init__(self, win_ref):
        self._win = win_ref

    def save_file(self, filename, data_uri):
        """Open native Save-As dialog and write binary data."""
        import base64
        win = self._win[0]
        result = win.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=filename,
        )
        if not result:
            return False
        path = result if isinstance(result, str) else result[0]
        # data_uri: "data:image/png;base64,xxxxx"
        header, b64 = data_uri.split(",", 1)
        with open(path, "wb") as f:
            f.write(base64.b64decode(b64))
        return path


def main():
    from app.config import find_free_port

    global _PORT
    _PORT = find_free_port()
    url = f"http://127.0.0.1:{_PORT}"

    # Start server in daemon thread
    server_thread = threading.Thread(target=start_server, args=(_PORT,), daemon=True)
    server_thread.start()

    # Holder for window reference (Api needs it before window is assigned)
    win_ref = [None]
    api = Api(win_ref)

    window = webview.create_window(
        title="AI Prompt Studio",
        url=url,
        width=1400,
        height=900,
        min_size=(900, 600),
        resizable=True,
        text_select=True,
        js_api=api,
    )
    win_ref[0] = window

    def _on_shown():
        window.maximize()
    window.events.shown += _on_shown

    webview.start(gui="edgechromium", debug=False)

    # Cleanup PID file on exit
    pid_file = ROOT_DIR / ".server.pid"
    if pid_file.exists():
        pid_file.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
