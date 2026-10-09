@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
echo Running the dev evaluation...
venv\Scripts\python.exe evaluate.py dev > eval_log_dev.txt 2>&1
type eval_log_dev.txt
pause
