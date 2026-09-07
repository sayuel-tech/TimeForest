@echo off
setlocal
chcp 65001 >nul
title Time Forest - Director Studio
cd /d "%~dp0.."
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0director_service.ps1" -Action Menu
if errorlevel 1 pause
endlocal
