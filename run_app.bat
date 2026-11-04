@echo off
title AI Video Summarizer
echo Starting AI Video Summarizer on your laptop...
start "" "http://localhost:8000"
.\.venv\Scripts\python.exe -m uvicorn app:app --host 0.0.0.0 --port 8000
pause
