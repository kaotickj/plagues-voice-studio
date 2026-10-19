@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_windows.ps1"
if errorlevel 1 (pause & exit /b 1)
pause
