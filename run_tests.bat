@echo off
rem Runs all three test sets (dev, holdout, realistic). Takes about 6 minutes.
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
for %%S in (dev holdout realistic) do (
    echo.
    echo ===== %%S set =====
    venv\Scripts\python.exe evaluate.py %%S
)
echo.
echo Reports saved as eval_report_dev.md, eval_report_holdout.md and eval_report_realistic.md
pause
