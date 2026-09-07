@echo off
rem ============================================================
rem  H3 Video Chain UI - Setup (run ONCE on a fresh machine)
rem  Creates a Python virtual environment (.venv) and installs
rem  dependencies. Then double-click start.bat to run the app.
rem  Requires Python 3.10+.
rem ============================================================
cd /d "%~dp0"

echo H3 Video Chain UI - Setup
echo.

rem ---- locate a Python 3.10+ on PATH ----
set "PY="
where py >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if not defined PY (
  where python >nul 2>nul
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  echo [ERROR] Python 3.10+ was not found on PATH.
  echo.
  echo Install Python from https://www.python.org/downloads/
  echo and during install check "Add python.exe to PATH".
  echo Then run this setup again.
  pause
  exit /b 1
)

rem ---- check Python version (need 3.10+ for the application) ----
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python 3.10+ is required, but this Python is older.
  echo Install a recent Python from https://www.python.org/downloads/
  pause
  exit /b 1
)

echo Using: %PY%
echo Creating virtual environment (.venv) ...
%PY% -m venv .venv
if errorlevel 1 (
  echo [ERROR] Failed to create the virtual environment.
  pause
  exit /b 1
)

set "PIP=.venv\Scripts\python.exe -m pip"

echo Installing dependencies...
rem Upgrade pip (best effort, ignore errors)
%PIP% install --upgrade pip --index-url https://pypi.org/simple >nul 2>nul

rem Try several package indexes until one works:
rem   1. the index configured in pip config (default behavior)
rem   2. Tsinghua mirror   (China)
rem   3. Aliyun mirror     (China)
rem   4. official PyPI
%PIP% install -r requirements.txt
if errorlevel 1 %PIP% install -r requirements.txt --index-url https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 %PIP% install -r requirements.txt --index-url https://mirrors.aliyun.com/pypi/simple/
if errorlevel 1 %PIP% install -r requirements.txt --index-url https://pypi.org/simple
if errorlevel 1 (
  echo.
  echo [ERROR] Could not install dependencies from any mirror.
  echo Check your network, or set a working mirror with:
  echo   .venv\Scripts\python.exe -m pip config set global.index-url https://pypi.org/simple
  pause
  exit /b 1
)

echo.
echo ============================================================
echo  Setup complete.
echo  Now double-click start.bat to run the app.
echo ============================================================
pause
