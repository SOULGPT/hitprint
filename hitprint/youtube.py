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
BLOCKED = "bot check: YouTube blocked us after 3 retries; try --cookies-from-browser chrome"


class Blocked(Exception):
    pass


def _last_line(text: str) -> str:
    lines = [l for l in (text or "").strip().splitlines() if l.strip()]
    return lines[-1] if lines else "unknown error"


def _run(run, cmd: list[str], sleep) -> subprocess.CompletedProcess:
    """Run yt-dlp; on a bot check retry with backoff, then raise Blocked."""
    for attempt in range(len(BACKOFF) + 1):
        r = run(cmd, capture_output=True, text=True)
        if r.returncode == 0 or not any(s in _last_line(r.stderr).lower() for s in BOT_SIGNS):
            return r
        if attempt < len(BACKOFF):
            sleep(BACKOFF[attempt])
    raise Blocked(BLOCKED)


def _json(run, cmd: list[str], sleep) -> dict:
    r = _run(run, cmd, sleep)
    if r.returncode != 0:
        raise RuntimeError(_last_line(r.stderr))
    return json.loads(r.stdout)


def shorts_url(channel: str) -> str:
    """A handle (@name or name) or any channel URL -> that channel's Shorts tab URL."""
    if "youtube.com/" not in channel:
        return f"https://www.youtube.com/{channel if channel.startswith('@') else '@' + channel}/shorts"
    base = channel.split("?")[0].split("#")[0].rstrip("/")
    base = base if "://" in base else "https://" + base
    head, _, tab = base.rpartition("/")
    if tab in ("shorts", "videos", "featured", "streams", "playlists", "community"):
        base = head
    return base + "/shorts"


def list_shorts(handle: str, today: date, run=subprocess.run, sleep=time.sleep) -> list[Video]:
    listing = _json(run, ["yt-dlp", "--flat-playlist", "-J", shorts_url(handle)], sleep)
    cutoff = (today - timedelta(days=MIN_AGE_DAYS)).strftime("%Y%m%d")
    videos, blocked = [], False
    for e in listing.get("entries") or []:
        url = f"https://www.youtube.com/shorts/{e['id']}"
        v = Video(id=e["id"], title=e.get("title") or "", views=None,
                  duration=None, upload_date=None, url=url)
        videos.append(v)
        if blocked:
            v.error = "not checked: YouTube blocked earlier requests"
            continue
        try:
            m = _json(run, ["yt-dlp", "-J", "--skip-download", url], sleep)
        except Blocked as err:
            v.error, blocked = str(err), True
            continue
        except (RuntimeError, json.JSONDecodeError) as err:
            v.error = f"metadata: {err}"
            continue
        v.upload_date = m.get("upload_date")
        if v.upload_date and v.upload_date > cutoff:
            videos.pop()  # too new: views haven't settled
            continue
        views = m.get("view_count", e.get("view_count"))
        v.views = int(float(views)) if views is not None else None
        v.duration = float(m["duration"]) if m.get("duration") is not None else None
        v.title = m.get("title") or v.title
        if m.get("timestamp"):  # hour in this machine's local timezone
            v.features["upload_hour"] = datetime.fromtimestamp(m["timestamp"]).hour
    return videos


def fetch(videos: list[Video], cache: Path, cookies: str | None = None,
          spacing: float = 2.0, run=subprocess.run, sleep=time.sleep) -> list[Video]:
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    downloaded_any = blocked = False
    for v in videos:
        if v.error:
            continue
        target = cache / f"{v.id}.mp4"
        if target.exists():
            v.path = str(target)
            continue
        if blocked:  # stop hitting a YouTube that keeps blocking us
            v.error = "not fetched: YouTube blocked downloads; try --cookies-from-browser chrome"
            continue
        cmd = ["yt-dlp", "-q", "--no-warnings",
               "-f", "b[height<=360][ext=mp4]/bv*[height<=360]+ba/w",
               "--merge-output-format", "mp4", "-o", str(target)]
        if cookies:
            cmd += ["--cookies-from-browser", cookies]
        cmd.append(v.url)
        if downloaded_any:
            sleep(spacing)  # space downloads out to avoid the bot check
        downloaded_any = True
        try:
            r = _run(run, cmd, sleep)
        except Blocked as err:
            v.error, blocked = str(err), True
            continue
        if r.returncode == 0 and target.exists():
            v.path = str(target)
        else:
            v.error = f"download failed: {_last_line(r.stderr)}"
    return videos
