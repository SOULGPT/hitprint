"""Write hitprint-report.html, my-formula.md and hitprint-data.json."""
import base64
import json
import subprocess
from dataclasses import asdict
from html import escape
from pathlib import Path

from .models import Rule, Video

NOT_PROOF = "Patterns from your own videos, not proof."
NO_PATTERNS = ("No clear patterns yet — keep posting and run Hitprint again "
               "after 10 more videos.")
TEMPLATE = Path(__file__).with_name("report_template.html")


def _frame(path: str, t: float) -> str | None:
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", str(t), "-i", path, "-frames:v", "1",
         "-vf", "scale=-2:192", "-f", "image2pipe", "-c:v", "mjpeg", "-"],
        capture_output=True)
    return base64.b64encode(r.stdout).decode() if r.returncode == 0 and r.stdout else None


def _strip(v: Video, score: str) -> str:
    imgs = [f for f in (_frame(v.path, t) for t in (0, 0.25, 0.5, 0.75)) if f] if v.path else []
    tags = "".join(f'<img alt="" src="data:image/jpeg;base64,{b}">' for b in imgs)
    return (f'<div class="strip"><div class="frames">{tags}</div><div class="cap">{escape(v.title)}'
            f'<b>{_fmt(getattr(v, score))} {escape(score.replace("_", " "))}</b></div></div>')


def _fmt(x) -> str:
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:.2f}"
    if isinstance(x, int) and not isinstance(x, bool):
        return f"{x:,}"
    return escape(str(x))


def _table(videos: list[Video], score: str) -> str:
    keys = sorted({k for v in videos for k in v.features})
    extra = ["views"] if score != "views" else []  # don't show views twice
    head = ["title", score, *extra, "uploaded", *keys]
    rows = []
    for v in videos:
        cells = [escape(v.title), _fmt(getattr(v, score)), *(_fmt(v.views) for _ in extra),
                 _fmt(v.upload_date), *(_fmt(v.features.get(k)) for k in keys)]
        rows.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
    th = "".join(f"<th>{escape(h.replace('_', ' '))}</th>" for h in head)
    return f'<div class="scroll"><table><tr>{th}</tr>{"".join(rows)}</table></div>'


def _html(videos: list[Video], rules: list[Rule], meta: dict) -> str:
    score = meta.get("score", "views")
    ok = [v for v in videos if v.error is None and getattr(v, score) is not None]
    parts = [f'<header><p class="kicker">Hitprint report</p><h1>Your <span>hitprint</span></h1>'
             f'<p>{escape(str(meta.get("source", "")))} · {len(ok)} videos · '
             f'{escape(str(meta.get("date", "")))}</p><p class="proof">{NOT_PROOF}</p></header>']
    for note in meta.get("notes", []):
        parts.append(f'<p class="muted">{escape(note)}</p>')

    if rules:
        items = "".join(f'<li><b class="ratio">{r.ratio:.1f}×</b><span>{escape(r.text)}</span></li>'
                        for r in rules[:5])
        parts.append(f'<section><h2>Your hitprint</h2><ol class="rules">{items}</ol></section>')
        fixes = [r for r in rules if r.fixable][:3]
        items = "".join(
            f"<li><strong>Make it so {escape(r.better)}.</strong> "
            f'<span class="muted">{r.ratio:.1f}× the {escape(score)}, based on '
            f"{r.n_better} vs {r.n_worse} videos.</span></li>" for r in fixes)
        parts.append(f"<section class='fixes'><h2>Your next 3 fixes</h2><ol>{items or '<li>None of your patterns are things you can change.</li>'}</ol></section>")
    else:
        parts.append(f"<section><h2>Your hitprint</h2><p>{NO_PATTERNS}</p></section>")

    ranked = sorted(ok, key=lambda v: getattr(v, score), reverse=True)
    if ranked:
        best = "".join(_strip(v, score) for v in ranked[:3])
        worst = "".join(_strip(v, score) for v in ranked[-3:][::-1])
        parts.append('<section><h2>Best vs worst: the first second</h2><div class="cols">'
                     f"<div><h3>Top 3</h3>{best}</div><div><h3>Bottom 3</h3>{worst}</div></div></section>")

    parts.append(f"<section><h2>Every video</h2>{_table(ok, score)}</section>")

    skipped = [f"{v.title or v.id}: {v.error}" for v in videos if v.error] + list(meta.get("skipped", []))
    if skipped:
        items = "".join(f'<li class="err">{escape(s)}</li>' for s in skipped)
        parts.append(f"<section><h2>Skipped and failed videos</h2><ul>{items}</ul></section>")

    parts.append(f"<footer>{NOT_PROOF}</footer>")
    return TEMPLATE.read_text().replace("{{body}}", "\n".join(parts))


def _formula(rules: list[Rule], meta: dict) -> str:
    score = meta.get("score", "views")
    lines = ["# My formula (from Hitprint)", "",
             f"Rules measured from my own videos ({meta.get('source', '')}, "
             f"{meta.get('date', '')}). When you script my next short video, follow them:", ""]
    if not rules:
        lines.append(NO_PATTERNS)
    for r in rules:
        lines.append(f"- Make it so {r.better}. My videos like this get {r.ratio:.1f}× the "
                     f"{score} (based on {r.n_better} vs {r.n_worse} videos, "
                     f"{r.confidence:.0%} confidence).")
    lines += ["", NOT_PROOF, ""]
    return "\n".join(lines)


def write_outputs(videos: list[Video], rules: list[Rule], out_dir: Path, meta: dict) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {"report": out_dir / "hitprint-report.html",
             "formula": out_dir / "my-formula.md",
             "data": out_dir / "hitprint-data.json"}
    paths["report"].write_text(_html(videos, rules, meta), encoding="utf-8")
    paths["formula"].write_text(_formula(rules, meta), encoding="utf-8")
    data = {"meta": meta, "videos": [asdict(v) for v in videos], "rules": [asdict(r) for r in rules]}
    paths["data"].write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return paths
