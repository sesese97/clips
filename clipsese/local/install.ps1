# ClipSese Windows installer. Run by double-clicking INSTALAR_LOCAL.bat.
# Installs local tools once, builds React once, never deploys to Railway/Vercel.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$venv = Join-Path $backend '.venv'
$pythonVenv = Join-Path $venv 'Scripts\python.exe'

function Refresh-LocalPath {
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$env:LOCALAPPDATA\Microsoft\WinGet\Links;$env:USERPROFILE\.deno\bin;$machine;$user;$env:Path"
}

function Has-Tool([string] $tool) {
    return [bool](Get-Command $tool -ErrorAction SilentlyContinue)
}

function Get-Python {
    if (Has-Tool 'py.exe') {
        foreach ($version in @('-3.11','-3.12')) {
            try {
                $test = & py.exe $version -c 'import sys; print(sys.version_info.major, sys.version_info.minor)' 2>$null
                if ($LASTEXITCODE -eq 0) { return @{ exe='py.exe'; prefix=@($version) } }
            } catch {}
        }
    }
    foreach ($cmd in @('python.exe', 'python3.exe')) {
        if (Has-Tool $cmd) {
            try {
                $test = & $cmd -c 'import sys; print(sys.version_info.major,sys.version_info.minor)' 2>$null
                if ($LASTEXITCODE -eq 0 -and ($test -match '^3 (11|12)$')) {
                    return @{ exe=$cmd; prefix=@() }
                }
            } catch {}
        }
    }
    return $null
}

function Install-Package([string] $name, [string] $id) {
    if (-not (Has-Tool 'winget.exe')) {
        Write-Host "Falta $name. Instala Microsoft App Installer (winget) o usa los enlaces del README_LOCAL." -ForegroundColor Yellow
        return
    }
    Write-Host ""
    Write-Host "Instalando $name por WinGet ($id). Puede pedir permiso de Windows..." -ForegroundColor Cyan
    & winget.exe install --id $id -e --source winget --silent --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) {
        Write-Host "WinGet devolvio codigo $LASTEXITCODE para $name. Verificare de todas maneras." -ForegroundColor Yellow
    }
    Refresh-LocalPath
}

Write-Host "==========================================="
Write-Host "      CLIPSESE - INSTALACION EN TU PC"
Write-Host "==========================================="
Write-Host "No se cargaran videos ni secretos a GitHub, Railway o Vercel."
Refresh-LocalPath

$pythonChoice = Get-Python
if (-not $pythonChoice) {
    Install-Package 'Python 3.11' 'Python.Python.3.11'
    $pythonChoice = Get-Python
}
if (-not (Has-Tool 'node.exe') -or -not (Has-Tool 'npm.cmd')) {
    Install-Package 'Node.js LTS' 'OpenJS.NodeJS.LTS'
}
if (-not (Has-Tool 'ffmpeg.exe') -or -not (Has-Tool 'ffprobe.exe')) {
    Install-Package 'FFmpeg' 'Gyan.FFmpeg'
}
if (-not (Has-Tool 'deno.exe')) {
    Install-Package 'Deno (para importar YouTube)' 'DenoLand.Deno'
}
Refresh-LocalPath
$pythonChoice = Get-Python

$missing = @()
if (-not $pythonChoice) { $missing += 'Python 3.11' }
if (-not (Has-Tool 'node.exe') -or -not (Has-Tool 'npm.cmd')) { $missing += 'Node.js LTS' }
if (-not (Has-Tool 'ffmpeg.exe') -or -not (Has-Tool 'ffprobe.exe')) { $missing += 'FFmpeg' }
if (-not (Has-Tool 'deno.exe')) {
    Write-Host "Aviso: Deno aun no aparece. Puedes usar archivos originales, pero importar YouTube puede fallar." -ForegroundColor Yellow
}
if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "Faltan herramientas: $($missing -join ', ')." -ForegroundColor Red
    Write-Host "Si WinGet acaba de instalarlas, CIERRA ESTA VENTANA y ejecuta INSTALAR_LOCAL.bat otra vez."
    Write-Host "Si siguen faltando, revisa clipsese\local\README_LOCAL.md."
    exit 1
}

Write-Host ""
Write-Host "[1/3] Preparando Python local..."
if (-not (Test-Path $pythonVenv)) {
    $exe = $pythonChoice.exe
    $prefix = $pythonChoice.prefix
    & $exe @prefix -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw 'Python no pudo crear el entorno local.' }
}
$env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
& $pythonVenv -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'No se pudo actualizar pip.' }

# The cloud-only bgutil helper is not needed when using the PC's own connection.
$requirements = Join-Path $backend 'requirements.txt'
$localReq = Join-Path $env:TEMP 'clipsese-local-requirements.txt'
Get-Content $requirements | Where-Object { $_ -notmatch 'bgutil-ytdlp-pot-provider' } | Set-Content -Encoding ASCII $localReq
& $pythonVenv -m pip install -r $localReq
if ($LASTEXITCODE -ne 0) { throw 'La instalacion de Python fallo. Revisa el mensaje anterior.' }

Write-Host ""
Write-Host "Verificando que el backend Python importe sin errores..."
Push-Location $backend
try {
    & $pythonVenv -m compileall -q 'app'
    if ($LASTEXITCODE -ne 0) { throw 'Hay un error de sintaxis en el backend.' }
    & $pythonVenv -c 'from app.main import app; print("Backend OK")'
    if ($LASTEXITCODE -ne 0) { throw 'El backend no pudo importar. Revisa las dependencias.' }
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "[2/3] Preparando la interfaz..."
Push-Location $frontend
try {
    # Always build against localhost even if this machine inherited a cloud variable.
    $env:VITE_API_URL = 'http://127.0.0.1:8000'
    & npm.cmd install --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'npm install fallo.' }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'La compilacion de la interfaz fallo.' }
} finally {
    Pop-Location
}
if (-not (Test-Path (Join-Path $frontend 'dist\index.html'))) {
    throw 'No se genero frontend\dist\index.html.'
}

Write-Host ""
Write-Host "[3/3] Preparando almacenamiento temporal..."
$work = Join-Path $env:LOCALAPPDATA 'ClipSese\Work'
$logs = Join-Path $env:LOCALAPPDATA 'ClipSese\Logs'
New-Item -ItemType Directory -Path @($work, $logs) -Force | Out-Null
Write-Host ""
Write-Host "LISTO. Para abrir ClipSese, doble clic en INICIAR_LOCAL.bat." -ForegroundColor Green
Write-Host "La primera transcripcion con Whisper puede tardar mientras baja el modelo."
Write-Host "No copies cookies ni secretos al repositorio."
