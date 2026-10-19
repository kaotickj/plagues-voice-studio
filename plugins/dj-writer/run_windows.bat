@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
    py -3 goodneighbor_dj.py
) else (
    python goodneighbor_dj.py
)
if errorlevel 1 (
    echo.
    echo Startup failed. Install requirements with your selected Python first:
    echo python -m pip install -r requirements.txt
    pause
)
