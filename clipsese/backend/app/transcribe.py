import math
import re
from pathlib import Path
from threading import Lock

import numpy as np

from .utils import project_dir, read_json, write_json
from .video import source_path

_model = None
_embedder = None
_model_lock = Lock()
_embed_lock = Lock()


def transcribe_project(project_id: str):
    pdir = project_dir(project_id)
    project = read_json(pdir / "project.json") or {}
    project["transcript_status"] = "processing"
    write_json(pdir / "project.json", project)
    try:
        from faster_whisper import WhisperModel
        global _model
        with _model_lock:
            if _model is None:
                import os
                model_name = os.getenv("WHISPER_MODEL", "small")
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
        write_json(pdir / "transcript.json", {"language": getattr(info, "language", "es"), "segments": out})
        project = read_json(pdir / "project.json") or project
        project["transcript_status"] = "ready"
        project["transcript_segments"] = len(out)
        write_json(pdir / "project.json", project)
    except Exception as e:
        project = read_json(pdir / "project.json") or project
        project["transcript_status"] = "error"
        project["transcript_error"] = str(e)
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
    texts=[]
    for s in segments:
        if s["end"] >= start and s["start"] <= end:
            texts.append(s["text"])
    return {"start": round(start, 3), "end": round(end, 3), "text": " ".join(texts).strip()}


def keyword_search(project_id: str, query: str, max_results=8) -> list[dict]:
    tr = read_json(project_dir(project_id) / "transcript.json") or {}
    segments = tr.get("segments", [])
    nq = _norm(query)
    hits=[]
    last_start=-999
    for i,s in enumerate(segments):
        if nq in _norm(s["text"]):
            win=_window_for_hit(segments, i)
            if win["start"] - last_start < 8:
                continue
            win["score"] = 1.0
            hits.append(win)
            last_start=win["start"]
            if len(hits) >= max_results:
                break
    return hits


def _make_windows(segments: list[dict], width=26.0, stride=16.0) -> list[dict]:
    if not segments:
        return []
    end_all = segments[-1]["end"]
    windows=[]
    t=0.0
    while t < end_all:
        e=t+width
        texts=[s["text"] for s in segments if s["end"] >= t and s["start"] <= e]
        if texts:
            windows.append({"start":t, "end":min(e,end_all), "text":" ".join(texts).strip()})
        t += stride
    return windows


def _fallback_score(query: str, text: str) -> float:
    q=set(_norm(query).split())
    t=set(_norm(text).split())
    if not q or not t:
        return 0.0
    return len(q & t) / max(1, len(q))


def theme_search(project_id: str, query: str, max_results=8) -> list[dict]:
    tr = read_json(project_dir(project_id) / "transcript.json") or {}
    windows=_make_windows(tr.get("segments", []))
    if not windows:
        return []
    try:
        from sentence_transformers import SentenceTransformer
        global _embedder
        with _embed_lock:
            if _embedder is None:
                _embedder = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        texts=[w["text"] for w in windows]
        emb=_embedder.encode([query]+texts, normalize_embeddings=True)
        q=emb[0]
        scores=np.dot(emb[1:], q)
        order=np.argsort(-scores)[:max_results]
        results=[]
        for idx in order:
            w=dict(windows[int(idx)])
            w["score"]=round(float(scores[int(idx)]), 4)
            results.append(w)
        return results
    except Exception:
        scored=[]
        for w in windows:
            item=dict(w); item["score"]=_fallback_score(query,w["text"]); scored.append(item)
        return sorted(scored,key=lambda x:x["score"], reverse=True)[:max_results]
