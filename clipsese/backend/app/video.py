import json
import math
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from .models import Crop, RenderRequest
from .utils import ffprobe, project_dir, read_json, run, write_json


def _download_with_ytdlp(url: str, out_dir: Path, stem: str) -> Path:
    out_tpl = str(out_dir / f"{stem}.%(ext)s")
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--no-playlist",
        "--merge-output-format", "mp4",
        "-f", "bv*[vcodec^=avc1]+ba[acodec^=mp4a]/b[ext=mp4]/best",
        "-o", out_tpl,
        url,
    ]
    run(cmd)
    candidates = sorted(out_dir.glob(f"{stem}.*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise RuntimeError("No se pudo descargar el video.")
    return candidates[0]


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
    source = _download_with_ytdlp(url, pdir, "source")
    meta = ffprobe(source)
    _make_proxy(source, pdir / "preview.mp4")
    payload = {
        "id": project_id,
        "status": "ready",
        "original_name": "YouTube",
        "source_url": url,
        "source_file": source.name,
        "preview_file": "preview.mp4",
        "metadata": meta,
        "transcript_status": "not_started",
    }
    write_json(pdir / "project.json", payload)
    return payload


def _make_proxy(src: Path, dest: Path):
    run([
        "ffmpeg", "-y", "-i", str(src),
        "-vf", "scale='min(1280,iw)':-2",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
        str(dest)
    ])


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
    # Crop coordinates are normalized to the source frame. Scale keeps aspect ratio, then center-crops to the target box.
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
    # Split the source video so each crop gets an independent input stream.
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

    else:  # two_media
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
        "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-profile:v", "high",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k",
        "-movflags", "+faststart", "-shortest", str(out)
    ]
    run(cmd)
    info = ffprobe(out)
    item = {"id": render_id, "file": out.name, "metadata": info, "start": req.start, "end": req.end, "layout": req.layout}
    renders = read_json(pdir / "renders.json", []) or []
    renders.insert(0, item)
    write_json(pdir / "renders.json", renders[:100])
    return item
