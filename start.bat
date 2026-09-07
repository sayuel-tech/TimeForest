@echo off
rem ============================================================
rem  H3 Video Chain UI - Start (Windows)
rem  Double-click to start. Close this window to stop.
rem  If .venv is missing, run setup.bat first.
rem ============================================================
cd /d "%~dp0"

rem ---- pick the Python to use ----
set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY if exist "..\..\comf\ComfyUI_windows_portable\python_embeded\python.exe" set "PY=..\..\comf\ComfyUI_windows_portable\python_embeded\python.exe"
if not defined PY (
  where python >nul 2>nul
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  echo [ERROR] Python 3.10+ not found.
  echo Install Python from https://www.python.org/downloads/
  echo then run setup.bat, then start.bat.
  pause
  exit /b 1
)

echo.
echo   H3 Video Chain UI   http://127.0.0.1:5093
echo   Close this window to stop the server.
echo.

rem ---- if port 5093 is already in use, just open the browser ----
netstat -ano | findstr ":5093" | findstr "LISTENING" >nul
if not errorlevel 1 (
  echo   Server already running. Opening browser...
  start "" "http://127.0.0.1:5093"
  echo.
  pause
  exit /b 0
)

echo   Starting... the browser will open automatically.
"%PY%" run.py
echo.
echo   Server stopped.
pause
