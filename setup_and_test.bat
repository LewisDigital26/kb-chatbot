@echo off
cd /d "%~dp0"
echo === Setting up the Business Knowledge Chatbot ===
if not exist venv\Scripts\python.exe (
    echo Creating virtual environment...
    python -m venv venv
)
echo Installing packages (can take a minute)...
venv\Scripts\python.exe -m pip install -q -r requirements.txt > setup_log.txt 2>&1
echo.
echo === Building the knowledge base, then test searches ===
(
  venv\Scripts\python.exe ingest.py
  echo.
  venv\Scripts\python.exe search.py
) >> setup_log.txt 2>&1
type setup_log.txt
echo.
pause
