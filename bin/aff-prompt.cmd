@echo off
setlocal
for %%I in ("%~dp0..") do set "ROOT_DIR=%%~fI"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

if exist "%ROOT_DIR%\.venv\Scripts\python.exe" (
    set "PY_CMD=%ROOT_DIR%\.venv\Scripts\python.exe"
) else if exist "%ROOT_DIR%\venv\Scripts\python.exe" (
    set "PY_CMD=%ROOT_DIR%\venv\Scripts\python.exe"
) else if exist "%ROOT_DIR%\_internal\python.exe" (
    set "PY_CMD=%ROOT_DIR%\_internal\python.exe"
) else (
    set "PY_CMD=python"
)

"%PY_CMD%" "%ROOT_DIR%\cli.py" %*
set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%
