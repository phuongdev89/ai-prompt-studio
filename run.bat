@echo off
cd /d "%~dp0"
title AI Prompt Studio

echo ==================================================
echo         AI PROMPT STUDIO - DESKTOP
echo ==================================================
echo.

set "PY_CMD="

if exist ".venv\Scripts\python.exe" (
    set "PY_CMD=.venv\Scripts\python.exe"
) else if exist "venv\Scripts\python.exe" (
    set "PY_CMD=venv\Scripts\python.exe"
) else (
    set "PY_CMD=python"
)

echo [*] Khoi chay bang: %PY_CMD%
echo [*] Vui long doi ung dung khoi dong...
echo.

"%PY_CMD%" run.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [!] Chuong trinh ket thuc voi ma loi: %ERRORLEVEL%
    pause
)
