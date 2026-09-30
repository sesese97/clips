@echo off
chcp 65001 >nul
cd /d "%~dp0"
title ClipSese - Instalacion local
echo Buscando correcciones del instalador...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -UseBasicParsing -Uri 'https://raw.githubusercontent.com/sesese97/clips/clipsese-local-windows/clipsese/local/install.ps1' -OutFile '%~dp0local\install.ps1' } catch { Write-Host 'No se pudo actualizar el instalador; usare la copia local.' -ForegroundColor Yellow }"
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
