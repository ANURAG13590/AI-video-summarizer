@echo off
title AI Video Summarizer - 24/7 Auto Start
cd /d "%~dp0"

echo ============================================================
echo   AI Video Summarizer - Starting...
echo   Website: https://anurag13590.github.io/AI-video-summarizer/
echo ============================================================
echo.
echo [Auto-updating website URL and keeping it alive 24/7]
echo [Keep this window OPEN while laptop is on]
echo [Minimize it - don't close it]
echo.

:RESTART
echo Starting AI Video Summarizer...
.\.venv\Scripts\python.exe auto_start_and_update.py
echo.
echo [Server stopped. Restarting in 10 seconds...]
timeout /t 10 /nobreak >nul
goto RESTART
