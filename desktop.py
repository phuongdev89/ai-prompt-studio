"""
AI Prompt Studio - Desktop Application
Khoi dong FastAPI trong thread ngam, mo cua so pywebview.
Man hinh dau tien: Setup cau hinh AI (neu chua setup).
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


def _setup_html(port: int) -> str:
    """Inline HTML cho man hinh Setup cau hinh AI."""
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<title>AI Prompt Studio - Cấu hình</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; display: flex; align-items: center; justify-content: center; }}
  .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 16px; padding: 36px; width: 520px; max-width: 95vw; box-shadow: 0 20px 60px rgba(0,0,0,.5); }}
  h1 {{ font-size: 22px; margin-bottom: 6px; background: linear-gradient(135deg, #22d3ee, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
  .sub {{ font-size: 13px; color: #94a3b8; margin-bottom: 24px; }}
  .tabs {{ display: flex; gap: 8px; margin-bottom: 20px; }}
  .tab {{ flex: 1; padding: 10px; border-radius: 10px; border: 1.5px solid #334155; background: #0f172a; color: #94a3b8; cursor: pointer; font-weight: 600; font-size: 13px; text-align: center; transition: all .2s; }}
  .tab.active {{ border-color: #22d3ee; color: #22d3ee; background: #0c1629; }}
  .tab:hover {{ border-color: #475569; }}
  label {{ display: block; font-size: 12px; font-weight: 600; color: #94a3b8; margin-bottom: 5px; margin-top: 14px; }}
  input {{ width: 100%; padding: 10px 12px; border-radius: 8px; border: 1px solid #334155; background: #0f172a; color: #e2e8f0; font-size: 13px; outline: none; transition: border-color .2s; }}
  input:focus {{ border-color: #22d3ee; }}
  input::placeholder {{ color: #475569; }}
  .row {{ display: flex; gap: 12px; }}
  .row > div {{ flex: 1; }}
  .group {{ display: none; }}
  .group.active {{ display: block; }}
  .btn {{ margin-top: 24px; width: 100%; padding: 12px; border-radius: 10px; border: none; background: linear-gradient(135deg, #0891b2, #7c3aed); color: white; font-size: 14px; font-weight: 700; cursor: pointer; transition: transform .1s, box-shadow .2s; }}
  .btn:hover {{ box-shadow: 0 4px 20px rgba(8,145,178,.4); }}
  .btn:active {{ transform: scale(.98); }}
  .btn:disabled {{ opacity: .5; cursor: not-allowed; }}
  .msg {{ margin-top: 12px; font-size: 12px; text-align: center; min-height: 18px; }}
  .msg.err {{ color: #f87171; }}
  .msg.ok {{ color: #34d399; }}
  .hint {{ font-size: 11px; color: #64748b; margin-top: 3px; }}
</style>
</head>
<body>
<div class="card">
  <h1>AI Prompt Studio</h1>
  <p class="sub">Cấu hình kết nối AI trước khi bắt đầu. Thông tin được lưu vĩnh viễn trên máy.</p>

  <div class="tabs">
    <div class="tab active" onclick="switchProvider('openai')" id="tabOpenAI">Custom OpenAI</div>
  </div>

  <div class="group active" id="grpOpenAI">
    <label>Base URL</label>
    <input id="baseUrl" placeholder="https://api.openai.com/v1" value="https://api.openai.com/v1">
    <p class="hint">Hỗ trợ OpenAI, OpenRouter, 9Router, Ollama, v.v.</p>

    <label>API Key</label>
    <input id="apiKey" type="password" placeholder="sk-...">

    <label>Model</label>
    <input id="model" placeholder="gpt-4o-mini" value="gpt-4o-mini">
    <p class="hint">Một model duy nhất dùng cho chat, tạo ảnh và mọi tác vụ AI.</p>
  </div>

  <div class="row" style="margin-top:14px">
    <div>
      <label>Timeout (giây)</label>
      <input id="timeout" type="number" value="300" min="30" max="600">
    </div>
  </div>

  <button class="btn" id="startBtn" onclick="doStart()">Bắt đầu sử dụng</button>
  <div class="msg" id="msg"></div>
</div>

<script>
let provider = 'openai';

function switchProvider(p) {{
  provider = 'openai';
}}

async function doStart() {{
  const btn = document.getElementById('startBtn');
  const msg = document.getElementById('msg');
  btn.disabled = true;
  btn.textContent = 'Đang lưu cấu hình...';
  msg.className = 'msg';
  msg.textContent = '';

  const payload = {{
    provider: 'openai',
    base_url: document.getElementById('baseUrl').value.trim(),
    api_key: document.getElementById('apiKey').value.trim(),
    model: document.getElementById('model').value.trim() || 'gpt-4o-mini',
    timeout: parseInt(document.getElementById('timeout').value) || 300,
    stream: true,
    setup_done: true,
  }};

  // Validate
  if (!payload.api_key) {{
    msg.className = 'msg err';
    msg.textContent = 'Vui lòng nhập API Key cho OpenAI.';
    btn.disabled = false;
    btn.textContent = 'Bắt đầu sử dụng';
    return;
  }}

  try {{
    const resp = await fetch('http://127.0.0.1:{port}/api/config', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify(payload)
    }});
    const data = await resp.json();
    if (data.ok) {{
      msg.className = 'msg ok';
      msg.textContent = 'Đã lưu! Đang mở ứng dụng...';
      setTimeout(() => {{
        // Maximize window via pywebview JS API, then navigate
        if (window.pywebview) {{
          window.pywebview.api && window.pywebview.api.maximize && window.pywebview.api.maximize();
        }}
        window.location.href = 'http://127.0.0.1:{port}';
      }}, 600);
    }} else {{
      throw new Error('Server error');
    }}
  }} catch (e) {{
    msg.className = 'msg err';
    msg.textContent = 'Lỗi kết nối server: ' + e.message;
    btn.disabled = false;
    btn.textContent = 'Bắt đầu sử dụng';
  }}
}}

// Pre-fill from existing config
(async () => {{
  try {{
    const resp = await fetch('http://127.0.0.1:{port}/api/config');
    const cfg = await resp.json();
    if (cfg.base_url) document.getElementById('baseUrl').value = cfg.base_url;
    if (cfg.model) document.getElementById('model').value = cfg.model;
    if (cfg.timeout) document.getElementById('timeout').value = cfg.timeout;
    // Keys are masked — don't prefill, but show hint
    if (cfg.has_api_key) document.getElementById('apiKey').placeholder = '••••••• (đã lưu, để trống = giữ nguyên)';
  }} catch(e) {{}}
}})();
</script>
</body>
</html>"""


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
    from app.config import find_free_port, is_setup_done

    global _PORT
    _PORT = find_free_port()
    url = f"http://127.0.0.1:{_PORT}"

    # Start server in daemon thread
    server_thread = threading.Thread(target=start_server, args=(_PORT,), daemon=True)
    server_thread.start()

    # Decide start page: setup or main app
    if is_setup_done():
        start_url = url
    else:
        start_url = None  # will load setup HTML

    _IS_FROZEN = getattr(sys, "frozen", False)

    # Holder for window reference (Api needs it before window is assigned)
    win_ref = [None]
    api = Api(win_ref)

    window = webview.create_window(
        title="AI Prompt Studio",
        url=start_url if start_url else None,
        html=None if start_url else _setup_html(_PORT),
        width=1400 if start_url else 560,
        height=900 if start_url else 680,
        min_size=(900, 600) if start_url else (520, 600),
        resizable=True,
        text_select=True,
        js_api=api,
    )
    win_ref[0] = window

    if start_url:
        # Already configured — maximize on start
        def _on_shown():
            window.maximize()
        window.events.shown += _on_shown
    else:
        # Setup screen — watch for navigation to main app, then maximize
        def _on_loaded():
            current = window.get_current_url() or ""
            if f":{_PORT}" in current and "/api/" not in current:
                window.maximize()
        window.events.loaded += _on_loaded

    webview.start(gui="edgechromium", debug=False)

    # Cleanup PID file on exit
    pid_file = ROOT_DIR / ".server.pid"
    if pid_file.exists():
        pid_file.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
