@echo off
cd /d "%~dp0"
title AI Prompt Studio

echo ==================================================
echo         AI PROMPT STUDIO - LAUNCHER
echo ==================================================
echo.

set "PY_CMD="

if exist ".venv\Scripts\python.exe" (
    set "PY_CMD=.venv\Scripts\python.exe"
    goto RUN
)

if exist "venv\Scripts\python.exe" (
    set "PY_CMD=venv\Scripts\python.exe"
    goto RUN
)

where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "PY_CMD=python"
    goto RUN
)

where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "PY_CMD=py"
    goto RUN
)

echo [ERROR] Khong tim thay Python tren he thong!
echo Vui long cai dat Python (https://www.python.org/) va tich chon "Add Python to PATH".
echo.
pause
exit /b 1

:RUN
echo [*] Dang khoi chay voi: %PY_CMD%
echo.
%PY_CMD% run.py %*

if %ERRORLEVEL% neq 0 (
    echo.
    echo [!] Chuong trinh ket thuc voi ma loi: %ERRORLEVEL%
    pause
)
 