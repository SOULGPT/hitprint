"""Editing features per video, via ffmpeg/ffprobe and (optionally) whisper."""
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

W, H = 64, 112  # small grayscale frames for brightness and loop match


def _ff(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *args],
                          capture_output=True)


def duration(path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def cut_times(path: str) -> list[float]:
    """Shorts Doctor method: 10 fps, scene > 0.2, merge within 0.3s, ignore < 0.2s."""
    r = _ff(["-i", path, "-an", "-vf", "fps=10,select='gt(scene,0.2)',showinfo",
             "-f", "null", "-"])
    hits = [float(t) for t in re.findall(rb"pts_time:([\d.]+)", r.stderr)]
    cuts: list[float] = []
    for t in sorted(hits):
        if t < 0.2:
            continue
        if cuts and t - cuts[-1] <= 0.3:
            continue
        cuts.append(t)
    return cuts


def lufs(path: str) -> float | None:
    r = _ff(["-i", path, "-vn", "-af", "ebur128", "-f", "null", "-"])
    m = re.findall(rb"I:\s+(-?[\d.]+) LUFS", r.stderr)
    return float(m[-1]) if m else None  # last match is the summary; None = no audio


def _gray_frames(args: list[str]) -> bytes:
    r = _ff([*args, "-vf", f"scale={W}:{H},format=gray", "-f", "rawvideo", "-"])
    return r.stdout


def first_and_last_frame(path: str) -> tuple[bytes, bytes]:
    first = _gray_frames(["-i", path, "-frames:v", "1"])[: W * H]
    tail = _gray_frames(["-sseof", "-0.5", "-i", path])
    return first, tail[-W * H:]


def first_word(path: str) -> float | None:
    if not shutil.which("whisper"):
        return None
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(
            ["whisper", path, "--model", "base", "--word_timestamps", "True",
             "--output_format", "json", "--output_dir", d, "--fp16", "False",
             "--verbose", "False"], capture_output=True)
        files = list(Path(d).glob("*.json"))
        if not files:
            return None
        data = json.loads(files[0].read_text())
    starts = [w["start"] for s in data.get("segments", []) for w in s.get("words", [])]
    return min(starts) if starts else None


def measure_video(path: str, whisper: bool = True) -> dict:
    dur = duration(path)
    cuts = cut_times(path)
    bounds = [0.0, *cuts, dur]
    first, last = first_and_last_frame(path)
    loop = (sum(abs(a - b) for a, b in zip(first, last)) / len(first)
            if first and len(first) == len(last) else None)
    return {
        "first_word_s": first_word(path) if whisper else None,
        "first_cut_s": cuts[0] if cuts else None,
        "longest_shot_s": max(b - a for a, b in zip(bounds, bounds[1:])),
        "cuts_per_10s": len(cuts) / dur * 10 if dur else 0.0,
        "lufs": lufs(path),
        "first_frame_brightness": sum(first) / len(first) if first else None,
        "loop_diff": loop,
        "duration_s": dur,
    }
