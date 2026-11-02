import json
from datetime import date
from types import SimpleNamespace

from hitprint.models import Video
from hitprint.youtube import fetch, list_shorts

TODAY = date(2026, 11, 2)
META = {
    "aaa": {"upload_date": "20261020", "duration": 31, "view_count": 1234, "timestamp": 1792500000},
    "bbb": {"upload_date": "20261025", "duration": 18.5, "view_count": "88"},
    "new": {"upload_date": "20261101", "duration": 20, "view_count": 5},
}


def ok(stdout=""):
    return SimpleNamespace(returncode=0, stdout=stdout, stderr="")


def fake_listing(calls):
    def run(cmd, **kw):
        calls.append(cmd)
        if "--flat-playlist" in cmd:
            assert cmd[-1] == "https://www.youtube.com/@cosipai/shorts"
            entries = [{"id": i, "title": f"Title {i}", "view_count": 1} for i in META]
            return ok(json.dumps({"entries": entries}))
        vid = cmd[-1].rsplit("/", 1)[-1]
        return ok(json.dumps({"id": vid, **META[vid]}))
    return run


def test_list_shorts_parses_and_drops_recent():
    calls = []
    videos = list_shorts("@cosipai", TODAY, run=fake_listing(calls))
    assert [v.id for v in videos] == ["aaa", "bbb"]
    a, b = videos
    assert a.views == 1234 and isinstance(a.views, int)
    assert b.views == 88 and isinstance(b.views, int)
    assert a.duration == 31 and a.upload_date == "20261020" and a.title == "Title aaa"
    assert a.url == "https://www.youtube.com/shorts/aaa"
    assert "upload_hour" in a.features and "upload_hour" not in b.features


def test_list_shorts_accepts_handle_without_at():
    assert len(list_shorts("cosipai", TODAY, run=fake_listing([]))) == 2


def v(i):
    return Video(id=i, title=i, views=1, duration=1.0, upload_date="20261001",
                 url=f"https://www.youtube.com/shorts/{i}")


def test_fetch_retries_then_continues(tmp_path):
    calls, sleeps = [], []

    def run(cmd, **kw):
        calls.append(cmd)
        if cmd[-1].endswith("/A"):
            return SimpleNamespace(returncode=1, stdout="",
                                   stderr="ERROR: Sign in to confirm you're not a bot")
        out = cmd[cmd.index("-o") + 1]
        open(out, "wb").write(b"x")
        return ok()

    b, a = fetch([v("B"), v("A")], tmp_path, run=run, sleep=sleeps.append)
    assert "bot check" in a.error and a.path is None
    assert "--cookies-from-browser" in a.error
    assert b.path == str(tmp_path / "B.mp4") and b.error is None
    assert sum(c[-1].endswith("/A") for c in calls) == 4  # 1 try + 3 retries
    assert [s for s in sleeps if s > 2.0] == [5, 15, 45]
    assert sleeps[0] == 2.0  # spacing before A's download, after B


def test_fetch_uses_cache(tmp_path):
    (tmp_path / "A.mp4").write_bytes(b"x")

    def run(cmd, **kw):
        raise AssertionError("should not download a cached file")

    (a,) = fetch([v("A")], tmp_path, run=run, sleep=lambda s: None)
    assert a.path == str(tmp_path / "A.mp4")


def test_fetch_passes_cookies_and_records_other_errors(tmp_path):
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        return SimpleNamespace(returncode=1, stdout="", stderr="ERROR: Video unavailable")

    (a,) = fetch([v("A")], tmp_path, cookies="chrome", run=run, sleep=lambda s: None)
    assert len(calls) == 1  # no retry for non-bot errors
    i = calls[0].index("--cookies-from-browser")
    assert calls[0][i + 1] == "chrome"
    assert "Video unavailable" in a.error


BOT = SimpleNamespace(returncode=1, stdout="", stderr="ERROR: HTTP Error 429: Too Many Requests")


def test_fetch_stops_after_lasting_block(tmp_path):
    calls = []

    def run(cmd, **kw):
        calls.append(cmd[-1])
        return BOT

    a, b, c = fetch([v("A"), v("B"), v("C")], tmp_path, run=run, sleep=lambda s: None)
    assert len(calls) == 4 and all(u.endswith("/A") for u in calls)
    assert "bot check" in a.error
    assert "not fetched" in b.error and "not fetched" in c.error


def test_list_shorts_metadata_retries_then_stops(tmp_path):
    calls, sleeps = [], []
    meta_ok = fake_listing([])

    def run(cmd, **kw):
        calls.append(cmd[-1])
        if "--flat-playlist" in cmd or cmd[-1].endswith("/aaa"):
            return meta_ok(cmd)
        return BOT  # blocked from bbb on

    videos = list_shorts("@cosipai", TODAY, run=run, sleep=sleeps.append)
    by_id = {v.id: v for v in videos}
    assert by_id["aaa"].error is None and by_id["aaa"].views == 1234
    assert "bot check" in by_id["bbb"].error
    assert "not checked" in by_id["new"].error
    assert sum(u.endswith("/bbb") for u in calls) == 4
    assert not any(u.endswith("/new") for u in calls)
    assert sleeps == [5, 15, 45]
