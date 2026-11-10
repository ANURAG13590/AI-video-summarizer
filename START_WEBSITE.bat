@echo off
title AI Video Summarizer - 24/7
cd /d "%~dp0"
color 0A

echo.
echo ================================================================
echo   AI Video Summarizer - 24/7 Background Launcher
echo ================================================================
echo.

REM Kill old instances
taskkill /F /IM cloudflared.exe >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000.*LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul

REM Create logs folder
if not exist logs mkdir logs

REM === Start uvicorn in its own minimized window ===
echo [1/2] Starting AI server...
start "AI-Server-8000" /MIN cmd /c ".\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000"
timeout /t 5 /nobreak >nul

REM === Start cloudflared + auto URL updater ===
echo [2/2] Starting Cloudflare tunnel (auto-updates website URL)...
start "AI-Tunnel" /MIN cmd /c ".\.venv\Scripts\python.exe tunnel_and_update.py"

echo.
echo ================================================================
echo   BOTH SERVICES STARTED!
echo.
echo   Website: https://anurag13590.github.io/AI-video-summarizer/
echo.
echo   * Close Antigravity = website stays LIVE
echo   * Close this window = website stays LIVE  
echo   * Keep laptop ON    = website works 24/7
echo.
echo   To stop: Run this file again (it kills old + starts fresh)
echo ================================================================
echo.
timeout /t 10 /nobreak >nul
