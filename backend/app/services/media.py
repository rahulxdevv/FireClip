"""FFmpeg/FFprobe wrappers: probing, thumbnails, audio extraction, execution."""
from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..config import settings

logger = logging.getLogger("fireclip.media")

ProgressCallback = Callable[[float], None]


class MediaError(RuntimeError):
    pass


@dataclass
class MediaInfo:
    duration: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 0.0
    has_audio: bool = False
    has_video: bool = False
    container: str = ""
    video_codec: str = ""
    audio_codec: str = ""
    bitrate: int = 0
    sample_rate: int = 0
    channels: int = 0
    raw: dict = field(default_factory=dict)


def binary_available(binary: str) -> bool:
    return shutil.which(binary) is not None


def ffmpeg_available() -> bool:
    return binary_available(settings.ffmpeg_bin)


def ffprobe_available() -> bool:
    return binary_available(settings.ffprobe_bin)


def ffmpeg_version() -> str:
    try:
        result = subprocess.run(
            [settings.ffmpeg_bin, "-version"], capture_output=True, text=True, timeout=15
        )
        return result.stdout.splitlines()[0] if result.stdout else "unknown"
    except Exception:
        return "unavailable"


def _to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _fps(rate: str | None) -> float:
    if not rate or "/" not in rate:
        return _to_float(rate)
    num, den = rate.split("/", 1)
    den_f = _to_float(den, 1) or 1
    return round(_to_float(num) / den_f, 3)


def probe(path: Path | str) -> MediaInfo:
    if not ffprobe_available():
        raise MediaError(
            "ffprobe is not installed. Install FFmpeg and set FFMPEG_BIN/FFPROBE_BIN."
        )
    cmd = [
        settings.ffprobe_bin,
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired as exc:
        raise MediaError("ffprobe timed out reading this file") from exc
    if result.returncode != 0:
        raise MediaError(f"Could not read media file: {result.stderr.strip()[:500]}")
    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise MediaError("ffprobe returned unreadable metadata") from exc

    info = MediaInfo(raw=data)
    fmt = data.get("format", {})
    info.duration = _to_float(fmt.get("duration"))
    info.container = (fmt.get("format_name") or "").split(",")[0]
    info.bitrate = int(_to_float(fmt.get("bit_rate")))
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video" and not info.has_video:
            info.has_video = True
            info.width = int(stream.get("width") or 0)
            info.height = int(stream.get("height") or 0)
            info.fps = _fps(stream.get("avg_frame_rate") or stream.get("r_frame_rate"))
            info.video_codec = stream.get("codec_name") or ""
            if not info.duration:
                info.duration = _to_float(stream.get("duration"))
        elif stream.get("codec_type") == "audio" and not info.has_audio:
            info.has_audio = True
            info.audio_codec = stream.get("codec_name") or ""
            info.sample_rate = int(_to_float(stream.get("sample_rate")))
            info.channels = int(_to_float(stream.get("channels")))
    if info.duration <= 0:
        raise MediaError("Could not determine media duration")
    return info


def run_ffmpeg(
    args: list[str],
    *,
    duration: float = 0.0,
    on_progress: ProgressCallback | None = None,
    on_tick: Callable[[], None] | None = None,
    timeout: int | None = None,
    cwd: Path | None = None,
) -> None:
    """Run FFmpeg, reporting progress from `-progress pipe:1` output."""
    cmd = [settings.ffmpeg_bin, "-hide_banner", "-nostdin", "-y", *args]
    logger.debug("Running: %s", " ".join(cmd))
    # stderr is merged into stdout: FFmpeg's encoder log is verbose enough to fill a
    # separate unread stderr pipe and deadlock the process.
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(cwd) if cwd else None,
    )
    started = time.monotonic()
    last_emit = 0.0
    from collections import deque

    log_tail: deque[str] = deque(maxlen=25)
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            if on_tick:
                on_tick()
            if timeout and time.monotonic() - started > timeout:
                proc.kill()
                raise MediaError("FFmpeg timed out")
            if line.startswith(("out_time_ms=", "out_time_us=")):
                value = _to_float(line.split("=", 1)[1])
                if duration > 0 and on_progress:
                    pct = min(99.0, max(0.0, (value / 1_000_000) / duration * 100))
                    now = time.monotonic()
                    if now - last_emit > 0.4:
                        on_progress(pct)
                        last_emit = now
            elif line.startswith("progress=end"):
                if on_progress:
                    on_progress(100.0)
            else:
                stripped = line.strip()
                if stripped:
                    log_tail.append(stripped)
        code = proc.wait()
    finally:
        if proc.poll() is None:
            proc.kill()
    if code != 0:
        detail = "\n".join(log_tail) or "FFmpeg failed with no output"
        raise MediaError(f"FFmpeg exited with code {code}: {detail[-1500:]}")


def extract_thumbnail(video: Path | str, output: Path, at_seconds: float = 1.0) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    args = [
        "-ss", f"{max(0.0, at_seconds):.3f}",
        "-i", str(video),
        "-frames:v", "1",
        "-vf", "scale=640:-2",
        "-q:v", "3",
        str(output),
    ]
    try:
        result = subprocess.run(
            [settings.ffmpeg_bin, "-hide_banner", "-nostdin", "-y", *args],
            capture_output=True,
            timeout=120,
        )
    except Exception as exc:
        raise MediaError(f"Thumbnail extraction failed: {exc}") from exc
    if result.returncode != 0 or not output.exists():
        # Retry at 0s (some streams cannot seek to 1s)
        subprocess.run(
            [settings.ffmpeg_bin, "-hide_banner", "-nostdin", "-y", "-i", str(video),
             "-frames:v", "1", "-vf", "scale=640:-2", "-q:v", "3", str(output)],
            capture_output=True,
            timeout=120,
        )
    if not output.exists():
        raise MediaError("Could not generate a thumbnail")
    return output


def extract_audio(video: Path | str, output: Path, sample_rate: int = 16000) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    args = [
        "-i", str(video),
        "-vn",
        "-ac", "1",
        "-ar", str(sample_rate),
        "-c:a", "pcm_s16le",
        str(output),
    ]
    result = subprocess.run(
        [settings.ffmpeg_bin, "-hide_banner", "-nostdin", "-y", *args],
        capture_output=True,
        timeout=1800,
    )
    if result.returncode != 0 or not output.exists():
        raise MediaError("Could not extract audio: " + result.stderr.decode(errors="replace")[-600:])
    return output


def parse_ffmpeg_progress_time(line: str) -> float:
    match = re.search(r"time=(\d+):(\d+):(\d+\.?\d*)", line)
    if not match:
        return 0.0
    h, m, s = match.groups()
    return int(h) * 3600 + int(m) * 60 + float(s)
