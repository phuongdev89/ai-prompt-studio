; ========================================================
;   AI PROMPT STUDIO - NSIS FULL INSTALLER
; ========================================================
; Cài đặt vào $LOCALAPPDATA\Programs\AI Prompt Studio
; Không cần quyền Administrator
; Tự động bỏ qua prompts.db khi cài đè (bảo vệ dữ liệu người dùng)
; ========================================================

!include "MUI2.nsh"
!include "FileFunc.nsh"

; --- Đọc phiên bản từ file .version ---
!define /file APP_VERSION "..\..version"

; --- Thông tin ứng dụng ---
!define APP_NAME "AI Prompt Studio"
!define APP_EXE "AIPromptStudio.exe"
!define APP_PUBLISHER "PhuongDev"
!define APP_URL "https://github.com/YOUR_USER/ai_prompts_database"
!define INSTALL_DIR "$LOCALAPPDATA\Programs\AI Prompt Studio"

Name "${APP_NAME} v${APP_VERSION}"
OutFile "..\dist\AI_Prompt_Studio_Setup_v${APP_VERSION}.exe"
InstallDir "${INSTALL_DIR}"
InstallDirRegKey HKCU "Software\${APP_NAME}" "InstallDir"
RequestExecutionLevel user

; --- Giao diện Modern UI ---
!define MUI_ICON "..\assets\icon.ico"
!define MUI_UNICON "..\assets\icon.ico"
!define MUI_ABORTWARNING

; --- Pages ---
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "Khởi chạy ${APP_NAME}"
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

; ========================================================
;   SECTION: Cài đặt chính
; ========================================================
Section "Install" SecMain
    SetOutPath "$INSTDIR"

    ; --- Đóng ứng dụng nếu đang chạy ---
    nsExec::ExecToLog 'taskkill /F /IM ${APP_EXE}'

    ; --- Cài toàn bộ file ứng dụng (trừ prompts.db) ---
    File "..\dist\AIPromptStudio\${APP_EXE}"
    File /r /x "prompts.db" "..\dist\AIPromptStudio\_internal\*.*"

    ; --- Tạo thư mục data nếu chưa có ---
    CreateDirectory "$INSTDIR\data"
    CreateDirectory "$INSTDIR\data\images"

    ; --- Sao chép file .version ---
    File "..\.version"

    ; --- Tạo file .env từ .env.example nếu chưa tồn tại ---
    IfFileExists "$INSTDIR\.env" +2 0
        CopyFiles /SILENT "$INSTDIR\_internal\.env.example" "$INSTDIR\.env"

    ; --- Ghi Registry ---
    WriteRegStr HKCU "Software\${APP_NAME}" "InstallDir" "$INSTDIR"
    WriteRegStr HKCU "Software\${APP_NAME}" "Version" "${APP_VERSION}"

    ; --- Tạo Uninstaller ---
    WriteUninstaller "$INSTDIR\Uninstall.exe"

    ; --- Đăng ký Add/Remove Programs ---
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "DisplayName" "${APP_NAME}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "UninstallString" '"$INSTDIR\Uninstall.exe"'
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "InstallLocation" "$INSTDIR"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "Publisher" "${APP_PUBLISHER}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "DisplayVersion" "${APP_VERSION}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "URLInfoAbout" "${APP_URL}"
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "NoModify" 1
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "NoRepair" 1

    ; --- Tính dung lượng ---
    ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
    IntFmt $0 "0x%08X" $0
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "EstimatedSize" $0

    ; --- Shortcut Desktop ---
    CreateShortCut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"

    ; --- Shortcut Start Menu ---
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortCut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
    CreateShortCut "$SMPROGRAMS\${APP_NAME}\Gỡ cài đặt.lnk" "$INSTDIR\Uninstall.exe"
SectionEnd

; ========================================================
;   SECTION: Gỡ cài đặt
; ========================================================
Section "Uninstall"
    ; --- Đóng ứng dụng ---
    nsExec::ExecToLog 'taskkill /F /IM ${APP_EXE}'

    ; --- Xóa file & thư mục (giữ lại data/ nếu người dùng muốn) ---
    Delete "$INSTDIR\${APP_EXE}"
    Delete "$INSTDIR\.version"
    Delete "$INSTDIR\.env"
    Delete "$INSTDIR\Uninstall.exe"
    RMDir /r "$INSTDIR\_internal"

    ; --- Hỏi người dùng có muốn xóa dữ liệu không ---
    MessageBox MB_YESNO|MB_ICONQUESTION \
        "Bạn có muốn xóa toàn bộ dữ liệu (prompts.db, ảnh mẫu)?$\n$\nChọn 'No' để giữ lại dữ liệu cũ." \
        IDYES removeData IDNO keepData

    removeData:
        RMDir /r "$INSTDIR\data"
        Goto cleanupDone

    keepData:
        ; Giữ nguyên thư mục data/

    cleanupDone:
    RMDir "$INSTDIR"

    ; --- Xóa Shortcuts ---
    Delete "$DESKTOP\${APP_NAME}.lnk"
    RMDir /r "$SMPROGRAMS\${APP_NAME}"

    ; --- Xóa Registry ---
    DeleteRegKey HKCU "Software\${APP_NAME}"
    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
SectionEnd
