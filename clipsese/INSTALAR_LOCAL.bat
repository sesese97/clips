@echo off
chcp 65001 >nul
cd /d "%~dp0"
title ClipSese - Instalacion local
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0local\install.ps1"
if errorlevel 1 (
  echo.
  echo Algo fallo. Lee el mensaje de arriba y vuelve a intentarlo.
  pause
  exit /b 1
)
echo.
echo Instalacion terminada. Ya puedes abrir INICIAR_LOCAL.bat.
pause
