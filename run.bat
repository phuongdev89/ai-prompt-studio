@echo off
cd /d "%~dp0"

if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" run_tray.py
    exit /b 0
)

if exist "venv\Scripts\pythonw.exe" (
    start "" "venv\Scripts\pythonw.exe" run_tray.py
    exit /b 0
)

where.exe pythonw >nul 2>&1
if %ERRORLEVEL% equ 0 (
    start "" pythonw run_tray.py
    exit /b 0
)

start "" python run_tray.py
exit /b 0
