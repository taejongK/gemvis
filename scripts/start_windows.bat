@echo off
chcp 65001 > nul
REM Gemvis start launcher for Windows
cd /d "%~dp0\.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_windows.ps1"
echo.
pause
