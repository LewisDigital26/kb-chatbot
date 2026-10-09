@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
echo Running the holdout evaluation...
venv\Scripts\python.exe evaluate.py holdout > eval_log_holdout.txt 2>&1
type eval_log_holdout.txt
pause
