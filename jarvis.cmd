@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo JARVIS virtual environment not found.
    echo Create it with: py -3.12 -m venv .venv
    echo Then install dependencies with: .venv\Scripts\python.exe -m pip install -r requirements.txt
    exit /b 1
)

".venv\Scripts\python.exe" -m main %*
exit /b %errorlevel%