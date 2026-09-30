@echo off
chcp 65001 >nul
cd /d "%~dp0"
title ClipSese - iPad seguro
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0local\ipad.ps1"
if errorlevel 1 (
  echo.
  echo Revisa las instrucciones de arriba.
)
pause
