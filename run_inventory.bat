@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%CD%\src"

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -m sdhq_toolkit inventory --packs "samples\packs" --extracted "samples\extracted" --output "reports" --skip-hash
) else (
    python -m sdhq_toolkit inventory --packs "samples\packs" --extracted "samples\extracted" --output "reports" --skip-hash
)

echo.
if errorlevel 1 (
    echo [ERRO] A pipeline terminou com erro.
) else (
    echo [OK] Relatorios gerados na pasta reports.
)
pause
