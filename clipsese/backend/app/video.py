import base64
import os
import shutil
import sys
import uuid
from pathlib import Path

from .models import Crop, RenderRequest
from .utils import CommandError, ffprobe, project_dir, read_json, run, write_json


def _cookie_file() -> Path | None:
    raw = os.getenv("YOUTUBE_COOKIES_B64", "").strip()
    if not raw:
        return None
    path = Path("/tmp/clipsese_youtube_cookies.txt")
    try:
        path.write_bytes(base64.b64decode(raw, validate=True))
        return path
    except Exception as e:
        raise RuntimeError("YOUTUBE_COOKIES_B64 existe pero no es Base64 válido") from e


def _set_import_state(project_id: str, *, status: str | None = None, stage: str | None = None, error: str | None = None, **extra):
    pdir = project_dir(project_id)
    data = read_json(pdir / "project.json") or {"id": project_id}
    if status is not None:
        data["status"] = status
    if stage is not None:
        data["import_stage"] = stage
    if error is not None:
        data["import_error"] = error
    data.update(extra)
    write_json(pdir / "project.json", data)
    return data


def _download_with_ytdlp(url: str, out_dir: Path, stem: str) -> Path:
    out_tpl = str(out_dir / f"{stem}.%(ext)s")
    cookies = _cookie_file()

    # Preferimos siempre el mejor master disponible. El preview del editor se crea aparte,
    # así que un 1440p/4K60 de YouTube se conserva y el render final usa ese master.
    base = [
        sys.executable, "-m", "yt_dlp",
        "--no-playlist",
        "--force-ipv4",
        "--retries", "3",
        "--fragment-retries", "3",
        "--no-progress",
        "--js-runtimes", "deno:/usr/local/bin/deno",
        "--merge-output-format", "mp4",
        "-f", "bv*+ba/b",
        "-o", out_tpl,
    ]
    if cookies:
        base += ["--cookies", str(cookies)]

    # YouTube trata de forma distinta varias familias de cliente. En IPs de datacenter
    # algunos clientes pueden disparar el anti-bot mientras otros siguen funcionando.
    # Probamos alternativas oficiales de yt-dlp antes de rendirnos y pedir cookies.
    attempts: list[tuple[str, list[str]]] = [
        ("default", []),
        ("web_embedded", ["--extractor-args", "youtube:player_client=web_embedded"]),
        ("web_safari", ["--extractor-args", "youtube:player_client=web_safari"]),
    ]

    last_error: Exception | None = None
    for label, extra in attempts:
        # Limpia restos parciales del intento anterior para no confundir el resultado.
        for old in out_dir.glob(f"{stem}.*"):
            if old.is_file() and old.name.endswith((".part", ".ytdl")):
                try:
                    old.unlink()
                except OSError:
                    pass

        cmd = base[:-2] + extra + base[-2:] + [url]
        try:
            print(f"[CLIPSESE] YouTube attempt: {label}", flush=True)
            run(cmd, timeout=1200)
            candidates = [
                p for p in out_dir.glob(f"{stem}.*")
                if p.is_file() and not p.name.endswith((".part", ".ytdl"))
            ]
            candidates = sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)
            if candidates:
                return candidates[0]
        except CommandError as e:
            last_error = e
            msg = str(e)
            low = msg.lower()
            # Si no es el típico bloqueo de YouTube, no tiene sentido probar clientes al azar.
            if not any(x in low for x in ("sign in to confirm", "not a bot", "login_required", "403")):
                if "javascript runtime" in low or "js challenge" in low:
                    raise RuntimeError(
                        "El runtime de YouTube no quedó disponible en el contenedor. "
                        "Abre /api/health para comprobar Deno y yt-dlp."
                    ) from e
                raise RuntimeError(f"YouTube no pudo importarse: {msg[-1800:]}") from e

    msg = str(last_error or "")
    raise RuntimeError(
        "YouTube está rechazando temporalmente la IP de Railway (anti-bot). "
        "ClipSese probó varios clientes de YouTube y ninguno pudo abrir el video. "
        "Para una solución estable hay que autenticar yt-dlp con cookies de una cuenta dedicada, "
        "o usar Archivo original."
    ) from last_error


def ingest_upload(project_id: str, src: Path, original_name: str) -> dict:
    pdir = project_dir(project_id)
    ext = src.suffix.lower() or ".mp4"
    dest = pdir / f"source{ext}"
    shutil.move(str(src), str(dest))
    meta = ffprobe(dest)
    _make_proxy(dest, pdir / "preview.mp4")
    payload = {
        "id": project_id,
        "status": "ready",
        "import_stage": "ready",
        "original_name": original_name,
        "source_file": dest.name,
        "preview_file": "preview.mp4",
        "metadata": meta,
        "transcript_status": "not_started",
    }
    write_json(pdir / "project.json", payload)
    return payload


def ingest_youtube(project_id: str, url: str) -> dict:
    pdir = project_dir(project_id)
    try:
        _set_import_state(project_id, status="importing", stage="downloading", error="")
        source = _download_with_ytdlp(url, pdir, "source")

        _set_import_state(project_id, stage="analyzing")
        meta = ffprobe(source)

        # El master se conserva en la máxima calidad que entregue YouTube. Para navegar
        # por el editor usamos un proxy ligero y el render final vuelve siempre al master.
        _set_import_state(project_id, stage="preparing_preview")
        preview_path = pdir / "preview.mp4"
        _make_proxy(source, preview_path)
        preview_name = preview_path.name

        payload = {
            "id": project_id,
            "status": "ready",
            "import_stage": "ready",
            "import_error": "",
            "original_name": "YouTube",
            "source_url": url,
            "source_file": source.name,
            "preview_file": preview_name,
            "metadata": meta,
            "transcript_status": "not_started",
        }
        write_json(pdir / "project.json", payload)
        return payload
    except Exception as e:
        message = str(e)
        payload = _set_import_state(project_id, status="error", stage="error", error=message)
        print(f"[CLIPSESE] ingest_youtube ERROR: {type(e).__name__}: {message}", flush=True)
        # IMPORTANTE: no relanzar la excepción. Starlette ejecuta BackgroundTasks después
        # de mandar la respuesta; si la tarea lanza una excepción, el navegador puede ver
        # un falso 'Failed to fetch' aunque el POST ya haya respondido 200.
        return payload


def _make_proxy(src: Path, dest: Path):
    run([
        "ffmpeg", "-y", "-i", str(src),
        "-vf", "scale='min(960,iw)':-2,fps=30",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
        str(dest)
    ], timeout=1800)


def source_path(project_id: str) -> Path:
    pdir = project_dir(project_id)
    pj = read_json(pdir / "project.json") or {}
    name = pj.get("source_file")
    if not name:
        raise FileNotFoundError("Proyecto sin video fuente")
    return pdir / name


def add_media_upload(project_id: str, src: Path, original_name: str) -> dict:
    pdir = project_dir(project_id)
    mid = uuid.uuid4().hex[:12]
    ext = src.suffix.lower() or ".mp4"
    dest = pdir / f"media_{mid}{ext}"
    shutil.move(str(src), str(dest))
    item = {"id": mid, "file": dest.name, "name": original_name, "type": _media_type(dest)}
    media = read_json(pdir / "media.json", []) or []
    media.append(item)
    write_json(pdir / "media.json", media)
    return item


def add_media_url(project_id: str, url: str) -> dict:
    pdir = project_dir(project_id)
    mid = uuid.uuid4().hex[:12]
    dest = _download_with_ytdlp(url, pdir, f"media_{mid}")
    item = {"id": mid, "file": dest.name, "name": url, "type": _media_type(dest), "source_url": url}
    media = read_json(pdir / "media.json", []) or []
    media.append(item)
    write_json(pdir / "media.json", media)
    return item


def _media_type(path: Path) -> str:
    if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
        return "image"
    return "video"


def _crop_filter(label: str, crop: Crop, width: int, height: int, out_label: str) -> str:
    return (
        f"[{label}]crop=iw*{crop.w:.8f}:ih*{crop.h:.8f}:iw*{crop.x:.8f}:ih*{crop.y:.8f},"
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height}[{out_label}]"
    )


def render_clip(project_id: str, req: RenderRequest) -> dict:
    if req.end <= req.start:
        raise ValueError("El final debe ser posterior al inicio")
    if req.end - req.start > 30.001:
        raise ValueError("Los clips no pueden exceder 30 segundos")
    if req.layout in {"two_cameras", "two_media"} and req.camera2 is None:
        raise ValueError("El layout requiere cámara 2")
    if req.layout in {"one_media", "two_media"} and not req.media_id and req.content is None:
        raise ValueError("El layout requiere multimedia externa o un recorte de contenido")

    pdir = project_dir(project_id)
    src = source_path(project_id)
    render_id = uuid.uuid4().hex[:12]
    out = pdir / f"clip_{render_id}.mp4"
    duration = req.end - req.start

    cmd = ["ffmpeg", "-y", "-ss", f"{req.start:.3f}", "-t", f"{duration:.3f}", "-i", str(src)]
    media_item = None
    if req.media_id:
        media = read_json(pdir / "media.json", []) or []
        media_item = next((m for m in media if m["id"] == req.media_id), None)
        if not media_item:
            raise ValueError("Multimedia no encontrada")
        mpath = pdir / media_item["file"]
        if media_item["type"] == "image":
            cmd += ["-loop", "1", "-framerate", "30", "-i", str(mpath)]
        else:
            cmd += ["-stream_loop", "-1", "-i", str(mpath)]

    filters: list[str] = []
    if req.layout == "one_media":
        source_copies = 2 if not media_item else 1
    elif req.layout == "two_cameras":
        source_copies = 2
    else:
        source_copies = 3 if not media_item else 2

    if source_copies == 1:
        filters.append("[0:v]null[s0]")
    else:
        labels = "".join(f"[s{i}]" for i in range(source_copies))
        filters.append(f"[0:v]split={source_copies}{labels}")

    filters.append(_crop_filter("s0", req.camera1, 1080 if req.layout != "two_media" else 540, 720 if req.layout != "two_cameras" else 960, "cam1"))

    if req.layout == "one_media":
        if media_item:
            filters.append("[1:v]scale=1080:1200:force_original_aspect_ratio=increase,crop=1080:1200[media]")
        else:
            filters.append(_crop_filter("s1", req.content, 1080, 1200, "media"))
        filters.append("[cam1][media]vstack=inputs=2[outv]")
    elif req.layout == "two_cameras":
        filters.append(_crop_filter("s1", req.camera2, 1080, 960, "cam2"))
        filters.append("[cam1][cam2]vstack=inputs=2[outv]")
    else:
        filters.append(_crop_filter("s1", req.camera2, 540, 720, "cam2"))
        filters.append("[cam1][cam2]hstack=inputs=2[top]")
        if media_item:
            filters.append("[1:v]scale=1080:1200:force_original_aspect_ratio=increase,crop=1080:1200[media]")
        else:
            filters.append(_crop_filter("s2", req.content, 1080, 1200, "media"))
        filters.append("[top][media]vstack=inputs=2[outv]")

    cmd += [
        "-filter_complex", ";".join(filters),
        "-map", "[outv]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-profile:v", "high",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k",
        "-movflags", "+faststart", "-shortest", str(out)
    ]
    run(cmd, timeout=1800)
    info = ffprobe(out)
    item = {"id": render_id, "file": out.name, "metadata": info, "start": req.start, "end": req.end, "layout": req.layout}
    renders = read_json(pdir / "renders.json", []) or []
    renders.insert(0, item)
    write_json(pdir / "renders.json", renders[:100])
    return item
