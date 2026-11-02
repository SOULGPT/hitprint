import subprocess

import pytest


@pytest.fixture(scope="session")
def cut_video(tmp_path_factory):
    """12s 360x640 clip: color cuts at 1.0s and 6.0s, 440 Hz tone from 0.4s."""
    out = tmp_path_factory.mktemp("vid") / "cuts.mp4"
    flt = (
        "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v];"
        "[3:a]adelay=400:all=1,apad,atrim=0:12[a]"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-f", "lavfi", "-i", "color=c=red:s=360x640:r=30:d=1",
         "-f", "lavfi", "-i", "color=c=blue:s=360x640:r=30:d=5",
         "-f", "lavfi", "-i", "color=c=white:s=360x640:r=30:d=6",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=11.6",
         "-filter_complex", flt, "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(out)],
        check=True,
    )
    return str(out)
