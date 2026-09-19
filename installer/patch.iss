; ========================================================
;   AI PROMPT STUDIO - PATCH UPDATE (Inno Setup)
; ========================================================
; Chỉ ghi đè code (_internal), exe
; Bỏ qua data/ (prompts.db, config.json)
; ========================================================

#define MyAppName "AI Prompt Studio"
#define MyAppPublisher "PhuongDev"
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
AppName={#MyAppName} (Patch Update)
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}

DefaultDirName={localappdata}\Programs\AI Prompt Studio
UsePreviousAppDir=yes
CreateUninstallRegKey=no
UpdateUninstallLogAppName=no
PrivilegesRequired=lowest

OutputDir=..\dist
OutputBaseFilename=AI_Prompt_Studio_Patch_v{#MyAppVersion}
SetupIconFile=..\assets\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

DisableProgramGroupPage=yes
DisableDirPage=auto

[Files]
Source: "..\dist\AIPromptStudio\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\AIPromptStudio\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\.version"; DestDir: "{app}"; Flags: ignoreversion

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Khởi chạy {#MyAppName} sau khi cập nhật"; Flags: nowait postinstall skipifsilent

[InstallDelete]
; Clean up old internal dir before installing new one
Type: filesandordirs; Name: "{app}\_internal"

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssInstall then
  begin
    Exec('taskkill.exe', '/F /IM AIPromptStudio.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;
