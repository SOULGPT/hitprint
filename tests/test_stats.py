import zipfile
from pathlib import Path

from hitprint import stats
from hitprint.stats import collect_folder, read_stats

TEMPLATE = Path(__file__).parent.parent / "templates" / "stats-template.csv"


def test_aliases_and_number_formats(tmp_path):
    f = tmp_path / "s.csv"
    f.write_text("Video Views,Post time,Caption,Likes,Average percentage viewed\n"
                 '1.2K,2026-10-01 18:30,Hi,99,12%\n"1,234",10/02/2026,Yo,1,\n3.4M,,X,,\n')
    rows = read_stats(f)
    assert rows[0] == {"views": 1200, "date": "20261001", "title": "Hi", "stayed": 12.0}
    assert rows[1]["views"] == 1234 and rows[1]["date"] == "20261002" and rows[1]["stayed"] is None
    assert rows[2]["views"] == 3_400_000 and rows[2]["date"] is None


def test_xlsx(tmp_path):
    f = tmp_path / "s.xlsx"
    with zipfile.ZipFile(f, "w") as z:
        z.writestr("xl/sharedStrings.xml", '<sst xmlns="http://schemas.openxmlformats.org/'
                   'spreadsheetml/2006/main"><si><t>Plays</t></si><si><t>Title</t></si>'
                   '<si><t>Cat video</t></si></sst>')
        z.writestr("xl/worksheets/sheet1.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/'
                   'spreadsheetml/2006/main"><sheetData><row><c r="A1" t="s"><v>0</v></c>'
                   '<c r="B1" t="s"><v>1</v></c></row><row><c r="A2"><v>500</v></c>'
                   '<c r="B2" t="s"><v>2</v></c></row></sheetData></worksheet>')
    assert read_stats(f) == [{"views": 500, "title": "Cat video"}]


def test_template_matching_by_file(tmp_path):
    rows = read_stats(TEMPLATE)
    assert rows and all("file" in r and "views" in r for r in rows)
    (tmp_path / rows[0]["file"]).write_bytes(b"")
    (tmp_path / "Other.MP4").write_bytes(b"")
    videos, unmatched = collect_folder(tmp_path, rows)
    assert [v.path for v in videos] == [str(tmp_path / rows[0]["file"])]
    assert videos[0].views == rows[0]["views"] and videos[0].title == rows[0]["title"]
    assert unmatched == ["Other.MP4"]


def test_match_by_date_and_duration(tmp_path, monkeypatch):
    (tmp_path / "clip_20261001.mp4").write_bytes(b"")
    monkeypatch.setattr(stats, "duration", lambda p: 30.4)
    rows = [{"views": 10, "date": "20261002", "duration": 30.0},
            {"views": 20, "date": "20261001", "duration": 45.0}]
    videos, unmatched = collect_folder(tmp_path, rows)
    assert [v.views for v in videos] == [10] and unmatched == []


def test_ambiguous_match_left_unmatched(tmp_path, monkeypatch):
    for n in ("a_2026-10-01.mp4", "b_2026-10-01.mp4"):
        (tmp_path / n).write_bytes(b"")
    monkeypatch.setattr(stats, "duration", lambda p: 30.0)
    videos, unmatched = collect_folder(tmp_path, [{"views": 10, "date": "20261001", "duration": 30.0},
                                                  {"views": 20, "date": "20261001", "duration": 30.0}])
    assert videos == [] and unmatched == ["a_2026-10-01.mp4", "b_2026-10-01.mp4"]


def test_too_new_flagged(tmp_path):
    (tmp_path / "x.mp4").write_bytes(b"")
    from datetime import date
    videos, _ = collect_folder(tmp_path, [{"file": "x.mp4", "views": 5,
                                           "date": date.today().strftime("%Y%m%d")}])
    assert "3 days" in videos[0].error
