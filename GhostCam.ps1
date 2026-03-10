# GhostCam Management Script for Windows
# Usage: .\GhostCam.ps1 [start|stop|install-driver|setup]

param (
    [Parameter(Mandatory=$false, Position=0)]
    [ValidateSet("start", "stop", "setup", "install-driver")]
    [string]$Action = "start",

    [string]$InputDevice = "video=Integrated Camera",
    [int]$Width = 1280,
    [int]$Height = 720,
    [string]$BackgroundMode = "image",
    [string]$BackgroundColor = "#222222",
    [int]$BlurStrength = 21,
    [string]$BackgroundImage = ""
)

$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$VenvPath = Join-Path $PSScriptRoot ".venv"
$PythonExe = Join-Path $VenvPath "Scripts\python.exe"

if (-not $BackgroundImage) {
    $BackgroundImage = Join-Path $PSScriptRoot "tests\test_background.webp"
}

function Show-Banner {
    Write-Host "👻 GhostCam (Headless-VCam) Control" -ForegroundColor Cyan
    Write-Host "------------------------------------"
}

function Setup-Environment {
    Write-Host "[*] Setting up Python Virtual Environment..." -ForegroundColor Yellow
    if (-not (Test-Path $VenvPath)) {
        python -m venv .venv
    }

    Write-Host "[*] Installing dependencies..." -ForegroundColor Yellow
    & $PythonExe -m pip install --upgrade pip
    & $PythonExe -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
    Write-Host "[+] Environment ready." -ForegroundColor Green
}

function Install-Driver {
    Write-Host "[*] Installing UnityCapture Driver..." -ForegroundColor Yellow
    $DriverPath = Join-Path $PSScriptRoot "drivers\UnityCapture\Install\Install.bat"
    if (Test-Path $DriverPath) {
        Start-Process "cmd.exe" -ArgumentList "/c `"$DriverPath`"" -Verb RunAs -Wait
        Write-Host "[+] Driver installation triggered (Check the pop-up window)." -ForegroundColor Green
    } else {
        Write-Host "[!] Driver path not found: $DriverPath" -ForegroundColor Red
    }
}

function Start-GhostCam {
    if (-not (Test-Path $PythonExe)) {
        Setup-Environment
    }

    $ArgsList = @(
        (Join-Path $PSScriptRoot "src\ghostcam\main.py"),
        "--input", $InputDevice,
        "--width", $Width,
        "--height", $Height,
        "--background-mode", $BackgroundMode,
        "--background-color", $BackgroundColor,
        "--blur-strength", $BlurStrength
    )

    if ($BackgroundImage -and (Test-Path $BackgroundImage)) {
        $ArgsList += "--background-image"
        $ArgsList += $BackgroundImage
    }

    Write-Host "[>] Starting GhostCam Service..." -ForegroundColor Green
    Write-Host "[i] Device: $InputDevice"
    Write-Host "[i] Resolution: ${Width}x${Height}"
    Write-Host "[i] Background Mode: $BackgroundMode"
    Write-Host "------------------------------------"
    Write-Host "Press Ctrl+C to stop the service."

    & $PythonExe @ArgsList
}

function Stop-GhostCam {
    Write-Host "[*] Stopping GhostCam service and restoring the default camera..." -ForegroundColor Yellow

    if (Get-Command pm2 -ErrorAction SilentlyContinue) {
        pm2 stop ghostcam | Out-Null
        pm2 delete ghostcam | Out-Null
    }

    Get-Process ghostcam -ErrorAction SilentlyContinue | Stop-Process -Force

    Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*ghostcam*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

    Get-Process WindowsCamera, ApplicationFrameHost -ErrorAction SilentlyContinue | Stop-Process -Force

    Write-Host "[+] GhostCam stopped. Camera apps can now reacquire Integrated Camera." -ForegroundColor Green
}

# Main Execution
Show-Banner

switch ($Action) {
    "setup" { Setup-Environment }
    "install-driver" { Install-Driver }
    "start" { Start-GhostCam }
    "stop" { Stop-GhostCam }
}
