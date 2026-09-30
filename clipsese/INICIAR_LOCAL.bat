@echo off
chcp 65001 >nul
cd /d "%~dp0"
title ClipSese - Motor local
echo Buscando correcciones del motor local...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -UseBasicParsing -Uri 'https://raw.githubusercontent.com/sesese97/clips/clipsese-local-windows/clipsese/local/start.ps1' -OutFile '%~dp0local\start.ps1'; Invoke-WebRequest -UseBasicParsing -Uri 'https://raw.githubusercontent.com/sesese97/clips/clipsese-local-windows/clipsese/backend/app/video.py' -OutFile '%~dp0backend\app\video.py' } catch { Write-Host 'No se pudo buscar la ultima correccion; usare la copia local.' -ForegroundColor Yellow }"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0local\start.ps1"
if errorlevel 1 (
  echo.
  echo Revisa el error de arriba. Si falta instalar algo, usa INSTALAR_LOCAL.bat.
)
pause
