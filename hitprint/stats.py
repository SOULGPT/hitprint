"""Folder mode: read any platform's stats export and match rows to local video files."""
import csv
import re
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

from .measure import duration
from .models import Video

ALIASES = {
    "views": ("views", "video views", "plays", "total plays", "reach"),
    "date": ("date", "post time", "publish time", "posted", "published"),
    "title": ("title", "caption", "description", "video title"),
    "duration": ("duration", "video duration", "length"),
    "stayed": ("stayed to watch", "stayed_pct", "average percentage viewed", "completion rate"),
    "file": ("file", "filename"),
    "id": ("id", "video id", "content"),
}
HEADER = {alias: key for key, names in ALIASES.items() for alias in names}
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
DATE_FORMATS = ("%m/%d/%Y", "%m/%d/%y", "%b %d, %Y", "%d %b %Y", "%B %d, %Y")
MIN_AGE_DAYS = 3
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _number(s: str) -> float | None:
    s = s.strip().replace(",", "").rstrip("%").strip()
    if ":" in s:  # m:ss or h:mm:ss
        try:
            return float(sum(float(p) * 60 ** i for i, p in enumerate(reversed(s.split(":")))))
        except ValueError:
            return None
    mult = {"K": 1e3, "M": 1e6, "B": 1e9}.get(s[-1:].upper(), 1)
    try:
        return float(s[:-1] if mult != 1 else s) * mult
    except ValueError:
        return None


def _date(s: str) -> str | None:
    s = s.strip()
    if re.fullmatch(r"\d{5}(\.\d+)?", s):  # Excel serial day number
        return (datetime(1899, 12, 30) + timedelta(days=float(s))).strftime("%Y%m%d")
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).strftime("%Y%m%d")
    except ValueError:
        pass
    head = s.split(" ")[0] if "/" in s else s  # "10/02/2026 18:30" -> date part
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(head, fmt).strftime("%Y%m%d")
        except ValueError:
            pass
    return None


def _xlsx_rows(path: Path) -> list[list[str]]:
    """First sheet of an .xlsx as rows of strings (standard library only)."""
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            shared = ["".join(t.text or "" for t in si.iter(NS + "t"))
                      for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(NS + "si")]
        sheet = sorted(n for n in z.namelist() if n.startswith("xl/worksheets/sheet"))[0]
        rows = []
        for row in ET.fromstring(z.read(sheet)).iter(NS + "row"):
            cells = {}
            for c in row.iter(NS + "c"):
                col = 0
                for ch in re.match(r"[A-Z]+", c.get("r", "A")).group():
                    col = col * 26 + ord(ch) - 64
                v = c.find(NS + "v")
                if c.get("t") == "s" and v is not None:
                    text = shared[int(v.text)]
                elif c.get("t") == "inlineStr":
                    text = "".join(t.text or "" for t in c.iter(NS + "t"))
                else:
                    text = v.text if v is not None and v.text else ""
                cells[col - 1] = text
            rows.append([cells.get(i, "") for i in range(max(cells, default=-1) + 1)])
        return rows


def read_stats(path: Path) -> list[dict]:
    path = Path(path)
    if path.suffix.lower() == ".xlsx":
        rows = _xlsx_rows(path)
    else:
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
    if not rows:
        return []
    keys = [HEADER.get(h.strip().lower()) for h in rows[0]]
    out = []
    for row in rows[1:]:
        if not any(c.strip() for c in row):
            continue
        rec = {}
        for key, cell in zip(keys, row):
            if key is None or key in rec:  # unknown column, or a second alias of one we have
                continue
            cell = cell.strip()
            if key == "views":
                n = _number(cell)
                rec[key] = int(n) if n is not None else None
            elif key in ("duration", "stayed"):
                rec[key] = _number(cell)
            elif key == "date":
                rec[key] = _date(cell) if cell else None
            else:
                rec[key] = cell
        out.append(rec)
    return out


def _file_date(p: Path) -> str:
    m = re.search(r"(20\d\d)-?(\d\d)-?(\d\d)", p.name)
    if m:
        return "".join(m.groups())
    st = p.stat()
    return datetime.fromtimestamp(getattr(st, "st_birthtime", st.st_mtime)).strftime("%Y%m%d")


def _close(file_date: str, row: dict, dur: float | None) -> bool:
    if not row.get("date") or row.get("duration") is None or dur is None:
        return False
    days = abs((datetime.strptime(file_date, "%Y%m%d") - datetime.strptime(row["date"], "%Y%m%d")).days)
    return days <= 1 and abs(dur - row["duration"]) <= 1


def collect_folder(folder: Path, stats: list[dict]) -> tuple[list[Video], list[str]]:
    files = sorted(p for p in Path(folder).iterdir() if p.suffix.lower() in VIDEO_EXT)
    by_name = {r["file"].lower(): r for r in stats if r.get("file")}
    pairs = [(p, by_name.pop(p.name.lower())) for p in files if p.name.lower() in by_name]
    named = {id(r) for r in stats if r.get("file")}
    loose_rows = [r for r in stats if id(r) not in named]
    loose_files = [p for p in files if p not in {f for f, _ in pairs}]

    if loose_rows and loose_files:  # match by date (±1 day) + duration (±1 s), never guessing
        cand = {}
        for p in loose_files:
            try:
                dur = duration(str(p))
            except Exception:
                dur = None
            cand[p] = [r for r in loose_rows if _close(_file_date(p), r, dur)]
        for p, rows in cand.items():
            if len(rows) == 1 and sum(rows[0] in rs for rs in cand.values()) == 1:
                pairs.append((p, rows[0]))
    matched = {f for f, _ in pairs}

    cutoff = (date.today() - timedelta(days=MIN_AGE_DAYS)).strftime("%Y%m%d")
    videos = []
    for p, r in sorted(pairs):
        v = Video(id=r.get("id") or p.stem, title=r.get("title") or "", views=r.get("views"),
                  duration=r.get("duration"), upload_date=r.get("date"), path=str(p),
                  stayed_pct=r.get("stayed"))
        if v.upload_date and v.upload_date > cutoff:
            v.error = f"too new (under {MIN_AGE_DAYS} days): views haven't settled"
        videos.append(v)
    return videos, [p.name for p in files if p not in matched]
