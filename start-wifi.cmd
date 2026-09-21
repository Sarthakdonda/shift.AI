@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\ensure_wifi_firewall.ps1"
if errorlevel 1 (
  echo.
  echo Shift AI Wi-Fi setup did not complete. No servers were started.
  pause
  exit /b 1
)
backend\.venv\Scripts\python.exe tools\start_wifi.py
pause
