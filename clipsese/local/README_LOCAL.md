# ClipSese LOCAL para Windows (sin Railway)

Esta version reutiliza el editor, buscador NFL y los 3 layouts que ya tenemos, pero ejecuta YouTube, Python, FFmpeg y Whisper en TU computadora. Solo sirve mientras la PC esta encendida. No instala un servicio publico ni requiere pagar Railway.

IMPORTANTE: esta version esta en la rama separada clipsese-local-windows, para no romper la web que aun exista en Vercel. No copies variables ni cookies desde Railway al repositorio.

## Una sola vez: instalacion

1. Desde tu cuenta de GitHub, abre el repositorio sesese97/clips y selecciona la rama **clipsese-local-windows**. Ve a **Code > Download ZIP**. Descomprime TODO el ZIP, por ejemplo en Documentos (no en una carpeta sincronizada con la nube si vas a manejar cookies).
2. Entra a la carpeta **clipsese** que esta dentro del ZIP. Veras los archivos **INSTALAR_LOCAL.bat** e **INICIAR_LOCAL.bat**. No necesitas bajar GitHub Desktop, abrir Railway ni usar Docker Desktop.
3. Doble clic en **INSTALAR_LOCAL.bat**. Sigue las solicitudes de Windows. Este instalador usa WinGet (la herramienta de Microsoft) para instalar, si faltan, Python 3.11, Node.js LTS, FFmpeg y Deno. Luego instala las dependencias Python en una carpeta privada de ClipSese y compila el sitio React.
4. Si acaba de instalar alguno de esos programas y aun indica que falta, cierra esa ventana, vuelve a abrir **INSTALAR_LOCAL.bat** y deja que continue. Esto se debe a que Windows a veces necesita una terminal nueva para actualizar PATH.
5. Cuando veas **LISTO**, la instalacion ya termino. No tienes que volver a instalar cada vez que quieras hacer clips.

**Si Windows no tiene WinGet**, instala Microsoft App Installer desde Microsoft Store. Alternativamente puedes instalar las herramientas por sus medios oficiales y ejecutar de nuevo el instalador:
- Python 3.11: https://www.python.org/downloads/windows/
- Node.js LTS: https://nodejs.org/en/download
- FFmpeg para Windows: https://www.gyan.dev/ffmpeg/builds/
- Deno: https://docs.deno.com/runtime/getting_started/installation/

Si al abrir un BAT Windows muestra un aviso de seguridad, comprueba primero que lo descargaste de TU repositorio. Puedes inspeccionar los BAT y los PS1 con Bloc de notas; no requieren permisos de administrador por si mismos (WinGet puede solicitar permisos para herramientas externas).

## Uso de todos los dias

1. Doble clic en **INICIAR_LOCAL.bat** dentro de **clipsese**.
2. Se abre tu navegador en **http://127.0.0.1:8000/**. Si no se abre, pega esa direccion MANUALMENTE en Chrome de la PC. Ahi esta tu ClipSese. El sitio de Vercel NO es la version local.
3. Mantén la ventana del motor local abierta. Si la cierras, ClipSese deja de procesar. El motor NO ocupa recursos cuando no lo estas usando.
4. Carga tu YouTube o archivo original y edita exactamente como antes. Los clips duran hasta 90 segundos. Las tres opciones verticales siguen disponibles y las descargas van directo a tu PC.
5. Usa **Finalizar y limpiar** cuando ya descargaste TODOS los MP4 de esa sesion. Esto borra el video fuente temporal, los previews, la transcripcion y las exportaciones guardadas solo en el motor local.

Los proyectos sin actividad se eliminan despues de 6 horas. El sitio envia una señal mientras lo tienes abierto para que no pierdas una sesion activa. Nunca se elimina el archivo que YA descargaste al disco de tu PC.

**Calidad:** la salida es 1080x1920, H.264 High, AAC 256 kb/s, 60 fps. La PC intenta NVIDIA NVENC si tu driver y el FFmpeg instalado lo soportan, con calidad visual alta; si no, vuelve al antiguo libx264 CRF 17 sin que tengas que intervenir. NVENC CQ18 no es numericamente identico a CRF17, por lo que compara visualmente un primer clip antes de publicar.

**YouTube:** esta version usa la IP de tu propia conexion. Normalmente no necesita cookies. La disponibilidad de YouTube, X y TikTok depende de cada plataforma. Como opcion secundaria, si YouTube requiere autenticacion de TU propio contenido, crea la carpeta **clipsese/local/private** y guarda un archivo Netscape de una cuenta dedicada como **youtube-cookies.txt**. Cierra el navegador antes de exportarlo para reducir rotaciones. La carpeta private esta excluida de GitHub. No compartas cookies en el chat ni en commits.

**Transcripcion:** primero se intentan subtitulos del video; si faltan, se utiliza Whisper local en espanol. La primera vez que uses Whisper descarga un modelo: requiere internet y paciencia. Los nombres de jugadores siguen beneficiandose del directorio publico de Sleeper y de las correcciones foneticas que ya construimos. Si prefieres no depender de esas fuentes, puedes seguir cortando manualmente por tiempo.

## Solucion rapida de problemas

- **La app dice que no conecta:** revisa que INICIAR_LOCAL.bat siga abierto y visita http://127.0.0.1:8000/api/health. Deberia mostrar ok true y una version terminada en -local.
- **FFmpeg falla al instalar por WinGet:** el instalador actualizado ya no depende de ese paquete. Descarga una copia portatil de FFmpeg Essentials directamente desde gyan.dev y la guarda solo dentro de `clipsese/local/tools/ffmpeg`. Si viste el error `El archivo de instalador anidado no existe`, descarga de nuevo la rama `clipsese-local-windows` o reemplaza tu carpeta `clipsese` por la nueva y vuelve a ejecutar INSTALAR_LOCAL.bat.
- **El instalador no reconoce un programa recien instalado:** cierra la terminal y ejecuta INSTALAR_LOCAL.bat de nuevo; no borres nada.
- **YouTube no importa:** comprueba Deno, prueba con un video original y actualiza yt-dlp mediante INSTALAR_LOCAL.bat. No vuelvas a poner cookies en Railway.
- **La RTX no codifica:** no bloquea el flujo: ClipSese repite la exportacion con CPU. Para ver el modo seleccionado, consulta los logs.
- **No ves el MP4:** usa el boton **Descargar ultimo MP4** bajo Exportar, y comprueba la carpeta Descargas de Windows.
- **Se fue la luz:** al abrir de nuevo no hay cuenta ni nube de respaldo; los proyectos temporales se conservan un tiempo si Windows y el disco sobreviven, pero no es un sistema de archivo permanente.

Los logs viven en %LOCALAPPDATA%\ClipSese\Logs y los temporales en %LOCALAPPDATA%\ClipSese\Work. Ninguno se sube automaticamente a GitHub.

**iPad y uso fuera de casa:** esta misma versión incorpora CONFIGURAR_IPAD.bat para conectar el motor de Windows a Safari de iPad mediante Tailscale Serve (red privada, no pública). Instala la app Tailscale en PC e iPad y sigue las instrucciones de [README_IPAD.md](README_IPAD.md). La PC y el motor deben seguir encendidos. Revisa el plan que corresponda si lo utilizarás comercialmente.
