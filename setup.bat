@echo off
rem One-time setup: creates the virtual environment, installs packages and builds the knowledge base.
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
if not exist .env (
    echo No .env file yet. Copy .env.example to .env and add your keys first.
    pause
    exit /b
)
if not exist venv\Scripts\python.exe python -m venv venv
echo Installing packages...
venv\Scripts\python.exe -m pip install -q -r requirements.txt
venv\Scripts\python.exe ingest.py
echo.
echo Setup complete. Double-click run_website.bat to start the chatbot.
pause
