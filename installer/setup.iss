; ========================================================
;   AI PROMPT STUDIO - FULL INSTALLER (Inno Setup)
; ========================================================

#define MyAppName "AI Prompt Studio"
#define MyAppPublisher "PhuongDev"
#define MyAppURL "https://github.com/phuongdev89/ai-prompt-studio"
#define MyAppExeName "AIPromptStudio.exe"

#ifndef MyAppVersion
  #if FileExists(AddBackslash(SourcePath) + "..\.version")
    #define FileHandle FileOpen(AddBackslash(SourcePath) + "..\.version")
    #define MyAppVersion Trim(FileRead(FileHandle))
    #expr FileClose(FileHandle)
  #else
    #define MyAppVersion "1.0.0"
  #endif
#endif

[Setup]
AppId={{5C1D8249-FE78-4392-80D7-F514E94848A1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Install to Local AppData (No Admin rights required)
DefaultDirName={localappdata}\Programs\AI Prompt Studio
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
PrivilegesRequired=lowest

OutputDir=..\dist
OutputBaseFilename=AI_Prompt_Studio_Setup_v{#MyAppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\AIPromptStudio\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\AIPromptStudio\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\.version"; DestDir: "{app}"; Flags: ignoreversion

; Create empty data dirs if not exist
Source: "..\.version"; DestDir: "{app}\data"; Flags: uninsneveruninstall; Permissions: users-modify
Source: "..\.version"; DestDir: "{app}\data\images"; Flags: uninsneveruninstall; Permissions: users-modify

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[InstallDelete]
; Clean up old internal dir before installing new one
Type: filesandordirs; Name: "{app}\_internal"

[UninstallDelete]
Type: files; Name: "{app}\.version"
Type: files; Name: "{app}\{#MyAppExeName}"
Type: filesandordirs; Name: "{app}\_internal"
; Ask to delete data folder in Code section

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if DirExists(ExpandConstant('{app}\data')) then
    begin
      if MsgBox('Bạn có muốn xóa toàn bộ dữ liệu (cấu hình, DB, ảnh mẫu)?'#13#10#13#10'Chọn "No" để giữ lại dữ liệu cũ.', mbConfirmation, MB_YESNO) = idYes then
      begin
        DelTree(ExpandConstant('{app}\data'), True, True, True);
        DelTree(ExpandConstant('{app}'), True, True, True);
      end;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssInstall then
  begin
    Exec('taskkill.exe', '/F /IM AIPromptStudio.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;
