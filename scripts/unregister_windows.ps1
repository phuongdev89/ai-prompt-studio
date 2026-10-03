# ========================================================
#   AI PROMPT STUDIO - WINDOWS UNREGISTRATION SCRIPT
#   Go bo 'bin' khoi User PATH va xoa Shortcut
# ========================================================

[CmdletBinding()]
param(
    [string]$InstallDir = ""
)

$ErrorActionPreference = "Stop"

# Thiet lap UTF-8 output cho console
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if ([string]::IsNullOrWhiteSpace($InstallDir)) {
    $InstallDir = (Resolve-Path (Join-Path $ScriptDir "..")).Path
} else {
    $InstallDir = (Resolve-Path $InstallDir).Path
}

$BinDir = (Join-Path $InstallDir "bin")

Write-Host "==================================================" -ForegroundColor Yellow
Write-Host "   AI PROMPT STUDIO - GO CAI DAT KHOI WINDOWS" -ForegroundColor Yellow
Write-Host "==================================================" -ForegroundColor Yellow
Write-Host "Thu muc cai dat: $InstallDir"
Write-Host "Thu muc bin    : $BinDir"

# 1. Go khoi User PATH
$UserPath = [Environment]::GetEnvironmentVariable("Path", [EnvironmentVariableTarget]::User)
if ($UserPath) {
    $PathEntries = ($UserPath -split ";") | Where-Object { $_ -ne "" }
    $NewEntries = $PathEntries | Where-Object { $_ -ne $BinDir -and $_ -ne "$BinDir\" }

    if ($NewEntries.Count -lt $PathEntries.Count) {
        $NewUserPath = ($NewEntries -join ";")
        [Environment]::SetEnvironmentVariable("Path", $NewUserPath, [EnvironmentVariableTarget]::User)
        Write-Host "[v] Da xoa '$BinDir' khoi User PATH thanh cong." -ForegroundColor Green
    } else {
        Write-Host "[i] Duong dan '$BinDir' khong co trong User PATH." -ForegroundColor Gray
    }
}

# 2. Xoa Shortcuts neu ton tai
$DesktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "AI Prompt Studio.lnk"
if (Test-Path $DesktopShortcut) {
    Remove-Item -Path $DesktopShortcut -Force
    Write-Host "[v] Da xoa Shortcut Desktop." -ForegroundColor Green
}

$StartMenuShortcut = Join-Path ([Environment]::GetFolderPath("Programs")) "AI Prompt Studio.lnk"
if (Test-Path $StartMenuShortcut) {
    Remove-Item -Path $StartMenuShortcut -Force
    Write-Host "[v] Da xoa Shortcut Start Menu." -ForegroundColor Green
}

Write-Host "--------------------------------------------------" -ForegroundColor Yellow
Write-Host "HOAN TAT GO CAI DAT SHIM VA SHORTCUTS." -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Yellow
