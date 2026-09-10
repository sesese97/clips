# ClipSese MVP

Herramienta privada para convertir videos horizontales en clips verticales de **máximo 30 segundos** para TikTok, Reels y Shorts.

## Qué ya incluye

- Entrada por **archivo original** o **URL de YouTube**.
- El archivo fuente se conserva intacto; se genera un proxy H.264 solamente para el preview.
- Transcripción local con `faster-whisper`.
- Búsqueda por **jugador/palabra**.
- Búsqueda por **tema** con embeddings multilingües (`sentence-transformers`).
- Corte exacto por tiempo, con límite estricto de 30 s.
- Selector visual de zonas: Cámara 1, Cámara 2 y Contenido.
- 3 layouts verticales 1080×1920:
  1. 1 cámara + multimedia/contenido.
  2. 2 cámaras.
  3. 2 cámaras + multimedia/contenido.
- Multimedia externa por archivo. También se intenta importar enlaces HTTPS de YouTube, X/Twitter y TikTok mediante `yt-dlp`.
- Render final desde el **archivo fuente original**, H.264 High Profile, CRF 17, preset `slow`, audio AAC 256 kbps, `+faststart`.
- Si no agregas multimedia externa en layouts 1 o 3, usa el recorte `Contenido` del video fuente.

> Importante: la importación desde plataformas depende de que el contenido sea accesible y de los cambios que dichas plataformas hagan. Para máxima calidad y fiabilidad, el archivo original es la fuente recomendada. Usa únicamente contenido propio o para el que tengas autorización.

## Arquitectura

- `frontend/`: React + TypeScript + Vite. Ideal para Vercel.
- `backend/`: FastAPI + FFmpeg + yt-dlp + faster-whisper. Debe vivir en un servidor con proceso persistente y disco/objeto, no en una función serverless de Vercel.

## Arranque rápido con Docker

Requisitos: Docker Desktop.

```bash
docker compose up --build
```

Después abre:

- Web: `http://localhost:5173`
- API: `http://localhost:8000/api/health`

La primera transcripción tarda más porque Whisper descarga el modelo. La primera búsqueda temática también descarga su modelo de embeddings.

## Arranque manual

### Backend

Usa Python 3.11 o 3.12 y FFmpeg instalado.

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

## Subirlo a GitHub

Crea un repositorio vacío, por ejemplo `CLIPSESE`, y desde la carpeta raíz:

```bash
git init
git add .
git commit -m "ClipSese MVP"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/CLIPSESE.git
git push -u origin main
```

## Deploy recomendado

### Frontend: Vercel

1. Importa el repo desde GitHub.
2. Root Directory: `frontend`.
3. Build Command: `npm run build`.
4. Output Directory: `dist`.
5. Agrega `VITE_API_URL=https://TU-BACKEND`.

### Backend: Railway / Render / VPS

Usa `backend/Dockerfile`. Necesitas persistencia para `/data` o adaptar `STORAGE_DIR` a almacenamiento de objetos.

Variables principales:

```env
STORAGE_DIR=/data
CORS_ORIGINS=https://TU-FRONTEND.vercel.app
WHISPER_MODEL=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

Para un servidor con GPU NVIDIA puedes usar `WHISPER_DEVICE=cuda` y un compute type compatible.

## Lo que deliberadamente NO metí todavía

- Subtítulos automáticos.
- Auto-follow de rostros.
- Detección de quién está hablando.
- Guardado de presets/layouts por programa.
- Biblioteca persistente de proyectos en la nube.
- Login/usuarios.
- Publicación automática a TikTok/YouTube.

Esas cosas son fase 2. El MVP se concentra en lo que realmente necesitas: **encontrar un take específico y convertirlo en un clip vertical bien compuesto y con buena calidad**.
