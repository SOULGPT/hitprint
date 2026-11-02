import json

from hitprint.models import Rule, Video
from hitprint.report import write_outputs

META = {"source": "@cosipai", "date": "2026-11-02", "score": "views"}


def videos(n=12, path=None):
    return [Video(id=f"v{i}", title=f"Title {i}", views=100 * (i + 1), duration=20.0,
                  upload_date="20261001", path=path, features={"first_cut_s": 0.5 + i})
            for i in range(n)]


def rule(feature="first_cut_s", fixable=True):
    return Rule(feature, f"Shorts where {feature} is good get 2.1× the views (based on 9 vs 14 videos)",
                f"{feature} is good", f"{feature} is bad", 9, 14, 2100, 1000, 2.1, 0.97, fixable)


def test_outputs_written(tmp_path):
    out = write_outputs(videos(), [rule()], tmp_path, META)
    assert set(out) == {"report", "formula", "data"}
    assert out["report"].name == "hitprint-report.html"
    assert out["formula"].name == "my-formula.md"
    assert out["data"].name == "hitprint-data.json"
    html = out["report"].read_text()
    assert "Your hitprint" in html and "not proof" in html
    assert "Your next 3 fixes" in html and "based on 9 vs 14 videos" in html
    assert "@cosipai" in html and "12 videos" in html
    md = out["formula"].read_text()
    assert "first_cut_s is good" in md and "9 vs 14" in md
    data = json.loads(out["data"].read_text())
    assert len(data["videos"]) == 12 and data["rules"][0]["ratio"] == 2.1


def test_fixes_only_fixable(tmp_path):
    html = write_outputs(videos(), [rule("series_prefix", fixable=False)], tmp_path, META)["report"].read_text()
    fixes = html.split("Your next 3 fixes")[1].split("</section>")[0]
    assert "series_prefix" not in fixes


def test_no_rules_message(tmp_path):
    out = write_outputs(videos(), [], tmp_path, META)
    html = out["report"].read_text()
    assert "No clear patterns yet" in html and "Your next 3 fixes" not in html
    assert "No clear patterns yet" in out["formula"].read_text()


def test_failed_videos_listed(tmp_path):
    vs = videos()
    vs[0].error = "bot check"
    meta = {**META, "skipped": ["clip.mp4: no matching stats row"]}
    html = write_outputs(vs, [], tmp_path, meta)["report"].read_text()
    skipped = html.split("Skipped and failed")[1]
    assert "bot check" in skipped and "Title 0" in skipped
    assert "clip.mp4: no matching stats row" in skipped


def test_titles_are_escaped(tmp_path):
    vs = videos()
    vs[0].title = "<script>alert(1)</script>"
    html = write_outputs(vs, [], tmp_path, META)["report"].read_text()
    assert "<script>alert" not in html and "&lt;script&gt;" in html


def test_filmstrips_embedded(tmp_path, cut_video):
    html = write_outputs(videos(path=cut_video), [rule()], tmp_path, META)["report"].read_text()
    assert html.count("data:image/jpeg;base64,") == 6 * 4  # top 3 + bottom 3, 4 frames each
