import os
import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .models import RenderRequest, SearchRequest
from .transcribe import keyword_search, theme_search, transcribe_project
from .utils import is_allowed_url, project_dir, read_json, runtime_diagnostics, write_json
from .video import add_media_upload, add_media_url, ingest_upload, ingest_youtube, render_clip

app = FastAPI(title="ClipSese API", version="0.3.0")
origins = [x.strip().rstrip("/") for x in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"app": "ClipSese API", "ok": True, "health": "/api/health", "docs": "/docs"}


@app.get("/api/health")
def health():
    return {"ok": True, "version": "0.3.0", "runtime": runtime_diagnostics()}


@app.post("/api/projects")
async def create_project(
    background: BackgroundTasks,
    file: UploadFile | None = File(default=None),
    youtube_url: str | None = Form(default=None),
):
    if not file and not youtube_url:
        raise HTTPException(400, "Sube un archivo o pega un enlace de YouTube")
    if youtube_url and not is_allowed_url(youtube_url, youtube_only=True):
        raise HTTPException(400, "Solo se admiten URLs HTTPS de YouTube como fuente principal")

    pid = uuid.uuid4().hex[:16]

    try:
        if file:
            suffix = Path(file.filename or "video.mp4").suffix or ".mp4"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                shutil.copyfileobj(file.file, tmp)
                temp_path = Path(tmp.name)
            return ingest_upload(pid, temp_path, file.filename or "video")

        payload = {
            "id": pid,
            "status": "importing",
            "import_stage": "queued",
            "original_name": "YouTube",
            "source_url": youtube_url,
            "source_file": "",
            "preview_file": "",
            "metadata": {"duration": 0, "width": 0, "height": 0, "fps": "0/1"},
            "transcript_status": "not_started",
        }
        write_json(project_dir(pid) / "project.json", payload)
        background.add_task(ingest_youtube, pid, youtube_url)
        return payload
    except Exception as e:
        print(f"[CLIPSESE] create_project ERROR: {type(e).__name__}: {e}", flush=True)
        raise HTTPException(500, str(e))


@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    data = read_json(project_dir(project_id) / "project.json")
    if not data:
        raise HTTPException(404, "Proyecto no encontrado")
    data["media"] = read_json(project_dir(project_id) / "media.json", []) or []
    data["renders"] = read_json(project_dir(project_id) / "renders.json", []) or []
    return data


@app.post("/api/projects/{project_id}/transcribe")
def transcribe(project_id: str, background: BackgroundTasks):
    pj = read_json(project_dir(project_id) / "project.json")
    if not pj:
        raise HTTPException(404, "Proyecto no encontrado")
    if pj.get("status") != "ready":
        raise HTTPException(409, "Espera a que termine la importación del video")
    background.add_task(transcribe_project, project_id)
    return {"status": "processing"}


@app.post("/api/projects/{project_id}/search")
def search(project_id: str, req: SearchRequest):
    pj = read_json(project_dir(project_id) / "project.json")
    if not pj:
        raise HTTPException(404, "Proyecto no encontrado")
    if pj.get("transcript_status") != "ready":
        raise HTTPException(409, "Primero termina la transcripción")
    if req.mode == "keyword":
        return {"results": keyword_search(project_id, req.query, req.max_results)}
    return {"results": theme_search(project_id, req.query, req.max_results)}


@app.post("/api/projects/{project_id}/media")
async def add_media(project_id: str, file: UploadFile | None = File(default=None), url: str | None = Form(default=None)):
    if not read_json(project_dir(project_id) / "project.json"):
        raise HTTPException(404, "Proyecto no encontrado")
    if not file and not url:
        raise HTTPException(400, "Sube un archivo o pega un enlace")
    if url and not is_allowed_url(url, youtube_only=False):
        raise HTTPException(400, "URL no admitida. Usa YouTube, X o TikTok por HTTPS")
    try:
        if file:
            suffix = Path(file.filename or "asset.mp4").suffix or ".mp4"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                shutil.copyfileobj(file.file, tmp)
                temp_path = Path(tmp.name)
            return add_media_upload(project_id, temp_path, file.filename or "media")
        return add_media_url(project_id, url)
    except Exception as e:
        print(f"[CLIPSESE] add_media ERROR: {type(e).__name__}: {e}", flush=True)
        raise HTTPException(500, str(e))


@app.post("/api/projects/{project_id}/render")
def render(project_id: str, req: RenderRequest):
    try:
        return render_clip(project_id, req)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print(f"[CLIPSESE] render ERROR: {type(e).__name__}: {e}", flush=True)
        raise HTTPException(500, str(e))


@app.get("/files/{project_id}/{filename}")
def files(project_id: str, filename: str):
    safe = Path(filename).name
    path = project_dir(project_id) / safe
    if not path.exists():
        raise HTTPException(404, "Archivo no encontrado")
    return FileResponse(path)
