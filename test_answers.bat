@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
echo Asking the chatbot 8 test questions (takes about a minute)...
venv\Scripts\python.exe answer.py > answers_log.txt 2>&1
type answers_log.txt
echo.
pause
