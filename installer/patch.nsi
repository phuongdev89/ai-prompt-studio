; ========================================================
;   AI PROMPT STUDIO - NSIS PATCH UPDATE (Lightweight)
; ========================================================
; Chỉ ghi đè code (app/), file exe, templates, static
; KHÔNG ghi đè prompts.db, .env, ảnh người dùng
; ========================================================

!include "MUI2.nsh"

; --- Đọc phiên bản ---
!define /file APP_VERSION "..\..version"

!define APP_NAME "AI Prompt Studio"
!define APP_EXE "AIPromptStudio.exe"
!define INSTALL_DIR "$LOCALAPPDATA\Programs\AI Prompt Studio"

Name "${APP_NAME} Patch v${APP_VERSION}"
OutFile "..\dist\AI_Prompt_Studio_Patch_v${APP_VERSION}.exe"
InstallDir "${INSTALL_DIR}"
InstallDirRegKey HKCU "Software\${APP_NAME}" "InstallDir"
RequestExecutionLevel user

!define MUI_ABORTWARNING

!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "Khởi chạy ${APP_NAME}"
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_LANGUAGE "English"

Section "Patch" SecPatch
    SetOutPath "$INSTDIR"

    ; Đóng ứng dụng nếu đang chạy
    nsExec::ExecToLog 'taskkill /F /IM ${APP_EXE}'

    ; Ghi đè file exe
    File "..\dist\AIPromptStudio\${APP_EXE}"

    ; Ghi đè _internal (code, templates, static) — trừ prompts.db
    SetOutPath "$INSTDIR\_internal"
    File /r /x "prompts.db" /x "*.db-wal" /x "*.db-shm" "..\dist\AIPromptStudio\_internal\app\*.*"

    ; Ghi đè .version
    SetOutPath "$INSTDIR"
    File "..\.version"

    ; Cập nhật version trong Registry
    WriteRegStr HKCU "Software\${APP_NAME}" "Version" "${APP_VERSION}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "DisplayVersion" "${APP_VERSION}"
SectionEnd
