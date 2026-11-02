import math

from hitprint.measure import measure_video


def test_cuts_detected(cut_video):
    f = measure_video(cut_video, whisper=False)
    assert abs(f["first_cut_s"] - 1.0) <= 0.15
    assert abs(f["longest_shot_s"] - 6.0) <= 0.3
    assert abs(f["cuts_per_10s"] - 2 / 1.2) <= 0.3
    assert abs(f["duration_s"] - 12.0) <= 0.2


def test_no_speech_returns_none(cut_video):
    assert measure_video(cut_video, whisper=False)["first_word_s"] is None


def test_lufs_finite(cut_video):
    assert math.isfinite(measure_video(cut_video, whisper=False)["lufs"])


def test_frame_features(cut_video):
    f = measure_video(cut_video, whisper=False)
    assert 0 <= f["first_frame_brightness"] <= 255
    # first frame red, last frame white: a poor loop
    assert f["loop_diff"] > 20
