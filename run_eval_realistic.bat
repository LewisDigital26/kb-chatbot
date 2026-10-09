@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
echo Running the realistic evaluation...
venv\Scripts\python.exe evaluate.py realistic > eval_log_realistic.txt 2>&1
type eval_log_realistic.txt
pause
