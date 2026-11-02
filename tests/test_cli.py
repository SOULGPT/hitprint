from types import SimpleNamespace

from hitprint import cli
from hitprint.models import Video


def fake_pipeline(monkeypatch, n, calls):
    vids = [Video(id=f"v{i}", title=f"Title {i}", views=100 * i, duration=20.0,
                  upload_date="20261001", url=f"u{i}") for i in range(n)]
    monkeypatch.setattr(cli, "list_shorts", lambda target, today: vids)
    monkeypatch.setattr(cli, "fetch", lambda vs, cache, cookies=None: [
        setattr(v, "path", f"/x/{v.id}.mp4") or v for v in vs])
    monkeypatch.setattr(cli, "measure_video", lambda path, whisper=True: {"duration_s": 20.0})

    def find_rules(videos, score="views"):
        calls["score"] = score
        return []
    monkeypatch.setattr(cli, "find_rules", find_rules)
    return vids


def test_too_few_videos_exit_2(monkeypatch, tmp_path, capsys):
    fake_pipeline(monkeypatch, 7, {})
    assert cli.main(["@cosipai", "--out", str(tmp_path)]) == 2
    assert "Hitprint needs at least 10 videos (found 7)" in capsys.readouterr().err


def test_studio_flag_switches_score(monkeypatch, tmp_path):
    calls = {}
    fake_pipeline(monkeypatch, 12, calls)
    rows = [{"id": f"v{i}", "stayed": 50 + i} for i in range(12)]
    monkeypatch.setattr(cli, "_stats", lambda: SimpleNamespace(read_stats=lambda p: rows))
    assert cli.main(["@cosipai", "--studio", "s.csv", "--out", str(tmp_path), "--no-whisper"]) == 0
    assert calls["score"] == "stayed_pct"
    assert (tmp_path / "hitprint-report.html").exists()


def test_next_fixes_printed_as_advice(monkeypatch, tmp_path, capsys):
    from hitprint.models import Rule
    fake_pipeline(monkeypatch, 12, {})
    r = Rule("duration_s", "Shorts where the video is under 25s get 2.0× the views (based on 6 vs 6 videos)",
             "the video is under 25s", "the video is 25s or longer", 6, 6, 1000, 500, 2.0, 0.9, True,
             "Keep it under 25 seconds")
    monkeypatch.setattr(cli, "find_rules", lambda videos, score="views": [r])
    assert cli.main(["@cosipai", "--out", str(tmp_path), "--no-whisper"]) == 0
    out = capsys.readouterr().out
    assert "- Keep it under 25 seconds.\n" in out and "Make it so" not in out
