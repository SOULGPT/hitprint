"""hitprint CLI: collect -> fetch -> measure -> analyze -> report."""
import argparse
import shutil
import sys
import webbrowser
from datetime import date
from pathlib import Path

from .analyze import find_rules
from .measure import measure_video
from .report import write_outputs
from .titles import title_features
from .youtube import Blocked, fetch, list_shorts

MIN_VIDEOS = 10


def _stats():
    from . import stats
    return stats


def _usable(videos, score):
    return [v for v in videos if v.error is None and getattr(v, score) is not None]


def _err(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="hitprint", description="Find what your best short videos have in common.")
    p.add_argument("channel", nargs="?", help="YouTube handle (@name) or channel URL")
    p.add_argument("--folder", type=Path, help="folder of your own video files (any platform)")
    p.add_argument("--stats", type=Path, help="stats export for --folder (CSV or XLSX)")
    p.add_argument("--studio", type=Path, help="YouTube Studio export: score by stayed-to-watch")
    p.add_argument("--out", type=Path, default=Path("hitprint-out"))
    p.add_argument("--cookies-from-browser", metavar="BROWSER")
    p.add_argument("--no-whisper", action="store_true", help="skip the first-word check")
    p.add_argument("--open", action="store_true", help="open the report when done")
    a = p.parse_args(argv)
    if bool(a.channel) == bool(a.folder) or bool(a.folder) != bool(a.stats):
        p.error("give a channel, or --folder DIR --stats FILE")

    score = "stayed_pct" if a.studio else "views"
    meta = {"source": a.channel or str(a.folder), "date": date.today().isoformat(),
            "score": score, "notes": [], "skipped": []}
    try:
        if a.folder:
            videos, unmatched = _stats().collect_folder(a.folder, _stats().read_stats(a.stats))
            meta["skipped"] += [f"{f}: no matching stats row" for f in unmatched]
        else:
            _err(f"Listing Shorts for {a.channel}…")
            videos = list_shorts(a.channel, date.today())
            if len(_usable(videos, "views")) < MIN_VIDEOS:
                _err(f"Hitprint needs at least {MIN_VIDEOS} videos (found {len(_usable(videos, 'views'))})")
                return 2
            _err(f"Downloading {len(videos)} Shorts at 360p (cached in {a.out / 'cache'})…")
            videos = fetch(videos, a.out / "cache", cookies=a.cookies_from_browser)
    except (Blocked, RuntimeError, OSError) as e:
        _err(f"hitprint: {e}")
        return 1

    if a.studio:  # join Studio's "stayed to watch" on video id
        stayed = {r.get("id"): r.get("stayed") for r in _stats().read_stats(a.studio)}
        for v in videos:
            v.stayed_pct = stayed.get(v.id)

    whisper = not a.no_whisper and shutil.which("whisper") is not None
    if not whisper:
        meta["notes"].append("First-word check skipped (whisper "
                             + ("turned off" if a.no_whisper else "not installed") + ").")
    todo = [v for v in videos if v.error is None and v.path]
    for i, v in enumerate(todo, 1):
        _err(f"Measuring {i}/{len(todo)}: {v.title or v.id}")
        v.features.update(title_features(v.title))
        try:
            v.features.update(measure_video(v.path, whisper=whisper))
        except Exception as e:  # one bad file shouldn't sink the run
            v.error = f"measure failed: {e}"
    for v in videos:
        if v.error is None and not v.path:
            v.error = "no video file"

    found = len(_usable(videos, score))
    if found < MIN_VIDEOS:
        _err(f"Hitprint needs at least {MIN_VIDEOS} videos (found {found})")
        return 2

    rules = find_rules(videos, score=score)
    paths = write_outputs(videos, rules, a.out, meta)
    print(f"Measured {found} videos.")
    for r in rules[:5]:
        print(f"- {r.text}")
    if not rules:
        print("No clear patterns yet.")
    fixes = [r for r in rules if r.fixable][:3]
    if fixes:
        print("Next fixes:")
        for r in fixes:
            print(f"- {r.advice}.")
    for name, path in paths.items():
        print(f"{name}: {path.resolve()}")
    if a.open:
        webbrowser.open(paths["report"].resolve().as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
