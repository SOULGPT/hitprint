"""Find the creator's rules: feature splits whose groups differ in median score."""
import math
import random
from collections import Counter
from datetime import datetime
from statistics import median

from .models import Rule, Video

# feature -> (test that puts a value in the "yes" group, yes label, no label, yes advice, no advice)
NUMERIC = {
    "first_cut_s": (lambda x: x < 1.0, "the first cut comes before 1s", "the first cut comes at 1s or later",
                    "Cut within the first second", "Hold the first shot for at least a second"),
    "first_word_s": (lambda x: x < 0.5, "the first word comes before 0.5s", "the first word comes at 0.5s or later",
                     "Start talking within half a second", "Wait at least half a second before the first word"),
    "longest_shot_s": (lambda x: x < 4.0, "no shot lasts 4s or longer", "a shot lasts 4s or longer",
                       "Keep every shot under 4 seconds", "Let at least one shot run 4 seconds or longer"),
    "cuts_per_10s": (lambda x: x >= 3, "there are 3+ cuts per 10s", "there are fewer than 3 cuts per 10s",
                     "Cut at least 3 times every 10 seconds", "Cut fewer than 3 times every 10 seconds"),
    "duration_s": (lambda x: x < 25, "the video is under 25s", "the video is 25s or longer",
                   "Keep it under 25 seconds", "Let it run 25 seconds or longer"),
    "title_len": (lambda x: x < 45, "the title is under 45 characters", "the title is 45 characters or longer",
                  "Keep the title under 45 characters", "Write a title of 45 characters or more"),
    "first_frame_brightness": (lambda x: x >= 80, "the first frame is bright", "the first frame is dark",
                               "Open on a bright frame", "Open on a dark frame"),
    "loop_diff": (lambda x: x < 20, "the last frame matches the first (loops)", "the last frame doesn't match the first",
                  "End on the same frame you open on, so it loops", "End on a different frame from the one you open on"),
    "lufs": (lambda x: -16 <= x <= -12, "loudness is between -16 and -12 LUFS", "loudness is outside -16 to -12 LUFS",
             "Mix the audio to between -16 and -12 LUFS", "Mix the audio outside -16 to -12 LUFS"),
}
BOOLEAN = {
    "has_you": ("the title says \"you\"", "the title doesn't say \"you\"",
                "Say \"you\" in the title", "Leave \"you\" out of the title"),
    "is_question": ("the title is a question", "the title isn't a question",
                    "Phrase the title as a question", "Don't phrase the title as a question"),
    "has_number": ("the title has a number", "the title has no number",
                   "Put a number in the title", "Leave numbers out of the title"),
    "has_emoji": ("the title has an emoji", "the title has no emoji",
                  "Add an emoji to the title", "Leave emoji out of the title"),
}
SCORE_NAME = {"views": "views", "stayed_pct": "stayed-to-watch"}
N_BOOT = 1000


def _weekday(v: Video):
    try:
        return datetime.strptime(v.upload_date, "%Y%m%d").weekday() >= 5
    except (TypeError, ValueError):
        return None


def _splits(videos: list[Video]):
    """Yield (feature, (yes label, yes advice), (no label, no advice), fixable, video -> True/False/None)."""
    for name, (test, yes, no, do_yes, do_no) in NUMERIC.items():
        yield name, (yes, do_yes), (no, do_no), True, (
            lambda v, n=name, t=test: None if v.features.get(n) is None else t(v.features[n]))
    for name, (yes, no, do_yes, do_no) in BOOLEAN.items():
        yield name, (yes, do_yes), (no, do_no), True, (
            lambda v, n=name: None if v.features.get(n) is None else bool(v.features[n]))

    prefixes = Counter(v.features["series_prefix"] for v in videos if v.features.get("series_prefix"))
    if prefixes:
        top, count = prefixes.most_common(1)[0]
        if count >= 3:
            yield ("series_prefix", (f"the title starts with \"{top}\"", f"Start the title with \"{top}\""),
                   (f"the title doesn't start with \"{top}\"", f"Don't start the title with \"{top}\""), False,
                   lambda v: None if v.features.get("series_prefix") is None
                   else v.features["series_prefix"] == top)

    hours = [v.features["upload_hour"] for v in videos if v.features.get("upload_hour") is not None]
    if hours:
        h = median(hours)
        yield ("upload_hour", (f"it's posted before {h:g}:00", f"Post before {h:g}:00"),
               (f"it's posted at {h:g}:00 or later", f"Post at {h:g}:00 or later"), True,
               lambda v: None if v.features.get("upload_hour") is None else v.features["upload_hour"] < h)

    yield ("weekend", ("it's posted on a weekend", "Post on a weekend"),
           ("it's posted on a weekday", "Post on a weekday"), True, _weekday)


def _confidence(better: list[float], worse: list[float], rng: random.Random) -> float:
    wins = sum(
        median(rng.choices(better, k=len(better))) > median(rng.choices(worse, k=len(worse)))
        for _ in range(N_BOOT))
    return wins / N_BOOT


def find_rules(videos: list[Video], score: str = "views", min_group: int = 5,
               min_ratio: float = 1.3, seed: int = 7) -> list[Rule]:
    rng = random.Random(seed)
    scored = [v for v in videos if getattr(v, score) is not None and v.error is None]
    rules = []
    for feature, yes, no, fixable, side in _splits(scored):
        groups = {True: [], False: []}
        for v in scored:
            s = side(v)
            if s is not None:  # missing value: left out of this feature only
                groups[s].append(float(getattr(v, score)))
        if min(len(groups[True]), len(groups[False])) < min_group:
            continue
        med = {k: median(g) for k, g in groups.items()}
        b = med[True] >= med[False]
        better, worse = groups[b], groups[not b]
        if med[not b] <= 0:  # no meaningful ratio against a zero median
            continue
        ratio = med[b] / med[not b]
        if ratio < min_ratio:
            continue
        (label_b, advice), (label_w, _) = (yes, no) if b else (no, yes)
        text = (f"Shorts where {label_b} get {ratio:.1f}× the {SCORE_NAME.get(score, score)} "
                f"(based on {len(better)} vs {len(worse)} videos)")
        rules.append(Rule(feature, text, label_b, label_w, len(better), len(worse),
                          med[b], med[not b], ratio, _confidence(better, worse, rng), fixable, advice))
    rules.sort(key=lambda r: math.log(r.ratio) * r.confidence, reverse=True)
    return rules
