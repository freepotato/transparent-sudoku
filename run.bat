@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo [setup] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [error] python not found. Install Python 3.10+ first.
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [error] Failed to install dependencies.
        pause
        exit /b 1
    )
)

start "" ".venv\Scripts\pythonw.exe" main.py
