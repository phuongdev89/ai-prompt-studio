@echo off
REM ========================================================
REM   BUILD PATCH UPDATE - AI PROMPT STUDIO (Inno Setup)
REM ========================================================
cd /d "%~dp0\.."
title AI Prompt Studio - Build Patch

set "APP_VERSION=1.0.0"
if exist ".version" (
    set /p APP_VERSION=<.version
)

echo ==================================================
echo   BUILD PATCH - AI PROMPT STUDIO v%APP_VERSION%
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
echo [1/2] Dong goi phien ban moi voi PyInstaller...
%PY_CMD% -m PyInstaller --noconfirm installer\build.spec
if %ERRORLEVEL% neq 0 (
    echo [ERROR] PyInstaller that bai!
    pause
    exit /b 1
)

echo.
echo [2/2] Tao bo cai Patch voi Inno Setup...
set "ISCC_PATH="
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not defined ISCC_PATH (
    if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set "ISCC_PATH=C:\Program Files\Inno Setup 6\ISCC.exe"
)
if not defined ISCC_PATH (
    if exist "C:\Program Files (x86)\Inno Setup 5\ISCC.exe" set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 5\ISCC.exe"
)

if defined ISCC_PATH (
    "%ISCC_PATH%" installer\patch.iss
    if %ERRORLEVEL% equ 0 (
        echo [OK] Da tao file Patch EXE thanh cong!
    ) else (
        echo [ERROR] Inno Setup bien dich that bai!
        pause
        exit /b 1
    )
) else (
    echo [ERROR] Khong tim thay Inno Setup!
    pause
    exit /b 1
)

echo.
echo ==================================================
echo   BUILD PATCH HOAN TAT!
echo   File: dist\AI_Prompt_Studio_Patch_v%APP_VERSION%.exe
echo ==================================================
echo.
pause
