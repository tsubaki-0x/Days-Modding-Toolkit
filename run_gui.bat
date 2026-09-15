@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%CD%\src"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -m sdhq_toolkit.gui
) else (
    python -m sdhq_toolkit.gui
)
if errorlevel 1 pause
