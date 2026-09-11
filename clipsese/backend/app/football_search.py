import json
import re
import time
import unicodedata
import urllib.request
from difflib import SequenceMatcher

from .utils import project_dir, read_json

# Memoria NFL ligera. Primero usamos el directorio público de Sleeper y lo cacheamos
# en memoria del proceso. Si Sleeper no responde, esta lista cubre nombres fantasy/NFL
# comunes y, sobre todo, evita que la búsqueda dependa de que YouTube deletree perfecto.
_PLAYER_CACHE: list[str] | None = None
_PLAYER_CACHE_AT = 0.0
_PLAYER_CACHE_TTL = 6 * 60 * 60

_FALLBACK_PLAYERS = [
    "Patrick Mahomes", "Josh Allen", "Lamar Jackson", "Jalen Hurts", "Joe Burrow",
    "Justin Herbert", "Dak Prescott", "Kyler Murray", "Jared Goff", "Matthew Stafford",
    "Caleb Williams", "Jayden Daniels", "Drake Maye", "Bo Nix", "C.J. Stroud",
    "Bijan Robinson", "Saquon Barkley", "Jahmyr Gibbs", "Derrick Henry", "Christian McCaffrey",
    "De'Von Achane", "Chase Brown", "Omarion Hampton", "Ashton Jeanty", "Javonte Williams",
    "Quinshon Judkins", "David Montgomery", "D'Andre Swift", "Rico Dowdle", "James Cook",
    "Justin Jefferson", "Ja'Marr Chase", "CeeDee Lamb", "Amon-Ra St. Brown", "Nico Collins",
    "A.J. Brown", "DeVonta Smith", "Malik Nabers", "Mike Evans", "Davante Adams",
    "Marvin Harrison Jr.", "Jayden Reed", "Wan'Dale Robinson", "Michael Wilson", "Deebo Samuel",
    "George Kittle", "Trey McBride", "Brock Bowers", "Tucker Kraft", "T.J. Hockenson",
    "Sam LaPorta", "Mark Andrews", "Tyler Warren", "Chig Okonkwo", "Travis Kelce",
    "Rashee Rice", "Xavier Worthy", "Parker Washington", "Jameson Williams", "DJ Moore",
]

# Errores fonéticos que ya vimos en captions reales de ClipSese. Esto NO pretende
# reemplazar una transcripción; sólo normaliza términos inequívocos del dominio NFL.
_CORRECTIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(?:tocker\s*craf|tocker\s*craft|tuckercraf|tucker\s+craft)\b", re.I), "Tucker Kraft"),
    (re.compile(r"\bder\s+herny\b", re.I), "Derrick Henry"),
    (re.compile(r"\bpatri(?:ck)?\s+holmes\b", re.I), "Patrick Mahomes"),
    (re.compile(r"\bashton\s+gen(?:t|ti|ty)?\b", re.I), "Ashton Jeanty"),
    (re.compile(r"\bgeorge\s+ki(?:ro|lo|tle)\b", re.I), "George Kittle"),
    (re.compile(r"\bky\s+muray\b", re.I), "Kyler Murray"),
    (re.compile(r"\bmcbright\b", re.I), "McBride"),
    (re.compile(r"\btiden\b", re.I), "tight end"),
    (re.compile(r"\blos\s+bers\b", re.I), "los Bears"),
]


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9' -]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _norm(text))


def _correct_text(text: str) -> str:
    out = str(text or "")
    for pattern, replacement in _CORRECTIONS:
        out = pattern.sub(replacement, out)
    return out


def _load_players() -> list[str]:
    global _PLAYER_CACHE, _PLAYER_CACHE_AT
    now = time.time()
    if _PLAYER_CACHE is not None and now - _PLAYER_CACHE_AT < _PLAYER_CACHE_TTL:
        return _PLAYER_CACHE

    names: set[str] = set(_FALLBACK_PLAYERS)
    try:
        req = urllib.request.Request(
            "https://api.sleeper.app/v1/players/nfl",
            headers={"User-Agent": "ClipSese/0.4 (+private fantasy clip search)"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.load(resp)
        for p in data.values():
            if not isinstance(p, dict):
                continue
            # Mantener jugadores actuales/relevantes. Los sin estado explícito también entran.
            if p.get("active") is False:
                continue
            full = (p.get("full_name") or "").strip()
            if not full:
                first = (p.get("first_name") or "").strip()
                last = (p.get("last_name") or "").strip()
                full = f"{first} {last}".strip()
            if len(full) >= 4 and any(ch.isalpha() for ch in full):
                names.add(full)
    except Exception as e:
        print(f"[CLIPSESE] player memory fallback: {type(e).__name__}: {e}", flush=True)

    _PLAYER_CACHE = sorted(names)
    _PLAYER_CACHE_AT = now
    return _PLAYER_CACHE


def _player_candidates(query: str) -> list[tuple[float, str]]:
    q = _norm(query)
    if not q:
        return []
    q_compact = _compact(q)
    scored: list[tuple[float, str]] = []

    for full in _load_players():
        nf = _norm(full)
        parts = nf.split()
        if not parts:
            continue
        first, last = parts[0], parts[-1]
        score = 0.0
        if q == nf:
            score = 1.0
        elif q == last:
            score = 0.995
        elif q == first and len(first) >= 5:
            score = 0.88
        elif q in parts:
            score = 0.90
        elif len(q.split()) >= 2:
            score = SequenceMatcher(None, q_compact, _compact(nf)).ratio()
            if score < 0.80:
                score = 0.0
        elif len(q) >= 5:
            ratio = SequenceMatcher(None, q, last).ratio()
            if ratio >= 0.90:
                score = ratio * 0.92
        if score:
            scored.append((score, full))

    scored.sort(key=lambda x: (-x[0], len(x[1])))
    # Un apellido común puede devolver muchos jugadores. No necesitamos indexar media NFL
    # para cada tecla: con ocho candidatos se cubre la intención sin llenar de falsos positivos.
    return scored[:8]


def _segment_text(segment: dict) -> str:
    return _correct_text(str(segment.get("search_text") or segment.get("text") or ""))


def _visible_text(segment: dict) -> str:
    return _correct_text(str(segment.get("text") or ""))


def _ngrams(tokens: list[str], min_n: int = 1, max_n: int = 3):
    for n in range(min_n, min(max_n, len(tokens)) + 1):
        for i in range(0, len(tokens) - n + 1):
            yield tokens[i:i+n]


def _player_text_score(canonical: str, text: str) -> float:
    nt = _norm(_correct_text(text))
    if not nt:
        return 0.0
    nf = _norm(canonical)
    parts = nf.split()
    last = parts[-1]

    # Si la normalización de dominio ya recuperó el nombre, no hay nada que adivinar.
    if nf in nt:
        return 1.0
    tokens = nt.split()
    if last in tokens:
        return 0.97

    # Apellido aproximado, pero con umbral alto. Así "kraft" NO casa con "draft".
    last_best = max((SequenceMatcher(None, last, t).ratio() for t in tokens if len(t) >= 4), default=0.0)
    if last_best >= 0.88:
        return 0.90 + (last_best - 0.88) * 0.5

    # Los captions suelen pegar el nombre: "tockercraf". Comparamos el nombre completo
    # compacto contra grupos de 1-3 tokens; aquí sí permitimos más error porque dos nombres
    # juntos son mucho más discriminantes que un apellido aislado.
    target = _compact(nf)
    best_full = 0.0
    for gram in _ngrams(tokens, 1, 3):
        comp = _compact(" ".join(gram))
        if len(comp) < 6:
            continue
        ratio = SequenceMatcher(None, target, comp).ratio()
        if ratio > best_full:
            best_full = ratio
    if best_full >= 0.70:
        return 0.72 + (best_full - 0.70) * 0.75
    return 0.0


def _generic_score(query: str, text: str) -> float:
    q = _norm(query)
    t = _norm(_correct_text(text))
    if not q or not t:
        return 0.0
    if q in t:
        return 1.0
    qparts = q.split()
    tparts = t.split()

    if len(qparts) == 1:
        token = qparts[0]
        if len(token) < 4:
            return 0.0
        best = max((SequenceMatcher(None, token, x).ratio() for x in tparts if len(x) >= 4), default=0.0)
        return best if best >= 0.90 else 0.0

    target = _compact(q)
    best = 0.0
    for gram in _ngrams(tparts, max(1, len(qparts)-1), min(3, len(qparts)+1)):
        ratio = SequenceMatcher(None, target, _compact(" ".join(gram))).ratio()
        best = max(best, ratio)
    return best if best >= 0.86 else 0.0


def _window_for_hit(segments: list[dict], idx: int, max_len: float = 30.0) -> dict:
    hit = segments[idx]
    center = (float(hit.get("start", 0)) + float(hit.get("end", 0))) / 2
    start = max(0.0, center - 12.0)
    end = start + max_len
    texts = [_visible_text(s) for s in segments if float(s.get("end", 0)) >= start and float(s.get("start", 0)) <= end]
    return {"start": round(start, 3), "end": round(end, 3), "text": " ".join(texts).strip()}


def keyword_search(project_id: str, query: str, max_results: int = 8) -> list[dict]:
    tr = read_json(project_dir(project_id) / "transcript.json") or {}
    segments = tr.get("segments", [])
    if not segments:
        return []

    candidates = _player_candidates(query)
    # Si el apellido/nombre es inequívoco usamos memoria NFL. Si "Smith" devuelve media
    # plantilla, preferimos búsqueda textual estricta para no inventar de qué Smith hablaban.
    use_player_memory = bool(candidates) and not (len(candidates) >= 6 and len(_norm(query).split()) == 1)

    scored: list[tuple[float, int, str | None]] = []
    for i, s in enumerate(segments):
        text = _segment_text(s)
        if use_player_memory:
            best_score = 0.0
            best_name: str | None = None
            for candidate_score, canonical in candidates:
                hit = _player_text_score(canonical, text)
                # La confianza de resolución de la consulta modula ligeramente el resultado.
                hit *= 0.93 + 0.07 * candidate_score
                if hit > best_score:
                    best_score, best_name = hit, canonical
            if best_score >= 0.70:
                scored.append((best_score, i, best_name))
        else:
            hit = _generic_score(query, text)
            if hit:
                scored.append((hit, i, None))

    scored.sort(key=lambda x: (-x[0], float(segments[x[1]].get("start", 0))))
    hits: list[dict] = []
    used_starts: list[float] = []
    for score, idx, canonical in scored:
        win = _window_for_hit(segments, idx)
        if any(abs(win["start"] - old) < 8 for old in used_starts):
            continue
        if canonical and canonical not in win["text"]:
            # Ayuda visual: la UI deja claro qué jugador recuperó la memoria NFL aunque
            # YouTube lo haya escrito fonéticamente. No reescribimos el resto de la frase.
            win["text"] = f"[{canonical}] {win['text']}"
        win["score"] = round(min(1.0, score), 4)
        hits.append(win)
        used_starts.append(win["start"])
        if len(hits) >= max_results:
            break
    return hits


def theme_search(project_id: str, query: str, max_results: int = 8) -> list[dict]:
    # Para consultas temáticas que en realidad son nombres de jugador, usamos el buscador
    # especializado. Para el resto conservamos el buscador temático existente y sólo limpiamos
    # errores NFL inequívocos en el texto mostrado.
    candidates = _player_candidates(query)
    if candidates and len(_norm(query).split()) <= 3:
        hits = keyword_search(project_id, query, max_results)
        if hits:
            return hits

    from .transcribe import theme_search as legacy_theme_search
    hits = legacy_theme_search(project_id, query, max_results)
    for item in hits:
        item["text"] = _correct_text(item.get("text", ""))
    return hits
