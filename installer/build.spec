# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# Project root (parent of installer/)
SPEC_DIR = os.path.dirname(os.path.abspath(SPEC)) if 'SPEC' in locals() else os.path.abspath('.')
if os.path.basename(SPEC_DIR) == 'installer':
    ROOT_DIR = os.path.dirname(SPEC_DIR)
else:
    ROOT_DIR = SPEC_DIR

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Hidden imports
hidden_imports = [
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'fastapi',
    'pydantic',
    'sqlite3',
    'pystray',
    'pystray._win32',
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'ctypes',
] + collect_submodules('app')

datas = [
    (os.path.join(ROOT_DIR, 'public'), 'public'),
]

# .version file
version_file = os.path.join(ROOT_DIR, '.version')
if os.path.exists(version_file):
    datas.append((version_file, '.'))

# Optional certifi bundle
try:
    import certifi
    datas.append((certifi.where(), 'certifi'))
except ImportError:
    pass

icon_path = os.path.join(ROOT_DIR, 'public', 'favicon.ico')
icon_file = icon_path if os.path.exists(icon_path) else None

a = Analysis(
    [os.path.join(ROOT_DIR, 'run_tray.py')],
    pathex=[ROOT_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'torch', 'notebook'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AIPromptStudio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # No black console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='AIPromptStudio',
)
