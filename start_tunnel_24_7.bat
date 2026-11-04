@echo off
title AI Video Summarizer - 24/7 Engine
cd /d "%~dp0"

echo ========================================================
echo        AI Video Summarizer - Background Runner
echo ========================================================
echo.

:: 1. Start Python server in background
echo Starting local AI engine on port 8000...
start "AI-Summarizer-Backend" /min cmd /c ".\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000"

:: Wait 3 seconds for server to initialize
timeout /t 3 /nobreak >nul

:: 2. Start Cloudflare Tunnel
echo Connecting to live internet tunnel...
echo.
echo Tunnel is now running! Keep this window open for 24/7 access.
echo (You can minimize this window).
echo.
echo Direct local URL: http://localhost:8000
echo.

cloudflared.exe tunnel --url http://127.0.0.1:8000
pause
