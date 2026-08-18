@echo off
cd /d "%~dp0"

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
set "APP_URL=http://127.0.0.1:8000"

if not exist "%PYTHON_EXE%" (
    echo ERROR: Virtual environment not found.
    echo Run this once first: python -m venv .venv
    echo Then install dependencies: .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

echo Starting AI Video Summarizer...

powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%PYTHON_EXE%' -ArgumentList '-m','uvicorn','app:app','--host','127.0.0.1','--port','8000','--reload' -WorkingDirectory '%~dp0' -WindowStyle Normal"

for /L %%I in (1,1,6) do (
    ping 127.0.0.1 -n 2 >nul
)

start "" "%APP_URL%"
echo Application started at %APP_URL%
echo Keep the server window open while using the app.
exit /b 0
