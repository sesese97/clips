"""Ephemeral, local-only project cleanup. No cloud storage or external services."""
import json
import os
import re
import shutil
import threading
import time
from pathlib import Path

from .utils import STORAGE_DIR

PROJECT_PATTERN = re.compile(r"^[a-f0-9]{16}$")
HEARTBEAT = ".clipsese_active"


def touch_project(project_id: str) -> None:
    if not PROJECT_PATTERN.fullmatch(project_id):
        return
    folder = STORAGE_DIR / project_id
    if folder.is_dir():
        (folder / HEARTBEAT).touch(exist_ok=True)


def delete_project(project_id: str) -> bool:
    if not PROJECT_PATTERN.fullmatch(project_id):
        return False
    folder = STORAGE_DIR / project_id
    if not folder.is_dir():
        return False
    shutil.rmtree(folder, ignore_errors=False)
    return True


def cleanup_stale_projects(*, ttl_hours: float = 6.0) -> int:
    """Only remove user projects whose last activity is older than TTL.

    Active import / transcription is given a 24h grace period. This is a
    per-machine workbench, not an archival store.
    """
    now = time.time()
    removed = 0
    for folder in STORAGE_DIR.iterdir():
        if not folder.is_dir() or not PROJECT_PATTERN.fullmatch(folder.name):
            continue
        pj_file = folder / "project.json"
        heartbeat = folder / HEARTBEAT
        try:
            timestamps = [
                p.stat().st_mtime for p in (pj_file, heartbeat) if p.exists()
            ]
            if not timestamps:
                timestamps = [folder.stat().st_mtime]
            age_seconds = now - max(timestamps)
            try:
                project = json.loads(pj_file.read_text(encoding="utf-8")) if pj_file.exists() else {}
            except (ValueError, OSError):
                project = {}
            running = (
                project.get("status") == "importing"
                or project.get("transcript_status") == "processing"
            )
            threshold = max(ttl_hours, 24.0) if running else ttl_hours
            if age_seconds > threshold * 3600:
                shutil.rmtree(folder)
                removed += 1
        except OSError as exc:
            print(f"[CLIPSESE] Cleanup skipped {folder.name}: {exc}", flush=True)
    return removed


def start_cleanup_daemon() -> None:
    ttl = max(1.0, float(os.getenv("CLIPSESE_TTL_HOURS", "6")))
    def worker():
        while True:
            try:
                count = cleanup_stale_projects(ttl_hours=ttl)
                if count:
                    print(f"[CLIPSESE] Cleared {count} inactive local projects", flush=True)
            except Exception as exc:
                print(f"[CLIPSESE] Cleanup warning: {exc}", flush=True)
            time.sleep(15 * 60)
    threading.Thread(target=worker, name="clipsese-temp-cleaner", daemon=True).start()
