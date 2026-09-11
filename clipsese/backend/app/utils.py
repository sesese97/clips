import json
import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

STORAGE_DIR = Path(os.getenv("STORAGE_DIR", Path(__file__).resolve().parents[1] / "storage"))
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


class CommandError(RuntimeError):
    def __init__(self, message: str, *, command: list[str] | None = None, returncode: int | None = None):
        super().__init__(message)
        self.command = command or []
        self.returncode = returncode


def run(cmd: list[str], *, timeout: int | None = None) -> subprocess.CompletedProcess:
    safe_cmd = [str(x) for x in cmd]
    print("[CLIPSESE] EXEC:", " ".join(safe_cmd), flush=True)
    try:
        cp = subprocess.run(safe_cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise CommandError(f"El proceso excedió el tiempo límite ({timeout}s)", command=safe_cmd) from e

    if cp.stdout:
        print("[CLIPSESE] STDOUT:\n" + cp.stdout[-8000:], flush=True)
    if cp.stderr:
        print("[CLIPSESE] STDERR:\n" + cp.stderr[-8000:], flush=True)

    if cp.returncode != 0:
        msg = (cp.stderr or cp.stdout or f"Proceso terminó con código {cp.returncode}").strip()
        raise CommandError(msg[-6000:], command=safe_cmd, returncode=cp.returncode)
    return cp


def binary_version(command: list[str]) -> str | None:
    try:
        cp = subprocess.run(command, capture_output=True, text=True, timeout=10)
        text = (cp.stdout or cp.stderr or "").strip()
        return text.splitlines()[0] if text else None
    except Exception:
        return None


def runtime_diagnostics() -> dict:
    return {
        "ffmpeg": binary_version(["ffmpeg", "-version"]),
        "yt_dlp": binary_version(["python", "-m", "yt_dlp", "--version"]),
        "deno": binary_version(["/usr/local/bin/deno", "--version"]),
        "deno_path": shutil.which("deno"),
        "storage_dir": str(STORAGE_DIR),
    }


def ffprobe(path: Path) -> dict:
    cp = run([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration:stream=index,codec_type,width,height,r_frame_rate,codec_name",
        "-of", "json", str(path)
    ], timeout=60)
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
