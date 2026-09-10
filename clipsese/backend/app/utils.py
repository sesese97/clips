import json
import os
import subprocess
from pathlib import Path
from urllib.parse import urlparse

STORAGE_DIR = Path(os.getenv("STORAGE_DIR", Path(__file__).resolve().parents[1] / "storage"))
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def ffprobe(path: Path) -> dict:
    cp = run([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration:stream=index,codec_type,width,height,r_frame_rate,codec_name",
        "-of", "json", str(path)
    ])
    data = json.loads(cp.stdout)
    duration = float(data.get("format", {}).get("duration") or 0)
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    audio = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), {})
    return {
        "duration": duration,
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "fps": video.get("r_frame_rate") or "0/1",
        "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name"),
    }


def project_dir(project_id: str) -> Path:
    p = STORAGE_DIR / project_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def is_allowed_url(url: str, *, youtube_only: bool = False) -> bool:
    try:
        p = urlparse(url)
    except Exception:
        return False
    if p.scheme != "https":
        return False
    host = p.netloc.lower().split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    youtube = {"youtube.com", "youtu.be", "m.youtube.com"}
    if youtube_only:
        return host in youtube
    allowed = youtube | {"x.com", "twitter.com", "tiktok.com", "vm.tiktok.com"}
    return host in allowed
