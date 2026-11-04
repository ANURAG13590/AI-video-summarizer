@echo off
cd /d "%~dp0"
set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"

echo ========================================================
echo Starting AI Video Summarizer + Cloudflare Public Tunnel
echo ========================================================
echo.

REM Start FastAPI server in a background window
start "AI Video Summarizer Server" "%PYTHON_EXE%" -m uvicorn app:app --host 127.0.0.1 --port 8000

REM Wait 3 seconds for server to initialize
timeout /t 3 /nobreak >nul

echo Server started at http://127.0.0.1:8000
echo.
echo Launching Cloudflare public tunnel...
echo (Your public link ending in .trycloudflare.com will be printed below)
echo Keep this window open to keep your public link active.
echo ========================================================
echo.
cloudflared.exe tunnel --url http://127.0.0.1:8000
pause
