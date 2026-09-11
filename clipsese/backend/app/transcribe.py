import json
import os
import re
import sys
from pathlib import Path
from threading import Lock

from .utils import CommandError, project_dir, read_json, run, write_json
from .video import source_path

_model = None
_model_lock = Lock()
BGUTIL_SERVER = os.getenv("BGUTIL_SERVER", "/opt/bgutil-ytdlp-pot-provider/server")


def _save_project_transcript(project_id: str, segments: list[dict], *, language: str = "es", source: str = "unknown"):
    pdir = project_dir(project_id)
    write_json(pdir / "transcript.json", {"language": language, "source": source, "segments": segments})
    project = read_json(pdir / "project.json") or {"id": project_id}
    project["transcript_status"] = "ready"
    project["transcript_source"] = source
    project["transcript_segments"] = len(segments)
    project.pop("transcript_error", None)
    project.pop("transcript_hint", None)
    write_json(pdir / "project.json", project)


def _parse_json3(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out: list[dict] = []
    last_text = ""
    for ev in data.get("events", []):
        segs = ev.get("segs") or []
        text = "".join(str(s.get("utf8") or "") for s in segs)
        text = re.sub(r"\s+", " ", text.replace("\n", " ")).strip()
        if not text or text == last_text:
            continue
        start = float(ev.get("tStartMs") or 0) / 1000.0
        dur = float(ev.get("dDurationMs") or 0) / 1000.0
        end = start + (dur if dur > 0 else 2.5)
        out.append({"start": start, "end": end, "text": text, "words": []})
        last_text = text
    return out


def prepare_youtube_transcript(project_id: str):
    """Intenta preparar la búsqueda usando subtítulos de YouTube, sin ejecutar Whisper."""
    pdir = project_dir(project_id)
    project = read_json(pdir / "project.json") or {}
    url = project.get("source_url")
    if not url:
        return False

    project["transcript_status"] = "processing"
    project["transcript_source"] = "youtube_captions"
    project["transcript_hint"] = "Preparando subtítulos de YouTube para búsqueda…"
    write_json(pdir / "project.json", project)

    # Elimina restos de intentos previos.
    for old in pdir.glob("captions*.json3"):
        try:
            old.unlink()
        except OSError:
            pass

    out_tpl = str(pdir / "captions.%(ext)s")
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--no-playlist",
        "--force-ipv4",
        "--skip-download",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs", "es.*,es,en.*",
        "--sub-format", "json3",
        "--js-runtimes", "deno:/usr/local/bin/deno",
        "--extractor-args", "youtube:player_client=mweb",
        "--extractor-args", f"youtubepot-bgutilscript:server_home={BGUTIL_SERVER}",
        "-o", out_tpl,
        url,
    ]

    try:
        run(cmd, timeout=180)
        files = list(pdir.glob("captions*.json3"))
        # Preferencia: español manual/auto, luego inglés si fuera lo único disponible.
        files.sort(key=lambda p: (0 if ".es" in p.name.lower() else 1, len(p.name)))
        for path in files:
            segments = _parse_json3(path)
            if segments:
                lang = "es" if ".es" in path.name.lower() else "en"
                _save_project_transcript(project_id, segments, language=lang, source="youtube_captions")
                print(f"[CLIPSESE] YouTube captions ready: {len(segments)} segments from {path.name}", flush=True)
                return True
        raise RuntimeError("YouTube no entregó subtítulos utilizables para este video")
    except Exception as e:
        # No tratamos esto como error del proyecto. El usuario todavía puede usar Whisper.
        project = read_json(pdir / "project.json") or project
        project["transcript_status"] = "not_started"
        project["transcript_source"] = "none"
        project["transcript_hint"] = "YouTube no entregó subtítulos. Usa “Analizar audio” para crear la búsqueda con Whisper."
        project["transcript_error"] = str(e)[-1200:]
        write_json(pdir / "project.json", project)
        print(f"[CLIPSESE] captions unavailable: {type(e).__name__}: {e}", flush=True)
        return False


def transcribe_project(project_id: str):
    pdir = project_dir(project_id)
    project = read_json(pdir / "project.json") or {}
    project["transcript_status"] = "processing"
    project["transcript_source"] = "whisper"
    project["transcript_hint"] = "Analizando el audio para habilitar la búsqueda…"
    write_json(pdir / "project.json", project)
    try:
        from faster_whisper import WhisperModel
        global _model
        with _model_lock:
            if _model is None:
                model_name = os.getenv("WHISPER_MODEL", "base")
                device = os.getenv("WHISPER_DEVICE", "cpu")
                compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
                _model = WhisperModel(model_name, device=device, compute_type=compute_type)
        segments, info = _model.transcribe(
            str(source_path(project_id)), language="es", vad_filter=True, word_timestamps=True,
            initial_prompt="NFL fantasy football. Nombres de jugadores, equipos, rookies y estadísticas."
        )
        out = []
        for s in segments:
            words = []
            if s.words:
                for w in s.words:
                    words.append({"start": float(w.start or s.start), "end": float(w.end or s.end), "word": w.word})
            out.append({"start": float(s.start), "end": float(s.end), "text": s.text.strip(), "words": words})
        _save_project_transcript(
            project_id,
            out,
            language=getattr(info, "language", "es"),
            source="whisper",
        )
    except Exception as e:
        project = read_json(pdir / "project.json") or project
        project["transcript_status"] = "error"
        project["transcript_error"] = str(e)
        project["transcript_hint"] = "No se pudo analizar el audio. Puedes seguir usando búsqueda por tiempo."
        write_json(pdir / "project.json", project)


def _norm(text: str) -> str:
    import unicodedata
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9' -]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _window_for_hit(segments: list[dict], idx: int, max_len=30.0) -> dict:
    hit = segments[idx]
    center = (hit["start"] + hit["end"]) / 2
    start = max(0.0, center - 12.0)
    end = start + max_len
    texts = []
    for s in segments:
        if s["end"] >= start and s["start"] <= end:
            texts.append(s["text"])
    return {"start": round(start, 3), "end": round(end, 3), "text": " ".join(texts).strip()}


def keyword_search(project_id: str, query: str, max_results=8) -> list[dict]:
    tr = read_json(project_dir(project_id) / "transcript.json") or {}
    segments = tr.get("segments", [])
    nq = _norm(query)
    hits = []
    last_start = -999
    for i, s in enumerate(segments):
        if nq in _norm(s["text"]):
            win = _window_for_hit(segments, i)
            if win["start"] - last_start < 8:
                continue
            win["score"] = 1.0
            hits.append(win)
            last_start = win["start"]
            if len(hits) >= max_results:
                break
    return hits


def _make_windows(segments: list[dict], width=26.0, stride=16.0) -> list[dict]:
    if not segments:
        return []
    end_all = segments[-1]["end"]
    windows = []
    t = 0.0
    while t < end_all:
        e = t + width
        texts = [s["text"] for s in segments if s["end"] >= t and s["start"] <= e]
        if texts:
            windows.append({"start": t, "end": min(e, end_all), "text": " ".join(texts).strip()})
        t += stride
    return windows


def _fallback_score(query: str, text: str) -> float:
    q = set(_norm(query).split())
    t = set(_norm(text).split())
    if not q or not t:
        return 0.0
    return len(q & t) / max(1, len(q))


def theme_search(project_id: str, query: str, max_results=8) -> list[dict]:
    """Búsqueda temática ligera para Railway pequeño."""
    tr = read_json(project_dir(project_id) / "transcript.json") or {}
    windows = _make_windows(tr.get("segments", []))
    scored = []
    for w in windows:
        item = dict(w)
        item["score"] = round(_fallback_score(query, w["text"]), 4)
        scored.append(item)
    return [x for x in sorted(scored, key=lambda x: x["score"], reverse=True) if x["score"] > 0][:max_results]
