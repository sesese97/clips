@echo off
chcp 65001 >nul
cd /d "%~dp0"
title ClipSese - Motor local
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0local\start.ps1"
if errorlevel 1 (
  echo.
  echo Revisa el error de arriba. Si falta instalar algo, usa INSTALAR_LOCAL.bat.
)
pause
