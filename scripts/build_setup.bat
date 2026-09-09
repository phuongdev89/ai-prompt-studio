@echo off
REM ========================================================
REM   BUILD FULL INSTALLER - AI PROMPT STUDIO
REM ========================================================
cd /d "%~dp0\.."
title AI Prompt Studio - Build Installer

set "APP_VERSION=1.0.0"
if exist ".version" (
    set /p APP_VERSION=<.version
)

echo ==================================================
echo   BUILD INSTALLER - AI PROMPT STUDIO v%APP_VERSION%
echo ==================================================
echo.

REM --- Tim Python ---
set "PY_CMD="
if exist ".venv\Scripts\python.exe" (
    set "PY_CMD=.venv\Scripts\python.exe"
    goto FOUND_PY
)
if exist "venv\Scripts\python.exe" (
    set "PY_CMD=venv\Scripts\python.exe"
    goto FOUND_PY
)
where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "PY_CMD=python"
    goto FOUND_PY
)
echo [ERROR] Khong tim thay Python!
pause
exit /b 1

:FOUND_PY
echo [1/2] Dong goi ung dung voi PyInstaller...
%PY_CMD% -m PyInstaller --noconfirm installer\build.spec
if %ERRORLEVEL% neq 0 (
    echo [ERROR] PyInstaller that bai!
    pause
    exit /b 1
)

echo.
echo [2/2] Tao bo cai dat voi NSIS...
set "NSIS_PATH="
if exist "C:\Program Files (x86)\NSIS\makensis.exe" (
    set "NSIS_PATH=C:\Program Files (x86)\NSIS\makensis.exe"
) else if exist "C:\Program Files\NSIS\makensis.exe" (
    set "NSIS_PATH=C:\Program Files\NSIS\makensis.exe"
)

if defined NSIS_PATH (
    "%NSIS_PATH%" installer\setup.nsi
    echo [OK] Da tao file Installer EXE thanh cong!
) else (
    echo [SKIP] Khong tim thay NSIS. Cai dat tai https://nsis.sourceforge.io/
)

echo.
echo ==================================================
echo   BUILD HOAN TAT!
echo   File: dist\AI_Prompt_Studio_Setup_v%APP_VERSION%.exe
echo ==================================================
echo.
pause
