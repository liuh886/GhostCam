@echo off
:: GhostCam One-Click Launcher
:: This batch file bypasses ExecutionPolicy and runs the smart PowerShell script.

SET DIR=%~dp0
cd /d "%DIR%"

powershell -NoProfile -ExecutionPolicy Bypass -File "GhostCam.ps1" start
pause
