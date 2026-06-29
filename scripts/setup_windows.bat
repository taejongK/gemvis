@echo off
chcp 65001 > nul
REM Gemvis setup launcher for Windows
cd /d "%~dp0\.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_windows.ps1"
echo.
pause
