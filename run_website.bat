@echo off
rem Starts the demo website (http://localhost:8000) and admin page (http://localhost:8000/admin).
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
venv\Scripts\python.exe server.py
pause
