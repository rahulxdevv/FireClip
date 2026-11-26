"""Still-screen detection feeds the clip filter without requiring a video fixture."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.services import static_screens


def _fake_ffmpeg(monkeypatch, lines: list[str]) -> None:
    def run(*_args, **_kwargs):
        return SimpleNamespace(stdout="\n".join(lines), stderr="", returncode=0)

    monkeypatch.setattr(static_screens.subprocess, "run", run)


def test_motion_map_buckets_luma_difference(monkeypatch):
    _fake_ffmpeg(
        monkeypatch,
        [
            "frame:0 pts_time:0.0",
            "lavfi.signalstats.YAVG=35",
            "frame:1 pts_time:0.5",
            "lavfi.signalstats.YAVG=0.1",
            "frame:2 pts_time:1.0",
            "lavfi.signalstats.YAVG=0.2",
            "frame:3 pts_time:2.5",
            "lavfi.signalstats.YAVG=12.0",
        ],
    )
    pairs = static_screens.motion_map(Path("video.mp4"), bucket_seconds=2.0)
    assert len(pairs) == 2
    assert pairs[0][0] == 0.0
    assert round(pairs[0][1], 2) == 0.15
    assert pairs[1] == (2.0, 12.0)


def test_detect_ranges_keeps_only_long_still_stretches(monkeypatch):
    lines: list[str] = ["frame:0 pts_time:0.0", "lavfi.signalstats.YAVG=40"]
    # 0.5s through 5.5s is still; 6.5s through 12.5s is also still.
    for index in range(1, 26):
        at = index * 0.5
        motion = 0.1 if at <= 5.5 or at >= 6.5 else 14.0
        lines += [f"frame:{index} pts_time:{at}", f"lavfi.signalstats.YAVG={motion}"]
    _fake_ffmpeg(monkeypatch, lines)
    ranges = static_screens.detect_ranges(
        Path("video.mp4"), bucket_seconds=1.0, threshold=0.4, min_seconds=3.0
    )
    assert ranges
    assert all(item["end_ms"] - item["start_ms"] >= 3000 for item in ranges)


def test_overlap_ratio_measures_share_inside_still_ranges():
    ranges = [{"start_ms": 10_000, "end_ms": 20_000}]
    assert static_screens.overlap_seconds(5_000, 15_000, ranges) == 5.0
    assert static_screens.overlap_ratio(5_000, 15_000, ranges) == 0.5
    assert static_screens.overlap_ratio(0, 5_000, ranges) == 0.0

