import pytest

from hitprint.analyze import find_rules
from hitprint.models import Video


def vid(i, views, stayed=None, date=None, **features):
    return Video(id=f"v{i}", title=f"t{i}", views=views, duration=20.0,
                 upload_date=date, stayed_pct=stayed, features=features)


def cut_videos(n_fast, n_slow, fast_views=1000, slow_views=300):
    return ([vid(i, fast_views, first_cut_s=0.5) for i in range(n_fast)]
            + [vid(100 + i, slow_views, first_cut_s=3.0) for i in range(n_slow)])


def test_rule_found():
    rules = find_rules(cut_videos(6, 6))
    assert len(rules) == 1
    r = rules[0]
    assert r.feature == "first_cut_s"
    assert r.ratio == pytest.approx(1000 / 300, rel=0.01)
    assert "6 vs 6" in r.text
    assert "1s" in r.text
    assert r.median_better == 1000 and r.median_worse == 300
    assert r.confidence == pytest.approx(1.0)
    assert r.fixable is True
    assert r.advice == "Cut within the first second"


def test_min_group():
    assert find_rules(cut_videos(4, 8)) == []


def test_min_ratio():
    assert find_rules(cut_videos(6, 6, fast_views=1200, slow_views=1000)) == []


def test_none_excluded():
    videos = cut_videos(6, 6)
    for v in videos:
        v.features["first_word_s"] = 0.2 if v.views == 1000 else 3.0
    # 3 silent videos: no first word. Must not be counted as 0 (which would be "fast").
    silent = [vid(200 + i, 10, first_cut_s=0.5, first_word_s=None) for i in range(3)]
    rules = {r.feature: r for r in find_rules(videos + silent)}
    assert rules["first_word_s"].n_better + rules["first_word_s"].n_worse == 12
    assert rules["first_cut_s"].n_better + rules["first_cut_s"].n_worse == 15


def test_constant_feature_skipped():
    videos = [vid(i, 100 * (i + 1), first_cut_s=0.5, has_you=True) for i in range(12)]
    assert find_rules(videos) == []


def test_zero_median_skipped():
    assert find_rules(cut_videos(6, 6, fast_views=1000, slow_views=0)) == []


def test_score_stayed():
    videos = ([vid(i, 500, stayed=80.0, first_cut_s=0.5) for i in range(6)]
              + [vid(10 + i, 500, stayed=40.0, first_cut_s=3.0) for i in range(6)])
    assert find_rules(videos) == []  # same views
    rules = find_rules(videos, score="stayed_pct")
    assert len(rules) == 1 and rules[0].ratio == pytest.approx(2.0)


def test_series_prefix_not_fixable():
    videos = ([vid(i, 1000, series_prefix="what if you") for i in range(6)]
              + [vid(10 + i, 200, series_prefix=f"other {i} x") for i in range(6)])
    (r,) = find_rules(videos)
    assert r.feature == "series_prefix" and r.fixable is False
    assert "what if you" in r.text and r.advice == 'Start the title with "what if you"'


def test_weekend_split():
    sat, tue = "20261031", "20261027"
    videos = ([vid(i, 1000, date=sat) for i in range(6)]
              + [vid(10 + i, 250, date=tue) for i in range(6)])
    (r,) = find_rules(videos)
    assert r.feature == "weekend" and "weekend" in r.better and r.fixable
    assert r.advice == "Post on a weekend"


def test_sorted_by_effect_times_confidence():
    videos = cut_videos(6, 6)
    for v in videos:
        # weaker effect on another feature, same split
        v.features["has_you"] = v.views == 1000
    videos += [vid(300 + i, 450, has_you=True) for i in range(6)]
    rules = find_rules(videos)
    assert [r.feature for r in rules][0] == "first_cut_s"
    assert len(rules) == 2
