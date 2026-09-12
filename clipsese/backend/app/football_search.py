import json
import re
import time
import unicodedata
import urllib.request
from difflib import SequenceMatcher
from functools import lru_cache

from .utils import project_dir, read_json

_PLAYER_CACHE: list[dict] | None = None
_PLAYER_CACHE_AT = 0.0
_PLAYER_CACHE_TTL = 6 * 60 * 60

# Respaldo si Sleeper no responde. La fuente normal es su directorio completo de jugadores NFL.
_FALLBACK_PLAYERS = [
    ("Patrick Mahomes","QB"),("Josh Allen","QB"),("Lamar Jackson","QB"),("Jalen Hurts","QB"),("Joe Burrow","QB"),
    ("Justin Herbert","QB"),("Dak Prescott","QB"),("Kyler Murray","QB"),("Jared Goff","QB"),("Matthew Stafford","QB"),
    ("Caleb Williams","QB"),("Jayden Daniels","QB"),("Drake Maye","QB"),("Bo Nix","QB"),("C.J. Stroud","QB"),("Jaxson Dart","QB"),
    ("Bijan Robinson","RB"),("Saquon Barkley","RB"),("Jahmyr Gibbs","RB"),("Derrick Henry","RB"),("Christian McCaffrey","RB"),
    ("De'Von Achane","RB"),("Chase Brown","RB"),("Omarion Hampton","RB"),("Ashton Jeanty","RB"),("Javonte Williams","RB"),
    ("Quinshon Judkins","RB"),("David Montgomery","RB"),("D'Andre Swift","RB"),("Rico Dowdle","RB"),("James Cook","RB"),("Jonathan Brooks","RB"),
    ("Justin Jefferson","WR"),("Ja'Marr Chase","WR"),("CeeDee Lamb","WR"),("Amon-Ra St. Brown","WR"),("Nico Collins","WR"),
    ("A.J. Brown","WR"),("DeVonta Smith","WR"),("Malik Nabers","WR"),("Mike Evans","WR"),("Davante Adams","WR"),
    ("Marvin Harrison Jr.","WR"),("Jayden Reed","WR"),("Wan'Dale Robinson","WR"),("Michael Wilson","WR"),("Deebo Samuel","WR"),
    ("Rashee Rice","WR"),("Xavier Worthy","WR"),("Parker Washington","WR"),("Jameson Williams","WR"),("DJ Moore","WR"),
    ("George Kittle","TE"),("Trey McBride","TE"),("Brock Bowers","TE"),("Tucker Kraft","TE"),("T.J. Hockenson","TE"),
    ("Sam LaPorta","TE"),("Mark Andrews","TE"),("Tyler Warren","TE"),("Chig Okonkwo","TE"),("Travis Kelce","TE"),
]

# Correcciones de ASR que ya vimos en videos reales. Se aplican antes del fuzzy dinámico.
# Aquí sí conviene ser explícitos con errores muy destructivos: son frases inequívocas en NFL.
_KNOWN_CORRECTIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(?:tocker\s*craf|tocker\s*craft|tuckercraf|tucker\s+craft)\b", re.I), "Tucker Kraft"),
    (re.compile(r"\bder\s+herny\b", re.I), "Derrick Henry"),
    (re.compile(r"\bpatri(?:ck)?\s+(?:holmes|moles?|homes)\b", re.I), "Patrick Mahomes"),
    (re.compile(r"\b(?:duck|dac|doc)\s+prescott\b", re.I), "Dak Prescott"),
    (re.compile(r"\b(?:jackson|japson|japsen|jaxon)\s+(?:dark|dar|dart)\b", re.I), "Jaxson Dart"),
    (re.compile(r"\bjonathan\s+(?:bx|bex|brok|brooks?)\b", re.I), "Jonathan Brooks"),
    (re.compile(r"\b(?:ashton|aston)\s+(?:gen|gent|genti|genty|jenti)\b", re.I), "Ashton Jeanty"),
    (re.compile(r"\b(?:yabonte|jabonte|javonte)\s+williams\b", re.I), "Javonte Williams"),
    (re.compile(r"\brico\s+(?:dow|dau|dowl|dowdel)\b", re.I), "Rico Dowdle"),
    (re.compile(r"\bgeorge\s+ki(?:ro|lo|tle)\b", re.I), "George Kittle"),
    (re.compile(r"\bky\s+muray\b", re.I), "Kyler Murray"),
    (re.compile(r"\bmalik\s+neighbors?\b", re.I), "Malik Nabers"),
    (re.compile(r"\b(?:mcbright|mc bride)\b", re.I), "McBride"),
    (re.compile(r"\b(?:tiden|tide\s+end|tighten)\b", re.I), "tight end"),
    (re.compile(r"\bwhite\s+receivers?\b", re.I), lambda m: "wide receiver" + ("s" if m.group(0).lower().endswith("s") else "")),
    (re.compile(r"\b(?:corback|coreback|quaterback)\b", re.I), "quarterback"),
    (re.compile(r"\b(?:sliper|sleepar|slipper)\b", re.I), "sleeper"),
    (re.compile(r"\b(?:runing|runnin)\s+back\b", re.I), "running back"),
    (re.compile(r"\blos\s+bers\b", re.I), "los Bears"),
]

_PLAYER_ALIASES: dict[str, tuple[str, ...]] = {
    "Tucker Kraft": ("tockercraf", "tocker craf", "tucker craft"),
    "Derrick Henry": ("der herny",),
    "Patrick Mahomes": ("patri holmes", "patrick holmes", "patrick mole", "patrick moles"),
    "Dak Prescott": ("duck prescott", "doc prescott"),
    "Jaxson Dart": ("jackson dark", "japson dar", "jackson dar"),
    "Jonathan Brooks": ("jonathan bx", "jonathan bex"),
    "Ashton Jeanty": ("aston genti", "ashton gen", "ashton gent", "ashton genti"),
    "Javonte Williams": ("yabonte williams", "jabonte williams"),
    "George Kittle": ("george kiro", "george kilo"),
    "Trey McBride": ("mcbright",),
    "Kyler Murray": ("ky muray",),
    "Malik Nabers": ("malik neighbors", "malik neighbor"),
    "Deebo Samuel": ("dove", "divo", "dibo", "debo"),
}

_STOP = {
    "que","de","la","el","los","las","un","una","y","o","en","es","se","me","te","lo","por","para","con","como","pero","si","no","este","esta","muy","mas","ya","yo","tu","su","a",
    "the","and","of","to","in","on","for","with","is","are","as","or","at","it","we","you","he","they","this","that"
}


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9' -]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _norm(text))


def _ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def _known(text: str) -> str:
    out = str(text or "")
    for pattern, replacement in _KNOWN_CORRECTIONS:
        out = pattern.sub(replacement, out)
    return out


def _load_players() -> list[dict]:
    global _PLAYER_CACHE, _PLAYER_CACHE_AT
    now = time.time()
    if _PLAYER_CACHE is not None and now - _PLAYER_CACHE_AT < _PLAYER_CACHE_TTL:
        return _PLAYER_CACHE

    by_name: dict[str, dict] = {}
    for full, pos in _FALLBACK_PLAYERS:
        nf=_norm(full); parts=nf.split()
        by_name[nf]={"full":full,"norm":nf,"first":parts[0] if parts else "","last":parts[-1] if parts else "","position":pos,"fantasy":pos in {"QB","RB","WR","TE"}}

    try:
        req = urllib.request.Request("https://api.sleeper.app/v1/players/nfl", headers={"User-Agent":"ClipSese/0.5 NFL transcript index"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.load(resp)
        for p in data.values():
            if not isinstance(p,dict) or p.get("active") is False:
                continue
            full=(p.get("full_name") or "").strip()
            if not full:
                full=f"{(p.get('first_name') or '').strip()} {(p.get('last_name') or '').strip()}".strip()
            if len(full)<4:
                continue
            nf=_norm(full); parts=nf.split()
            if len(parts)<2:
                continue
            pos=(p.get("position") or "").upper()
            fantasy_positions={str(x).upper() for x in (p.get("fantasy_positions") or [])}
            fantasy=bool({pos,*fantasy_positions} & {"QB","RB","WR","TE"})
            by_name[nf]={"full":full,"norm":nf,"first":parts[0],"last":parts[-1],"position":pos,"fantasy":fantasy}
    except Exception as e:
        print(f"[CLIPSESE] player directory fallback: {type(e).__name__}: {e}", flush=True)

    _PLAYER_CACHE=list(by_name.values())
    _PLAYER_CACHE_AT=now
    _correct_text.cache_clear()
    _best_display_player.cache_clear()
    return _PLAYER_CACHE


def _player_candidates(query: str) -> list[tuple[float, dict]]:
    q=_norm(query)
    if not q:
        return []
    qc=_compact(q)
    scored=[]
    for p in _load_players():
        nf=p["norm"]; first=p["first"]; last=p["last"]
        score=0.0
        if q==nf: score=1.0
        elif q==last: score=.995
        elif q==first and len(first)>=5: score=.90
        elif q in nf.split(): score=.91
        elif len(q.split())>=2:
            score=_ratio(qc,_compact(nf))
            if score<.78: score=0.0
        elif len(q)>=5:
            r=_ratio(q,last)
            if r>=.90: score=r*.94
        if score:
            if p["fantasy"]: score=min(1.0,score+.01)
            scored.append((score,p))
    scored.sort(key=lambda x:(-x[0],0 if x[1]["fantasy"] else 1,len(x[1]["full"])))
    return scored[:10]


@lru_cache(maxsize=4096)
def _best_display_player(word1: str, word2: str) -> str | None:
    a=_norm(word1); b=_norm(word2)
    if not a or not b or (a in _STOP and b in _STOP) or len(a)<3 or len(b)<3:
        return None
    phrase=f"{a} {b}"
    best_name=None; best_score=0.0; second=0.0
    for p in _load_players():
        if not p["fantasy"]:
            continue
        first,last=p["first"],p["last"]
        # Nombres con sufijos/varias palabras los resolvemos por sus extremos; para clips esto
        # sigue siendo suficiente y evita convertir frases ordinarias en jugadores.
        rf=_ratio(a,first); rl=_ratio(b,last); full=_ratio(_compact(phrase),_compact(p["norm"]))
        anchored_last=(b==last and rf>=.50)
        anchored_first=(a==first and rl>=.55)
        balanced=(rf>=.70 and rl>=.70 and full>=.80)
        very_close=(full>=.90 and rf>=.62 and rl>=.62)
        if not (anchored_last or anchored_first or balanced or very_close):
            continue
        score=(rf*.42)+(rl*.43)+(full*.15)
        if p["fantasy"]:
            score+=.01
        if score>best_score:
            second=best_score; best_score=score; best_name=p["full"]
        elif score>second:
            second=score
    if best_name and best_score>=.67 and (best_score-second>=.055 or best_score>=.88):
        return best_name
    return None


@lru_cache(maxsize=4096)
def _correct_text(text: str) -> str:
    out=_known(str(text or ""))
    # La corrección dinámica se hace sólo sobre pares de palabras del texto que se mostrará.
    # No tocamos cada token con fuzzy indiscriminado, porque eso sería una fábrica industrial
    # de falsos Patrick Mahomes.
    matches=list(re.finditer(r"[A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9'.-]*",out))
    replacements=[]; used_until=-1
    for i in range(len(matches)-1):
        m1,m2=matches[i],matches[i+1]
        if m1.start()<used_until:
            continue
        between=out[m1.end():m2.start()]
        if len(between)>3 or "\n" in between:
            continue
        original=out[m1.start():m2.end()]
        candidate=_best_display_player(m1.group(0),m2.group(0))
        if candidate and _norm(original)!=_norm(candidate):
            replacements.append((m1.start(),m2.end(),candidate)); used_until=m2.end()
    for s,e,repl in reversed(replacements):
        out=out[:s]+repl+out[e:]
    return out


def _segment_text(segment: dict) -> str:
    return _known(str(segment.get("search_text") or segment.get("text") or ""))


def _visible_text(segment: dict) -> str:
    return _correct_text(str(segment.get("text") or ""))


def _player_text_score(canonical: dict, text: str) -> float:
    nt=_norm(_known(text)); nf=canonical["norm"]; first=canonical["first"]; last=canonical["last"]
    if not nt:
        return 0.0
    if nf in nt:
        return 1.0
    for alias in _PLAYER_ALIASES.get(canonical["full"],()):
        if _norm(alias) in nt:
            return .98
    tokens=nt.split()
    if last in tokens:
        return .97

    # Dos palabras contiguas deben parecerse de verdad al nombre. Antes teníamos un umbral
    # demasiado permisivo y "Mahomes" llegaba a casar con frases que no tenían nada que ver.
    for i in range(len(tokens)-1):
        a,b=tokens[i],tokens[i+1]
        rf=_ratio(a,first); rl=_ratio(b,last); full=_ratio(_compact(a+b),_compact(nf))
        if (rl>=.92 and rf>=.55) or (rf>=.92 and rl>=.62) or (rf>=.70 and rl>=.70 and full>=.82) or (full>=.91 and rf>=.62 and rl>=.62):
            return min(.96,.74+rf*.10+rl*.10+full*.06)

    if len(last)>=5:
        best=max((_ratio(last,t) for t in tokens if len(t)>=4),default=0.0)
        if best>=.94:
            return .88+(best-.94)
    return 0.0


def _generic_score(query: str, text: str) -> float:
    q=_norm(query); t=_norm(_known(text))
    if not q or not t:
        return 0.0
    if q in t:
        return 1.0
    qparts=q.split(); tparts=t.split()
    if len(qparts)==1:
        token=qparts[0]
        if len(token)<4:
            return 0.0
        best=max((_ratio(token,x) for x in tparts if len(x)>=4),default=0.0)
        return best if best>=.92 else 0.0
    target=_compact(q); best=0.0
    for n in range(max(1,len(qparts)-1),min(3,len(qparts)+1)+1):
        for i in range(len(tparts)-n+1):
            best=max(best,_ratio(target,_compact(" ".join(tparts[i:i+n]))))
    return best if best>=.88 else 0.0


def _window_for_hit(segments: list[dict], idx: int, max_len: float=30.0) -> dict:
    hit=segments[idx]
    center=(float(hit.get("start",0))+float(hit.get("end",0)))/2
    start=max(0.0,center-12.0); end=start+max_len
    texts=[_visible_text(s) for s in segments if float(s.get("end",0))>=start and float(s.get("start",0))<=end]
    return {"start":round(start,3),"end":round(end,3),"text":" ".join(texts).strip()}


def keyword_search(project_id: str, query: str, max_results: int=8) -> list[dict]:
    tr=read_json(project_dir(project_id)/"transcript.json") or {}
    segments=tr.get("segments",[])
    if not segments:
        return []

    candidates=_player_candidates(query)
    use_player_memory=bool(candidates) and not (len(candidates)>=7 and len(_norm(query).split())==1)
    scored=[]
    for i,s in enumerate(segments):
        text=_segment_text(s)
        if use_player_memory:
            best_score=0.0; best_player=None
            for candidate_score,p in candidates:
                hit=_player_text_score(p,text)*(0.96+0.04*candidate_score)
                if hit>best_score:
                    best_score=hit; best_player=p
            if best_score>=.84:
                scored.append((best_score,i,best_player))
        else:
            hit=_generic_score(query,text)
            if hit:
                scored.append((hit,i,None))

    scored.sort(key=lambda x:(-x[0],float(segments[x[1]].get("start",0))))
    hits=[]; used=[]
    for score,idx,p in scored:
        win=_window_for_hit(segments,idx)
        if any(abs(win["start"]-old)<8 for old in used):
            continue
        if p and _norm(p["full"]) not in _norm(win["text"]):
            win["text"]=f"[{p['full']}] {win['text']}"
        win["score"]=round(min(1.0,score),4)
        hits.append(win); used.append(win["start"])
        if len(hits)>=max_results:
            break
    return sorted(hits,key=lambda x:x["start"])


def theme_search(project_id: str, query: str, max_results: int=8) -> list[dict]:
    candidates=_player_candidates(query)
    if candidates and len(_norm(query).split())<=3:
        hits=keyword_search(project_id,query,max_results)
        if hits:
            return hits

    from .transcribe import theme_search as legacy_theme_search
    hits=legacy_theme_search(project_id,query,max_results)
    for item in hits:
        item["text"]=_correct_text(item.get("text", ""))
    return hits
