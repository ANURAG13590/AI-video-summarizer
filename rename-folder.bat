@echo off
set "OLD=%~dp0"
set "NEW=%~dp0..\AI video Summarizer"
if exist "%NEW%" (
  echo Folder already renamed: %NEW%
  pause
  exit /b 0
)
echo Close Cursor first, then press any key to rename this folder...
pause >nul
move "%OLD:~0,-1%" "%NEW%"
if errorlevel 1 (
  echo Rename failed. Close Cursor and any running server, then try again.
) else (
  echo Done. Reopen the project from: %NEW%
)
pause
