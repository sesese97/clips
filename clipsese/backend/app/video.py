import base64
import os
import shutil
import sys
import uuid
from pathlib import Path

from .models import Crop, RenderRequest
from .utils import CommandError, ffprobe, project_dir, read_json, run, write_json

BGUTIL_SERVER = os.getenv("BGUTIL_SERVER", "/opt/bgutil-ytdlp-pot-provider/server")


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


def _youtube_cmd(
    url: str,
    out_tpl: str,
    *,
    format_selector: str,
    section: tuple[float, float] | None = None,
    use_pot: bool = True,
) -> list[str]:
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--no-playlist",
        "--force-ipv4",
        "--retries", "3",
        "--fragment-retries", "3",
        "--no-progress",
        "--js-runtimes", "deno:/usr/local/bin/deno",
        "--merge-output-format", "mp4",
        "-f", format_selector,
    ]

    if use_pot:
        cmd += [
            "--extractor-args", "youtube:player_client=mweb",
            "--extractor-args", f"youtubepot-bgutilscript:server_home={BGUTIL_SERVER}",
        ]

    cookies = _cookie_file()
    if cookies:
        cmd += ["--cookies", str(cookies)]

    if section is not None:
        start, end = section
        cmd += ["--download-sections", f"*{start:.3f}-{end:.3f}"]

    cmd += ["-o", out_tpl, url]
    return cmd


def _clean_partial_files(out_dir: Path, stem: str):
    for old in out_dir.glob(f"{stem}.*"):
        if old.is_file() and old.name.endswith((".part", ".ytdl")):
            try:
                old.unlink()
            except OSError:
                pass


def _pick_download(out_dir: Path, stem: str) -> Path:
    candidates = [
        p for p in out_dir.glob(f"{stem}.*")
        if p.is_file() and not p.name.endswith((".part", ".ytdl"))
    ]
    candidates = sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise RuntimeError("yt-dlp terminó sin crear un archivo de video.")
    return candidates[0]


def _download_youtube(
    url: str,
    out_dir: Path,
    stem: str,
    *,
    format_selector: str,
    section: tuple[float, float] | None = None,
    timeout: int = 1200,
) -> Path:
    out_tpl = str(out_dir / f"{stem}.%(ext)s")
    _clean_partial_files(out_dir, stem)

    attempts: list[tuple[str, bool, list[str]]] = [
        ("mweb+POT", True, []),
        ("default", False, []),
        ("web_embedded", False, ["--extractor-args", "youtube:player_client=web_embedded"]),
    ]

    last_error: Exception | None = None
    for label, use_pot, extra in attempts:
        cmd = _youtube_cmd(
            url,
            out_tpl,
            format_selector=format_selector,
            section=section,
            use_pot=use_pot,
        )
        if extra:
            cmd = cmd[:-3] + extra + cmd[-3:]
        try:
            print(f"[CLIPSESE] YouTube attempt: {label}", flush=True)
            run(cmd, timeout=timeout)
            return _pick_download(out_dir, stem)
        except CommandError as e:
            last_error = e
            low = str(e).lower()
            if not any(x in low for x in ("sign in to confirm", "not a bot", "login_required", "403", "429", "po token")):
                if "javascript runtime" in low or "js challenge" in low:
                    raise RuntimeError("El runtime de YouTube no quedó disponible en el contenedor.") from e
                raise RuntimeError(f"YouTube no pudo importarse: {str(e)[-1800:]}") from e

    raise RuntimeError(
        "YouTube sigue rechazando la IP de Railway incluso con PO Token. "
        "ClipSese ya probó POT y clientes alternativos. En ese caso la alternativa estable "
        "es usar Archivo original o añadir cookies de una cuenta dedicada."
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
        "source_kind": "upload",
        "source_file": dest.name,
        "preview_file": "preview.mp4",
        "metadata": meta,
        "transcript_status": "not_started",
    }
    write_json(pdir / "project.json", payload)
    return payload


def ingest_youtube(project_id: str, url: str) -> dict:
    """Prepara sólo un proxy ligero. El master de YouTube se baja únicamente al exportar."""
    pdir = project_dir(project_id)
    try:
        _set_import_state(project_id, status="importing", stage="connecting", error="")
        _set_import_state(project_id, stage="preparing_proxy")
        preview_source = _download_youtube(
            url,
            pdir,
            "preview_source",
            format_selector=(
                "b[ext=mp4][vcodec^=avc1][height<=480]/"
                "b[ext=mp4][height<=480]/b[height<=480]"
            ),
            timeout=900,
        )

        meta = ffprobe(preview_source)
        browser_ready = (
            preview_source.suffix.lower() == ".mp4"
            and meta.get("video_codec") == "h264"
            and meta.get("audio_codec") in {"aac", None}
        )

        if browser_ready:
            preview_name = preview_source.name
        else:
            _set_import_state(project_id, stage="preparing_preview")
            preview_path = pdir / "preview.mp4"
            _make_proxy(preview_source, preview_path)
            preview_name = preview_path.name

        payload = {
            "id": project_id,
            "status": "ready",
            "import_stage": "ready",
            "import_error": "",
            "original_name": "YouTube",
            "source_kind": "youtube",
            "source_url": url,
            "source_file": "",
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
        return payload


def _make_proxy(src: Path, dest: Path):
    run([
        "ffmpeg", "-y", "-threads", "2", "-i", str(src),
        "-vf", "scale='min(960,iw)':-2,fps=30,setsar=1",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28", "-threads", "2",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
        str(dest)
    ], timeout=1800)


def source_path(project_id: str) -> Path:
    pdir = project_dir(project_id)
    pj = read_json(pdir / "project.json") or {}
    name = pj.get("source_file") or pj.get("preview_file")
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
    dest = _download_youtube(
        url,
        pdir,
        f"media_{mid}",
        format_selector="b[height<=1080]/bv*[height<=1080]+ba/b",
        timeout=600,
    )
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
        f"crop={width}:{height},setsar=1[{out_label}]"
    )


def _media_filter(label: str, width: int, height: int, out_label: str, req: RenderRequest) -> str:
    """Ajusta multimedia sin deformarla: encajar/llenar + zoom + paneo."""
    aspect = width / height
    z = req.media_zoom
    px = (req.media_x + 1.0) / 2.0
    py = (req.media_y + 1.0) / 2.0
    if req.media_fit == "cover":
        scale = (
            f"scale=w='if(gt(a,{aspect:.8f}),-2,{width}*{z:.6f})':"
            f"h='if(gt(a,{aspect:.8f}),{height}*{z:.6f},-2)'"
        )
    else:
        scale = (
            f"scale=w='if(gt(a,{aspect:.8f}),{width}*{z:.6f},-2)':"
            f"h='if(gt(a,{aspect:.8f}),-2,{height}*{z:.6f})'"
        )
    return (
        f"[{label}]{scale},setsar=1,"
        f"pad=w='max(iw,{width})':h='max(ih,{height})':"
        f"x='(ow-iw)*{px:.6f}':y='(oh-ih)*{py:.6f}':color=black,"
        f"crop={width}:{height}:"
        f"x='max(0,(iw-{width})*{px:.6f})':y='max(0,(ih-{height})*{py:.6f})',"
        f"setsar=1[{out_label}]"
    )


def _render_source(project_id: str, req: RenderRequest, render_id: str) -> tuple[Path, float, Path | None]:
    pdir = project_dir(project_id)
    pj = read_json(pdir / "project.json") or {}

    if pj.get("source_kind") == "youtube" and pj.get("source_url"):
        seg_start = max(0.0, req.start - 2.0)
        seg_end = req.end + 2.0
        segment = _download_youtube(
            pj["source_url"],
            pdir,
            f"master_{render_id}",
            format_selector="bv*[vcodec!^=av01]+ba/bv*+ba/b",
            section=(seg_start, seg_end),
            timeout=900,
        )
        return segment, max(0.0, req.start - seg_start), segment

    src = source_path(project_id)
    return src, req.start, None


def render_clip(project_id: str, req: RenderRequest) -> dict:
    if req.end <= req.start:
        raise ValueError("El final debe ser posterior al inicio")
    if req.end - req.start > 60.001:
        raise ValueError("Los clips no pueden exceder 60 segundos")
    if req.layout in {"two_cameras", "two_media"} and req.camera2 is None:
        raise ValueError("El layout requiere cámara 2")
    if req.layout in {"one_media", "two_media"} and not req.media_id and req.content is None:
        raise ValueError("El layout requiere multimedia externa o un recorte de contenido")

    pdir = project_dir(project_id)
    render_id = uuid.uuid4().hex[:12]
    out = pdir / f"clip_{render_id}.mp4"
    duration = req.end - req.start
    src, local_seek, temp_master = _render_source(project_id, req, render_id)

    try:
        cmd = ["ffmpeg", "-y", "-threads", "2", "-ss", f"{local_seek:.3f}", "-t", f"{duration:.3f}", "-i", str(src)]
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
                filters.append(_media_filter("1:v", 1080, 1200, "media", req))
            else:
                filters.append(_crop_filter("s1", req.content, 1080, 1200, "media"))
            filters.append("[cam1][media]vstack=inputs=2[stacked]")
        elif req.layout == "two_cameras":
            filters.append(_crop_filter("s1", req.camera2, 1080, 960, "cam2"))
            filters.append("[cam1][cam2]vstack=inputs=2[stacked]")
        else:
            filters.append(_crop_filter("s1", req.camera2, 540, 720, "cam2"))
            filters.append("[cam1][cam2]hstack=inputs=2[top]")
            if media_item:
                filters.append(_media_filter("1:v", 1080, 1200, "media", req))
            else:
                filters.append(_crop_filter("s2", req.content, 1080, 1200, "media"))
            filters.append("[top][media]vstack=inputs=2[stacked]")

        # hstack/vstack puede heredar una tasa absurda de una multimedia externa (vimos 120 fps
        # en un export de iPhone aunque la fuente principal era 60). Safari/iOS puede abrir el MP4
        # pero negarse a reproducirlo. El archivo final queda deliberadamente CFR 60, H.264 High
        # Level 4.2 y tag avc1: máxima compatibilidad con iPhone/TikTok/Shorts sin perder 60 fps.
        filters.append("[stacked]fps=60,format=yuv420p,setsar=1[outv]")

        cmd += [
            "-filter_complex_threads", "1",
            "-filter_complex", ";".join(filters),
            "-map", "[outv]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "17",
            "-profile:v", "high", "-level:v", "4.2", "-tag:v", "avc1",
            "-threads", "2", "-x264-params", "threads=2:lookahead_threads=1",
            "-pix_fmt", "yuv420p", "-fps_mode", "cfr",
            "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
            "-movflags", "+faststart", "-shortest", str(out)
        ]
        try:
            run(cmd, timeout=1800)
        except CommandError as e:
            if out.exists():
                try:
                    out.unlink()
                except OSError:
                    pass
            print(f"[CLIPSESE] ffmpeg render failed: {str(e)[-1800:]}", flush=True)
            raise RuntimeError(
                "No se pudo terminar el render en el servidor. ClipSese ya descargó el tramo en máxima calidad, "
                "pero FFmpeg se quedó sin recursos o falló al codificar. Intenta exportar nuevamente."
            ) from e

        info = ffprobe(out)
        # No registramos un export que el navegador móvil vaya a rechazar otra vez.
        fps_text = str(info.get("fps") or info.get("r_frame_rate") or "")
        print(f"[CLIPSESE] render ready: {out.name} {info.get('width')}x{info.get('height')} fps={fps_text} codec={info.get('video_codec')}", flush=True)
        item = {"id": render_id, "file": out.name, "metadata": info, "start": req.start, "end": req.end, "layout": req.layout}
        renders = read_json(pdir / "renders.json", []) or []
        renders.insert(0, item)
        write_json(pdir / "renders.json", renders[:100])
        return item
    finally:
        if temp_master and temp_master.exists():
            try:
                temp_master.unlink()
            except OSError:
                pass
