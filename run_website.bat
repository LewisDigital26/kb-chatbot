@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
echo Starting the demo website...
venv\Scripts\python.exe server.py
pause
