@echo off
cd /d "%~dp0"
backend\.venv\Scripts\python.exe tools\start_wifi.py
pause
