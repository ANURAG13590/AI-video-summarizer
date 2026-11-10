@echo off
title AI Video Summarizer - Independent Start
cd /d "%~dp0"
color 0A

echo.
echo  ============================================================
echo   AI Video Summarizer - Starting Independent Services
echo  ============================================================
echo.

REM Kill old processes
taskkill /F /IM cloudflared.exe >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING"') do taskkill /F /PID %%a >nul 2>&1
timeout /t 2 /nobreak >nul

REM Start uvicorn INDEPENDENTLY (new process group, hidden window)
echo [1/3] Starting AI server on port 8000...
start "AI-Server" /MIN cmd /c "cd /d "%~dp0" && .\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000 >> logs\uvicorn.log 2>&1"

REM Wait for server
timeout /t 4 /nobreak >nul

REM Start the Python URL-updater which starts cloudflared and updates Gist
echo [2/3] Starting Cloudflare tunnel and updating website URL...
start "AI-Updater" /MIN cmd /c "cd /d "%~dp0" && .\.venv\Scripts\python.exe tunnel_and_update.py >> logs\updater.log 2>&1"

echo [3/3] Done! Waiting for tunnel URL to be registered...
timeout /t 15 /nobreak >nul

echo.
echo  ============================================================
echo   WEBSITE IS NOW LIVE!
echo   Open: https://anurag13590.github.io/AI-video-summarizer/
echo.
echo   Both processes run INDEPENDENTLY.
echo   You can close Antigravity - website stays LIVE!
echo   Keep this window open OR close it - your choice.
echo  ============================================================
echo.
pause
