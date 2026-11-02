"""Collect a channel's public Shorts with yt-dlp and fetch small cached copies."""
import json
import subprocess
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from .models import Video

MIN_AGE_DAYS = 3
BACKOFF = (5, 15, 45)  # waits before each of the 3 retries
BOT_SIGNS = ("not a bot", "sign in to confirm", "429", "too many requests")


def _json(run, cmd: list[str]) -> dict:
    r = run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(_last_line(r.stderr))
    return json.loads(r.stdout)


def _last_line(text: str) -> str:
    lines = [l for l in (text or "").strip().splitlines() if l.strip()]
    return lines[-1] if lines else "unknown error"


def list_shorts(handle: str, today: date, run=subprocess.run) -> list[Video]:
    handle = handle if handle.startswith("@") else "@" + handle
    listing = _json(run, ["yt-dlp", "--flat-playlist", "-J",
                          f"https://www.youtube.com/{handle}/shorts"])
    cutoff = (today - timedelta(days=MIN_AGE_DAYS)).strftime("%Y%m%d")
    videos = []
    for e in listing.get("entries") or []:
        url = f"https://www.youtube.com/shorts/{e['id']}"
        v = Video(id=e["id"], title=e.get("title") or "", views=None,
                  duration=None, upload_date=None, url=url)
        # shortcut: metadata calls are not spaced or retried, add if YouTube blocks them
        try:
            m = _json(run, ["yt-dlp", "-J", "--skip-download", url])
        except (RuntimeError, json.JSONDecodeError) as err:
            v.error = f"metadata: {err}"
            videos.append(v)
            continue
        v.upload_date = m.get("upload_date")
        if v.upload_date and v.upload_date > cutoff:
            continue  # too new: views haven't settled
        views = m.get("view_count", e.get("view_count"))
        v.views = int(float(views)) if views is not None else None
        v.duration = float(m["duration"]) if m.get("duration") is not None else None
        v.title = m.get("title") or v.title
        if m.get("timestamp"):
            v.features["upload_hour"] = datetime.fromtimestamp(m["timestamp"]).hour
        videos.append(v)
    return videos


def fetch(videos: list[Video], cache: Path, cookies: str | None = None,
          spacing: float = 2.0, run=subprocess.run, sleep=time.sleep) -> list[Video]:
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    downloaded_any = False
    for v in videos:
        if v.error:
            continue
        target = cache / f"{v.id}.mp4"
        if target.exists():
            v.path = str(target)
            continue
        cmd = ["yt-dlp", "-q", "--no-warnings",
               "-f", "b[height<=360][ext=mp4]/bv*[height<=360]+ba/w",
               "--merge-output-format", "mp4", "-o", str(target)]
        if cookies:
            cmd += ["--cookies-from-browser", cookies]
        cmd.append(v.url)
        for attempt in range(len(BACKOFF) + 1):
            if downloaded_any and attempt == 0:
                sleep(spacing)  # space downloads out to avoid the bot check
            downloaded_any = True
            r = run(cmd, capture_output=True, text=True)
            if r.returncode == 0 and target.exists():
                v.path = str(target)
                break
            msg = _last_line(r.stderr)
            if not any(s in msg.lower() for s in BOT_SIGNS):
                v.error = f"download failed: {msg}"
                break
            if attempt == len(BACKOFF):
                v.error = ("bot check: YouTube blocked the download after 3 retries; "
                           "try --cookies-from-browser chrome")
                break
            sleep(BACKOFF[attempt])
    return videos
