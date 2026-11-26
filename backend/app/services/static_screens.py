"""Find frozen screens, slates and commercial cards in a video.

Ad breaks and "be right back" cards are mostly still pictures. Measuring
frame-to-frame luma change reliably separates them from real footage, so
clips can avoid dead air without OCR or a model. The scan is sampled at two
frames per second and cached on the video, making it cheap enough to run once
before analysis.
"""
from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

from ..config import settings

logger = logging.getLogger("fireclip.static_screens")

_PTS = re.compile(r"pts_time:([0-9.]+)")
_YAVG = re.compile(r"lavfi\.signalstats\.YAVG=([0-9.]+)")


def motion_map(path: str | Path, bucket_seconds: float = 2.0) -> list[tuple[float, float]]:
    """Return (time, mean luma difference) buckets, or an empty list on failure."""
    try:
        proc = subprocess.run(
            [
                settings.ffmpeg_bin,
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(path),
                "-vf",
                "fps=2,scale=320:-2,tblend=all_mode=difference,signalstats,metadata=print:file=-",
                "-an",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=900,
        )
    except (OSError, subprocess.SubprocessError):
        logger.warning("Static screen scan could not run", exc_info=True)
        return []
    times: list[float] = []
    values: list[float] = []
    at = 0.0
    for line in (proc.stdout or "").splitlines():
        point = _PTS.search(line)
        if point:
            at = float(point.group(1))
            continue
        value = _YAVG.search(line)
        if value:
            times.append(at)
            values.append(float(value.group(1)))
    if len(values) > 1:
        # The first blended frame compares against black, not the previous frame.
        times, values = times[1:], values[1:]
    if not values:
        return []
    buckets: dict[int, list[float]] = {}
    for time_value, value in zip(times, values):
        buckets.setdefault(int(time_value / bucket_seconds), []).append(value)
    return [
        (index * bucket_seconds, sum(bucket) / len(bucket))
        for index, bucket in sorted(buckets.items())
    ]


def detect_ranges(
    path: str | Path,
    *,
    bucket_seconds: float = 2.0,
    threshold: float | None = None,
    min_seconds: float | None = None,
) -> list[dict[str, int]]:
    """Stretches that stay almost completely still, in milliseconds."""
    threshold = settings.static_screen_threshold if threshold is None else threshold
    min_seconds = settings.static_screen_min_seconds if min_seconds is None else min_seconds
    pairs = motion_map(path, bucket_seconds)
    if not pairs:
        return []
    ranges: list[tuple[float, float]] = []
    start: float | None = None
    for at, motion in pairs:
        if motion < threshold:
            if start is None:
                start = at
        elif start is not None:
            ranges.append((start, at))
            start = None
    if start is not None:
        ranges.append((start, pairs[-1][0] + bucket_seconds))
    return [
        {"start_ms": int(round(left * 1000)), "end_ms": int(round(right * 1000))}
        for left, right in ranges
        if right - left >= min_seconds
    ]


def overlap_seconds(
    start_ms: int, end_ms: int, ranges: list[dict[str, int]]
) -> float:
    """How many seconds of a clip sit inside a still stretch."""
    total = 0.0
    for item in ranges or []:
        left = max(int(item.get("start_ms", 0)), start_ms)
        right = min(int(item.get("end_ms", 0)), end_ms)
        if right > left:
            total += (right - left) / 1000
    return total


def overlap_ratio(
    start_ms: int, end_ms: int, ranges: list[dict[str, int]]
) -> float:
    duration = max(0.001, (end_ms - start_ms) / 1000)
    return min(1.0, overlap_seconds(start_ms, end_ms, ranges) / duration)





