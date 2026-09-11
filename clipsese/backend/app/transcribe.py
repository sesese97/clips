import json
import os
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path
from threading import Lock

from .utils import project_dir, read_json, run, write_json
from .video import _cookie_file, source_path

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


def _caption_cmd(url: str, out_tpl: str, *, mode: str) -> list[str]:
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--no-playlist",
        "--force-ipv4",
        "--skip-download",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs", "es.*,es,en.*,en",
        "--sub-format", "json3",
        "--js-runtimes", "deno:/usr/local/bin/deno",
    ]

    if mode == "mweb_pot":
        cmd += [
            "--extractor-args", "youtube:player_client=mweb",
            "--extractor-args", f"youtubepot-bgutilscript:server_home={BGUTIL_SERVER}",
        ]
    elif mode == "web_embedded":
        cmd += ["--extractor-args", "youtube:player_client=web_embedded"]

    cookies = _cookie_file()
    if cookies:
        cmd += ["--cookies", str(cookies)]

    cmd += ["-o", out_tpl, url]
    return cmd


def _load_caption_files(project_id: str) -> bool:
    pdir = project_dir(project_id)
    files = list(pdir.glob("captions*.json3"))
    # Español primero; si el video sólo ofrece inglés, al menos la búsqueda sigue funcionando.
    files.sort(key=lambda p: (0 if ".es" in p.name.lower() else 1, len(p.name)))
    for path in files:
        segments = _parse_json3(path)
        if segments:
            lang = "es" if ".es" in path.name.lower() else "en"
            _save_project_transcript(project_id, segments, language=lang, source="youtube_captions")
            print(f"[CLIPSESE] YouTube captions ready: {len(segments)} segments from {path.name}", flush=True)
            return True
    return False


def prepare_youtube_transcript(project_id: str):
    """Prepara la búsqueda: captions de YouTube primero y Whisper automático como respaldo."""
    pdir = project_dir(project_id)
    project = read_json(pdir / "project.json") or {}
    url = project.get("source_url")
    if not url:
        return False

    project["transcript_status"] = "processing"
    project["transcript_source"] = "youtube_captions"
    project["transcript_hint"] = "Preparando subtítulos de YouTube para búsqueda…"
    write_json(pdir / "project.json", project)

    attempts = ["mweb_pot", "default", "web_embedded"]
    errors: list[str] = []

    for mode in attempts:
        for old in pdir.glob("captions*.json3"):
            try:
                old.unlink()
            except OSError:
                pass

        out_tpl = str(pdir / "captions.%(ext)s")
        try:
            print(f"[CLIPSESE] captions attempt: {mode}", flush=True)
            run(_caption_cmd(url, out_tpl, mode=mode), timeout=180)
            if _load_caption_files(project_id):
                return True
            errors.append(f"{mode}: sin archivos de subtítulos utilizables")
        except Exception as e:
            errors.append(f"{mode}: {str(e)[-500:]}")

    # Los captions pueden no existir, estar desactivados o quedar bloqueados por YouTube.
    # Para el usuario la búsqueda debe funcionar de todos modos, así que hacemos Whisper
    # automáticamente sobre el proxy ligero ya descargado en vez de exigir otro botón.
    project = read_json(pdir / "project.json") or project
    project["transcript_status"] = "processing"
    project["transcript_source"] = "whisper"
    project["transcript_hint"] = "YouTube no entregó subtítulos; analizando el audio automáticamente para habilitar la búsqueda…"
    project["transcript_error"] = " | ".join(errors)[-1600:]
    write_json(pdir / "project.json", project)
    print("[CLIPSESE] captions unavailable; falling back to Whisper automatically", flush=True)

    transcribe_project(project_id)
    final = read_json(pdir / "project.json") or {}
    return final.get("transcript_status") == "ready"


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
            str(source_path(project_id)),
            language="es",
            vad_filter=True,
            word_timestamps=True,
            beam_size=3,
            initial_prompt=(
                "NFL fantasy football. Nombres propios de jugadores, apellidos, equipos, rookies, "
                "estadísticas, sleepers, waiver, trade, running backs, wide receivers, quarterbacks "
                "y tight ends. Conserva los nombres propios aunque estén en inglés."
            ),
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
        print(f"[CLIPSESE] Whisper ERROR: {type(e).__name__}: {e}", flush=True)


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


def _token_similarity(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if len(a) < 4 or len(b) < 4:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _fuzzy_query_score(query: str, text: str) -> float:
    nq = _norm(query)
    nt = _norm(text)
    if not nq or not nt:
        return 0.0
    if nq in nt:
        return 1.0

    q_tokens = [x for x in nq.split() if x]
    t_tokens = [x for x in nt.split() if x]
    if not q_tokens or not t_tokens:
        return 0.0

    per_token = []
    for q in q_tokens:
        per_token.append(max((_token_similarity(q, t) for t in t_tokens), default=0.0))
    return sum(per_token) / len(per_token)


def keyword_search(project_id: str, query: str, max_results=8) -> list[dict]:
    """Busca nombres/palabras con coincidencia exacta y tolerancia a errores de subtitulado."""
    tr = read_json(project_dir(project_id) / "transcript.json") or {}
    segments = tr.get("segments", [])
    scored_hits: list[tuple[float, int]] = []

    for i, s in enumerate(segments):
        score = _fuzzy_query_score(query, s.get("text", ""))
        # 0.80 tolera cosas como Javonte/Javonté o pequeños errores del ASR,
        # sin convertir cualquier palabra vagamente parecida en un resultado.
        if score >= 0.80:
            scored_hits.append((score, i))

    # Primero mejor coincidencia, luego tiempo. Al construir ventanas eliminamos duplicados cercanos.
    scored_hits.sort(key=lambda x: (-x[0], segments[x[1]].get("start", 0)))
    hits = []
    used_starts: list[float] = []
    for score, i in scored_hits:
        win = _window_for_hit(segments, i)
        if any(abs(win["start"] - s) < 8 for s in used_starts):
            continue
        win["score"] = round(score, 4)
        hits.append(win)
        used_starts.append(win["start"])
        if len(hits) >= max_results:
            break

    return sorted(hits, key=lambda x: x["start"])


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


_STOPWORDS = {
    "a", "al", "algo", "con", "como", "cuando", "de", "del", "el", "ella", "en", "es", "esta", "este",
    "hay", "la", "las", "lo", "los", "me", "mi", "para", "por", "que", "se", "si", "son", "su", "sus",
    "un", "una", "uno", "unos", "unas", "y", "ya", "sobre", "habla", "hablan", "hablando", "tema",
}


def _theme_score(query: str, text: str) -> float:
    q_tokens = [x for x in _norm(query).split() if x not in _STOPWORDS and len(x) > 2]
    t_tokens = [x for x in _norm(text).split() if x not in _STOPWORDS and len(x) > 2]
    if not q_tokens or not t_tokens:
        return 0.0

    scores = []
    for q in q_tokens:
        scores.append(max((_token_similarity(q, t) for t in t_tokens), default=0.0))

    strong = [s for s in scores if s >= 0.78]
    if not strong:
        return 0.0
    coverage = len(strong) / len(q_tokens)
    quality = sum(strong) / len(strong)
    return coverage * 0.7 + quality * 0.3


def theme_search(project_id: str, query: str, max_results=8) -> list[dict]:
    """Búsqueda temática ligera: ventanas de 26 s + coincidencia tolerante de conceptos/palabras."""
    tr = read_json(project_dir(project_id) / "transcript.json") or {}
    windows = _make_windows(tr.get("segments", []))
    scored = []
    for w in windows:
        score = _theme_score(query, w["text"])
        if score <= 0:
            continue
        item = dict(w)
        item["score"] = round(score, 4)
        scored.append(item)
    return sorted(scored, key=lambda x: x["score"], reverse=True)[:max_results]
