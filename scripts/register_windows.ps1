# ========================================================
#   AI PROMPT STUDIO - WINDOWS REGISTRATION SCRIPT
#   Tu dong dang ky 'bin' vao User PATH (Khong can Admin)
# ========================================================

[CmdletBinding()]
param(
    [string]$InstallDir = "",
    [switch]$CreateShortcuts = $true
)

$ErrorActionPreference = "Stop"

# Thiet lap UTF-8 output cho console
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Neu khong truyen InstallDir, tu dong nhan dien thu muc cai dat hoac repo goc
if ([string]::IsNullOrWhiteSpace($InstallDir)) {
    $InstallDir = (Resolve-Path (Join-Path $ScriptDir "..")).Path
} else {
    $InstallDir = (Resolve-Path $InstallDir).Path
}

$BinDir = (Join-Path $InstallDir "bin")
$IsInstalledApp = Test-Path (Join-Path $InstallDir "AIPromptStudio.exe")

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "   AI PROMPT STUDIO - DANG KY CONG CU WINDOWS" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "Thu muc cai dat: $InstallDir"
Write-Host "Thu muc bin    : $BinDir"
Write-Host "Moi truong     : $(if ($IsInstalledApp) { 'Bo cai dat (Packaged App)' } else { 'Ma nguon (Dev Repo)' })"

# 1. Kiem tra va tao thu muc bin neu chua co
if (-not (Test-Path $BinDir)) {
    New-Item -ItemType Directory -Path $BinDir -Force | Out-Null
}

# 2. Dang ky vao User PATH
$UserPath = [Environment]::GetEnvironmentVariable("Path", [EnvironmentVariableTarget]::User)
$PathEntries = ($UserPath -split ";") | Where-Object { $_ -ne "" }

if ($PathEntries -contains $BinDir) {
    Write-Host "[v] Duong dan 'bin' da co san trong User PATH." -ForegroundColor Yellow
} else {
    Write-Host "[*] Dang them '$BinDir' vao User PATH..." -ForegroundColor Green
    $NewUserPath = if ([string]::IsNullOrWhiteSpace($UserPath)) { $BinDir } else { "$UserPath;$BinDir" }
    [Environment]::SetEnvironmentVariable("Path", $NewUserPath, [EnvironmentVariableTarget]::User)

    # Cap nhat PATH cho phien lam viec PowerShell hien tai
    $env:Path = "$env:Path;$BinDir"
    Write-Host "[v] Da them thanh cong vao User PATH." -ForegroundColor Green
}

# 3. Tao Shortcut Desktop va Start Menu (tuy chon)
if ($CreateShortcuts) {
    try {
        $WshShell = New-Object -ComObject WScript.Shell
        $TargetExecutable = if ($IsInstalledApp) { Join-Path $InstallDir "AIPromptStudio.exe" } else { Join-Path $InstallDir "run.bat" }
        $IconFile = Join-Path $InstallDir "public\favicon.ico"

        # Shortcut Desktop cho Web UI
        $DesktopPath = [Environment]::GetFolderPath("Desktop")
        $ShortcutPath = Join-Path $DesktopPath "AI Prompt Studio.lnk"
        $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
        $Shortcut.TargetPath = $TargetExecutable
        $Shortcut.WorkingDirectory = $InstallDir
        $Shortcut.Description = "AI Prompt Studio - Web & Prompt Manager"
        if (Test-Path $IconFile) {
            $Shortcut.IconLocation = "$IconFile, 0"
        }
        $Shortcut.Save()
        Write-Host "[v] Da tao Shortcut Desktop: AI Prompt Studio.lnk" -ForegroundColor Green

        # Shortcut Start Menu
        $StartMenuPath = [Environment]::GetFolderPath("Programs")
        $SmShortcutPath = Join-Path $StartMenuPath "AI Prompt Studio.lnk"
        $SmShortcut = $WshShell.CreateShortcut($SmShortcutPath)
        $SmShortcut.TargetPath = $TargetExecutable
        $SmShortcut.WorkingDirectory = $InstallDir
        $SmShortcut.Description = "AI Prompt Studio"
        if (Test-Path $IconFile) {
            $SmShortcut.IconLocation = "$IconFile, 0"
        }
        $SmShortcut.Save()
        Write-Host "[v] Da tao Shortcut Start Menu: AI Prompt Studio.lnk" -ForegroundColor Green
    } catch {
        Write-Host "[!] Khong the tao Shortcut: $_" -ForegroundColor Yellow
    }
}

Write-Host "--------------------------------------------------" -ForegroundColor Cyan
Write-Host "HOAN TAT DANG KY THANH CONG!" -ForegroundColor Green
Write-Host "Ban co the mo Terminal moi va su dung lenh toan he thong:" -ForegroundColor White
Write-Host "  aff-prompt --help" -ForegroundColor Yellow
Write-Host "  aff-prompt list --limit 10" -ForegroundColor Yellow
Write-Host "  aff-prompt stats --json" -ForegroundColor Yellow
Write-Host "  aff-prompt serve" -ForegroundColor Yellow
Write-Host "==================================================" -ForegroundColor Cyan
