# ClipSese

Editor privado de clips verticales para videos propios: cortar por tiempo, jugador NFL/palabra o tema; tres layouts (1 cámara + multimedia, 2 cámaras o 2 cámaras + multimedia); hasta **90 segundos**, exportación 1080x1920 H.264 y audio AAC.

## NUEVO: ClipSese LOCAL para Windows (sin Railway)

La versión local está preparada en esta rama y utiliza tu PC para descargar, transcribir y renderizar. No requiere Railway, hosting de video ni cuenta de pago. Es la opción adecuada para extraer muchos clips de un mismo programa y limpiar después los temporales.

**[Instrucciones paso a paso: local/README_LOCAL.md](local/README_LOCAL.md)**

Dentro de esta carpeta `clipsese` tienes dos accesos directos:

1. `INSTALAR_LOCAL.bat`: úsalo **una sola vez** para preparar Python, Node, FFmpeg y Deno. Requiere conexión a Internet para descargar programas y modelos.
2. `INICIAR_LOCAL.bat`: úsalo **cada vez** que quieras editar. Abre `http://127.0.0.1:8000/` y mantén abierta su ventana mientras trabajes.

Conserva el repositorio en una carpeta de Documentos y descomprime el ZIP antes de ejecutar los BAT. No hacen falta Docker, GitHub Desktop ni comandos de Railway.

## Arquitectura local

- `frontend/`: aplicación React + TypeScript. El instalador compila el frontend a `frontend/dist`.
- `backend/`: FastAPI, FFmpeg, yt-dlp, subtítulos de YouTube, respaldo local Whisper y buscador NFL. El servidor local sirve también el frontend compilado.
- Archivos intermedios en `%LOCALAPPDATA%\ClipSese\Work`. Los proyectos sin actividad se limpian a las seis horas mientras el motor está encendido.
- Al terminar de sacar varios clips, **Finalizar y limpiar** elimina inmediatamente todo el proyecto temporal. Los MP4 ya descargados en tu carpeta Descargas no se tocan.
- `local/private/` está protegido por .gitignore. Nunca guardes allí algo que después vayas a subir manualmente a otro servicio.

La exportación intenta `h264_nvenc` de NVIDIA cuando está disponible, con retroceso automático a `libx264 CRF 17`. Siempre H.264 1080x1920 a 60 fps.

## Antiguo modo de servidor

El código incluye un `backend/Dockerfile` y `docker-compose.yml` para uso opcional. No forman parte del arranque LOCAL. La interfaz cloud antigua puede seguir conectada a Railway si su hosting sigue contratado, pero **no es necesaria** para esta versión.

## Límites conocidos

- La versión local funciona en la **misma PC** donde ejecutas el motor. No ofrece acceso remoto seguro desde iPhone ni genera un sitio público.
- Los servicios externos pueden bloquear la importación; para tu propio material, el archivo original es siempre una alternativa fiable.
- El reconocimiento de jugadores NFL mejora la búsqueda, pero ningún ASR puede garantizar acertar todos los apellidos.
- Las cookies de cuenta son opcionales. No las compartas en chats ni las subas a GitHub.
- Usa contenido propio o con autorización.
