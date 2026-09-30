# Expose the LOCAL app only to authenticated devices on the owner's Tailscale network.
# NEVER use Funnel or open a public router port.
$ErrorActionPreference = 'Stop'
Write-Host "==========================================="
Write-Host "    CLIPSESE - ACCESO SEGURO DESDE IPAD"
Write-Host "==========================================="
Write-Host ""
Write-Host "Antes de continuar:"
Write-Host "1. Instala ClipSese y verifica que INICIAR_LOCAL.bat abre la web en esta PC."
Write-Host "2. Instala Tailscale en esta PC e inicia sesion."
Write-Host "3. Instala la app Tailscale en el iPad y usa LA MISMA CUENTA."
Write-Host ""
$ts = Get-Command 'tailscale.exe' -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Source
if (-not $ts) {
    $candidate = Join-Path $env:ProgramFiles 'Tailscale\tailscale.exe'
    if (Test-Path $candidate) { $ts = $candidate }
}
if (-not $ts) {
    Write-Host "Aun no encuentro Tailscale para Windows." -ForegroundColor Yellow
    Start-Process "https://tailscale.com/download/windows"
    Write-Host "Instalalo desde la pagina oficial, inicia sesion y vuelve a abrir CONFIGURAR_IPAD.bat."
    exit 1
}
Write-Host "Comprobando Tailscale..."
$state = & $ts status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Tailscale no esta conectado: abre su icono junto al reloj y pulsa Log in." -ForegroundColor Yellow
    Write-Host ($state | Out-String)
    exit 1
}
try {
    $health = Invoke-RestMethod 'http://127.0.0.1:8000/api/health' -TimeoutSec 4
    if (-not $health.ok -or $health.version -notlike '*local*') { throw 'No esta abierto ClipSese LOCAL.' }
} catch {
    Write-Host "Abre primero INICIAR_LOCAL.bat y deja la ventana abierta." -ForegroundColor Yellow
    exit 1
}
Write-Host ""
Write-Host "Activando Tailscale Serve (privado, NO publica al internet)..."
$result = & $ts serve --bg 8000 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host ($result | Out-String)
    Write-Host "Si pide HTTPS, habilita certificados HTTPS en los ajustes DNS de tu red Tailscale." -ForegroundColor Yellow
    Write-Host "Consulta clipsese\local\README_IPAD.md."
    exit 1
}
Write-Host ($result | Out-String)
Write-Host ""
Write-Host "DIRECCION PRIVADA PARA EL IPAD:" -ForegroundColor Green
& $ts serve status
Write-Host ""
Write-Host "Abre la direccion https que te aparece arriba desde Safari CON TAILSCALE CONECTADO."
Write-Host "No abras 127.0.0.1 en el iPad: esa direccion apuntaria al propio iPad."
Write-Host "La PC y el motor ClipSese deben seguir encendidos para editar o exportar."
