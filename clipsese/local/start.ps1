# Native Windows launcher. Double-click INICIAR_LOCAL.bat.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backend = Join-Path $root 'backend'
$frontendDist = Join-Path $root 'frontend\dist'
$python = Join-Path $backend '.venv\Scripts\python.exe'
$work = Join-Path $root 'local\work'
$logs = Join-Path $root 'local\logs'
$runtimeTemp = Join-Path $root 'local\temp\runtime'
$localFfmpegBin = Join-Path $root 'local\tools\ffmpeg\bin'

Write-Host "==========================================="
Write-Host "       CLIPSESE - MOTOR LOCAL"
Write-Host "==========================================="
if (-not (Test-Path $python) -or -not (Test-Path (Join-Path $frontendDist 'index.html'))) {
    Write-Host "Primero ejecuta INSTALAR_LOCAL.bat una sola vez." -ForegroundColor Yellow
    exit 1
}

$machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
$user = [Environment]::GetEnvironmentVariable('Path', 'User')
$env:Path = "$localFfmpegBin;$env:LOCALAPPDATA\Microsoft\WinGet\Links;$env:USERPROFILE\.deno\bin;$machine;$user;$env:Path"
if (-not (Get-Command 'ffmpeg.exe' -ErrorAction SilentlyContinue)) {
    Write-Host "No encuentro FFmpeg de ClipSese. Ejecuta de nuevo INSTALAR_LOCAL.bat." -ForegroundColor Red
    exit 1
}
New-Item -ItemType Directory -Path @($work, $logs, $runtimeTemp) -Force | Out-Null

# Starlette/UploadFile and Python use the system temp directory while parsing large uploads.
# Keep that traffic on the same drive as ClipSese instead of a nearly-full C: drive.
$env:TEMP = $runtimeTemp
$env:TMP = $runtimeTemp
$env:TMPDIR = $runtimeTemp
$env:STORAGE_DIR = $work
$env:CLIPSESE_LOCAL = '1'
$env:CLIPSESE_FRONTEND_DIST = $frontendDist
$env:CLIPSESE_ENCODER = 'auto'
$env:CLIPSESE_TTL_HOURS = '6'
$env:WHISPER_MODEL = 'base'
$env:WHISPER_DEVICE = 'cpu'
$env:WHISPER_COMPUTE_TYPE = 'int8'
$env:PYTHONUNBUFFERED = '1'
$env:CORS_ORIGINS = 'http://127.0.0.1:8000,http://localhost:8000'

# Optional. Only this ignored local file is read.
$privateCookies = Join-Path $root 'local\private\youtube-cookies.txt'
if (Test-Path $privateCookies) {
    $env:YOUTUBE_COOKIES_FILE = $privateCookies
    Write-Host "Cookies locales detectadas (no se muestran ni se suben)."
}

# Do not overwrite another application on port 8000.
try {
    $health = Invoke-RestMethod 'http://127.0.0.1:8000/api/health' -TimeoutSec 3
    if ($health.version -like '*local*' -and $health.ok) {
        Write-Host "ClipSese ya esta abierto en tu computadora."
        Start-Process 'http://127.0.0.1:8000/'
        exit 0
    }
    Write-Host "El puerto 8000 ya esta ocupado por otra aplicacion." -ForegroundColor Red
    exit 1
} catch {
    # Nobody is listening, so start the local service.
}

$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$stdout = Join-Path $logs "clipsese_$stamp.log"
$stderr = Join-Path $logs "clipsese_$stamp.errors.log"
Write-Host "Iniciando ClipSese (solo en tu PC)..."
$server = Start-Process -FilePath $python -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $backend -RedirectStandardOutput $stdout -RedirectStandardError $stderr -WindowStyle Hidden -PassThru

$started = $false
for ($i=0; $i -lt 45; $i++) {
    Start-Sleep -Seconds 1
    if ($server.HasExited) { break }
    try {
        $health = Invoke-RestMethod 'http://127.0.0.1:8000/api/health' -TimeoutSec 2
        if ($health.ok -and $health.version -like '*local*') {
            $started = $true
            break
        }
    } catch {}
}
if (-not $started) {
    Write-Host "El motor local no pudo arrancar. Log de errores:" -ForegroundColor Red
    if (Test-Path $stderr) { Get-Content $stderr -Tail 25 }
    if (Test-Path $stdout) { Get-Content $stdout -Tail 12 }
    try { if (-not $server.HasExited) { Stop-Process -Id $server.Id -Force } } catch {}
    exit 1
}

Write-Host ""
Write-Host "CLIPSESE ESTA FUNCIONANDO EN:" -ForegroundColor Green
Write-Host "http://127.0.0.1:8000/" -ForegroundColor Cyan
Write-Host ""
Write-Host "Manten ESTA ventana abierta mientras haces tus clips."
Write-Host "Cuando termines, pulsa Ctrl+C o cierra esta ventana."
Write-Host "Trabajo temporal: $work"
Write-Host "TEMP de uploads: $runtimeTemp"
Write-Host "Los proyectos sin actividad se borran a las seis horas."
Write-Host "El boton Finalizar y limpiar borra inmediatamente el proyecto terminado."
Start-Process 'http://127.0.0.1:8000/'

try {
    while (-not $server.HasExited) { Start-Sleep -Seconds 2 }
} finally {
    try {
        if (-not $server.HasExited) { Stop-Process -Id $server.Id -Force }
    } catch {}
    Write-Host "ClipSese local detenido."
}
