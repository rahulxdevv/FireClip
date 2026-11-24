"""FFmpeg rendering pipeline.

Composes a single filter graph: aspect-ratio crop, burned captions, text and
image overlays, music mixing, loudness normalization, then encodes the preset
format. Runs inside a worker, never inside a request.
"""
from __future__ import annotations

import logging
import shutil
import time
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..config import settings
from ..models import EditingProject, SourceVideo
from ..storage import build_key, get_storage
from . import captions as caption_service
from .media import MediaError, extract_thumbnail, probe, run_ffmpeg
from .transcription import SegmentData

logger = logging.getLogger("fireclip.render")

PRESETS: dict[str, tuple[int, int, str]] = {
    "tiktok": (1080, 1920, "9:16"),
    "reels": (1080, 1920, "9:16"),
    "shorts": (1080, 1920, "9:16"),
    "square": (1080, 1080, "1:1"),
    "landscape": (1920, 1080, "16:9"),
    "portrait": (1080, 1350, "4:5"),
    "custom": (1080, 1920, "9:16"),
}

ASPECT_SIZES = {
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "16:9": (1920, 1080),
    "4:5": (1080, 1350),
}

_hw_encoders: bool | None = None


class RenderError(RuntimeError):
    pass


@dataclass
class RenderResult:
    output_key: str
    thumbnail_key: str
    size_bytes: int
    width: int
    height: int
    duration_ms: int
    render_seconds: float


def _even(value: int) -> int:
    return max(2, int(value) - int(value) % 2)


def _has_nvenc() -> bool:
    global _hw_encoders
    if _hw_encoders is not None:
        return _hw_encoders
    import subprocess

    try:
        result = subprocess.run(
            [settings.ffmpeg_bin, "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=20
        )
        _hw_encoders = "h264_nvenc" in (result.stdout or "")
    except Exception:
        _hw_encoders = False
    return _hw_encoders


def output_dimensions(
    project: EditingProject, preset: str, width: int | None, height: int | None, fmt: str
) -> tuple[int, int]:
    if width and height:
        return _even(min(width, 3840)), _even(min(height, 3840))
    if preset == "custom":
        return _even(project.width), _even(project.height)
    preset_width, preset_height, _ratio = PRESETS.get(preset, PRESETS["tiktok"])
    return _even(preset_width), _even(preset_height)


def _style_for(project: EditingProject, style_row) -> dict:
    base = dict(caption_service.DEFAULT_STYLE)
    if style_row is not None:
        base.update(style_row.config or {})
    base.update(project.caption_overrides or {})
    return base


def build_filter_graph(
    project: EditingProject,
    *,
    width: int,
    height: int,
    workdir: Path,
    has_audio: bool,
    music_index: int | None,
    image_indices: list[tuple[int, dict]],
    source_audio_index: int,
    duration: float,
) -> tuple[list[str], str]:
    """Return (filters, final_video_label). Audio labels are appended by caller."""
    focus_x = min(1.0, max(0.0, project.focus_x if project.focus_x is not None else 0.5))
    focus_y = min(1.0, max(0.0, project.focus_y if project.focus_y is not None else 0.5))
    layout = dict(project.layout or {})
    mode = str(layout.get("mode", "fill"))
    if mode == "fit":
        filters = [
            "[0:v]split=2[bg0][fg0]",
            f"[bg0]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},boxblur=24:2,setsar=1[bg]",
            f"[fg0]scale={width}:{height}:force_original_aspect_ratio=decrease,setsar=1[fg]",
            "[bg][fg]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2,format=yuv420p[base]",
        ]
    elif mode == "facecam":
        cam_x = min(0.82, max(0.0, float(layout.get("camera_x", 0.62))))
        cam_y = min(0.82, max(0.0, float(layout.get("camera_y", 0.55))))
        cam_w = min(1.0 - cam_x, max(0.18, float(layout.get("camera_w", 0.38))))
        cam_h = min(1.0 - cam_y, max(0.18, float(layout.get("camera_h", 0.42))))
        size = min(0.9, max(0.15, float(layout.get("size", 0.4))))
        position = str(layout.get("position", "bottom_right"))
        if position == "bottom_half":
            pip_width = _even(width)
            pip_height = _even(int(height * 0.5))
            pos_x, pos_y = 0.0, 1.0
            camera_filter = (
                f"[cam0]scale={pip_width}:{pip_height}:force_original_aspect_ratio=increase,"
                f"crop={pip_width}:{pip_height},setsar=1[cam]"
            )
        else:
            if position == "manual":
                pos_x = min(1.0, max(0.0, float(layout.get("x", 0.96))))
                pos_y = min(1.0, max(0.0, float(layout.get("y", 0.96))))
            else:
                pos_x = 0.04 if "left" in position else 0.96
                pos_y = 0.04 if "top" in position else 0.96
                if position == "bottom_center":
                    pos_x, pos_y = 0.5, 0.96
            pip_width = _even(int(width * size))
            camera_filter = (
                f"[cam0]crop=iw*{cam_w:.4f}:ih*{cam_h:.4f}:iw*{cam_x:.4f}:ih*{cam_y:.4f},"
                f"scale={pip_width}:-2,setsar=1[cam]"
            )
        filters = [
            "[0:v]split=2[bg0][cam0]",
            f"[bg0]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},boxblur=18:2,setsar=1[bg]",
            camera_filter,
            f"[bg][cam]overlay=x=(main_w-overlay_w)*{pos_x:.4f}:y=(main_h-overlay_h)*{pos_y:.4f}:"
            "shortest=1,format=yuv420p[base]",
        ]
    else:
        filters = [
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}:(in_w-{width})*{focus_x:.5f}:(in_h-{height})*{focus_y:.5f},"
            f"setsar=1,format=yuv420p[base]"
        ]
    current = "base"
    caption_file = workdir / "captions.ass"
    if project.captions_enabled and caption_file.exists():
        filters.append(f"[{current}]ass=captions.ass[cap]")
        current = "cap"
    overlay_file = workdir / "overlays.ass"
    if overlay_file.exists() and overlay_file.stat().st_size > 400:
        filters.append(f"[{current}]ass=overlays.ass[txt]")
        current = "txt"

    for idx, (input_index, overlay) in enumerate(image_indices):
        size_fraction = max(0.05, min(0.9, float(overlay.get("width", 0.28))))
        target_w = _even(int(width * size_fraction))
        label = f"img{idx}"
        filters.append(f"[{input_index}:v]scale={target_w}:-2[{label}]")
        x_expr = f"(main_w-overlay_w)*{min(1.0, max(0.0, float(overlay.get('x', 0.5)))):.4f}"
        y_expr = f"(main_h-overlay_h)*{min(1.0, max(0.0, float(overlay.get('y', 0.12)))):.4f}"
        raw_start = float(overlay.get("start_ms", 0))
        raw_end = float(overlay.get("end_ms", duration * 1000))
        # Explicitly marked campaign overlays use source timestamps; editor overlays are clip-relative.
        if overlay.get("source_ms"):
            trim_start = float(project.trim_start_ms or 0)
            raw_start -= trim_start
            raw_end -= trim_start
        start = max(0.0, raw_start / 1000)
        end = min(duration, raw_end / 1000)
        nxt = f"ov{idx}"
        filters.append(
            f"[{current}][{label}]overlay=x={x_expr}:y={y_expr}:"
            f"enable='between(t,{start:.3f},{end:.3f})':eof_action=pass[{nxt}]"
        )
        current = nxt

    audio = project.audio or {}
    fade_in = max(0.0, min(2.0, float(audio.get("fade_in", 0.0) or 0.0)))
    fade_out = max(0.0, min(2.0, float(audio.get("fade_out", 0.0) or 0.0)))
    if fade_in > 0:
        filters.append(f"[{current}]fade=t=in:st=0:d={fade_in:.2f}[fin]")
        current = "fin"
    if fade_out > 0:
        filters.append(f"[{current}]fade=t=out:st={max(0.0, duration - fade_out):.3f}:d={fade_out:.2f}[fout]")
        current = "fout"

    # Audio graph
    volume = 0.0 if audio.get("muted") else max(0.0, min(2.0, float(audio.get("volume", 1.0))))
    base_audio_label = source_audio_index
    if music_index is not None:
        music = project.music or {}
        music_volume = max(0.0, min(2.0, float(music.get("volume", 0.22))))
        filters.append(
            f"[{music_index}:a]atrim=0:{duration:.3f},asetpts=PTS-STARTPTS,"
            f"volume={music_volume:.3f}[mus]"
        )
        if has_audio and volume > 0:
            filters.append(f"[{base_audio_label}:a]volume={volume:.3f}[voice]")
            filters.append(
                "[voice][mus]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[mixed]"
            )
        else:
            filters.append("[mus]anull[mixed]")
        filters.append(
            f"[mixed]loudnorm=I={settings.loudness_target}:TP=-1.5:LRA=11,"
            f"aresample=48000,alimiter=limit=0.95[aout]"
        )
    elif has_audio:
        filters.append(
            f"[{base_audio_label}:a]volume={volume:.3f},"
            f"loudnorm=I={settings.loudness_target}:TP=-1.5:LRA=11,"
            f"aresample=48000[aout]"
        )
    else:
        filters.append(
            f"[{base_audio_label}:a]loudnorm=I={settings.loudness_target}:TP=-1.5:LRA=11,"
            f"aresample=48000[aout]"
        )
    if fade_out > 0:
        filters[-1] = filters[-1].replace("[aout]", "[anofade]")
        filters.append(f"[anofade]afade=t=out:st={max(0.0, duration - fade_out):.3f}:d={fade_out:.2f}[aout]")
    if fade_in > 0:
        # afade in is applied before the limiter by inserting after resample.
        filters[-1] = filters[-1].replace("[aout]", "[afin]")
        filters.append(f"[afin]afade=t=in:st=0:d={fade_in:.2f}[aout]")
    return filters, current


def render_project(
    project: EditingProject,
    video: SourceVideo,
    segments: list[SegmentData],
    caption_style_row,
    *,
    job_id: str,
    preset: str,
    fmt: str,
    width_override: int | None = None,
    height_override: int | None = None,
    on_progress: Callable[[float], None] | None = None,
    on_tick: Callable[[], None] | None = None,
) -> RenderResult:
    if not video.storage_key:
        raise RenderError("Source video has no stored file")
    storage = get_storage()
    width, height = output_dimensions(project, preset, width_override, height_override, fmt)
    start_ms = max(0, int(project.trim_start_ms))
    end_ms = int(project.trim_end_ms or 0)
    if end_ms <= start_ms:
        raise RenderError("Clip end must be after its start")
    duration_ms = end_ms - start_ms
    if duration_ms < 500:
        raise RenderError("Clip is shorter than 0.5 seconds")
    if video.duration_seconds:
        duration_ms = min(duration_ms, int(video.duration_seconds * 1000) - start_ms)
    if duration_ms < 500:
        raise RenderError("Clip range is outside the video")
    duration = duration_ms / 1000
    workdir = settings.data_dir / "tmp" / f"render-{job_id}"
    if workdir.exists():
        shutil.rmtree(workdir, ignore_errors=True)
    workdir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    logger.info(
        "Render start job=%s preset=%s format=%s size=%sx%s duration=%.2fs",
        job_id, preset, fmt, width, height, duration,
    )

    with ExitStack() as stack:
        source_path = stack.enter_context(storage.temp_copy(video.storage_key))
        style = _style_for(project, caption_style_row)
        caption_service.plan_captions(
            segments,
            style,
            project.overlays or [],
            clip_start_ms=start_ms,
            clip_end_ms=start_ms + duration_ms,
            width=width,
            height=height,
            workdir=workdir,
            captions_enabled=bool(project.captions_enabled),
        )

        extra_inputs: list[list[str]] = []
        image_indices: list[tuple[int, dict]] = []
        input_cursor = 1
        for overlay in project.overlays or []:
            if str(overlay.get("type", "text")) != "image" or not overlay.get("asset_key"):
                continue
            path = stack.enter_context(storage.temp_copy(overlay["asset_key"]))
            extra_inputs.append(["-loop", "1", "-i", str(path)])
            image_indices.append((input_cursor, overlay))
            input_cursor += 1

        music_index = None
        if project.music and project.music.get("asset_key") and storage.exists(project.music["asset_key"]):
            music_path = stack.enter_context(storage.temp_copy(project.music["asset_key"]))
            extra_inputs.append(["-stream_loop", "-1", "-i", str(music_path)])
            music_index = input_cursor
            input_cursor += 1

        source_audio_index = 0
        if not video.has_audio:
            # Synthesized silence keeps the filter graph and output audio track predictable.
            extra_inputs.append(
                ["-f", "lavfi", "-t", f"{duration:.3f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
            )
            source_audio_index = input_cursor
            input_cursor += 1

        filters, final_label = build_filter_graph(
            project,
            width=width,
            height=height,
            workdir=workdir,
            has_audio=video.has_audio,
            music_index=music_index,
            image_indices=image_indices,
            source_audio_index=source_audio_index,
            duration=duration,
        )
        output_path = workdir / f"output.{fmt}"
        filters.append(f"[{final_label}]null[vout]")

        encode_args: list[str]
        if fmt == "webm":
            encode_args = [
                "-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0", "-row-mt", "1",
                "-c:a", "libopus", "-b:a", "128k",
            ]
        else:
            if settings.hwaccel == "nvenc" and _has_nvenc():
                video_args = ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23", "-pix_fmt", "yuv420p"]
            else:
                crf = max(0, min(51, settings.render_crf))
                video_args = [
                    "-c:v", "libx264",
                    "-preset", settings.render_x264_preset,
                    "-crf", str(crf),
                    "-pix_fmt", "yuv420p",
                ]
            encode_args = [*video_args, "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
            if fmt == "mp4":
                encode_args += ["-movflags", "+faststart"]
        if fmt == "mov":
            encode_args += ["-f", "mov"]

        args: list[str] = [
            "-ss", f"{start_ms / 1000:.3f}",
            "-t", f"{duration:.3f}",
            "-i", str(source_path),
        ]
        for extra in extra_inputs:
            args.extend(extra)
        args.extend(
            [
                "-filter_complex", ";".join(filters),
                "-map", "[vout]",
                "-map", "[aout]",
                "-t", f"{duration:.3f}",
                *encode_args,
                "-progress", "pipe:1",
                str(output_path),
            ]
        )

        def report(pct: float) -> None:
            if on_progress:
                on_progress(min(95.0, pct * 0.93))

        try:
            run_ffmpeg(
                args,
                duration=duration,
                on_progress=report,
                on_tick=on_tick,
                timeout=max(600, int(duration * 30)),
                cwd=workdir,
            )
        except MediaError as exc:
            raise RenderError(str(exc)) from exc

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RenderError("FFmpeg did not produce an output file")

        thumb_path = workdir / "thumb.jpg"
        try:
            extract_thumbnail(output_path, thumb_path, at_seconds=min(0.5, duration / 3))
        except MediaError:
            thumb_path = None  # type: ignore[assignment]

        if on_progress:
            on_progress(96.0)
        info = probe(output_path)
        size = output_path.stat().st_size
        output_key = build_key("renders", project.workspace_id, f"{job_id}.{fmt}")
        storage.put_file(output_path, output_key, _content_type(fmt))
        thumb_key = ""
        if thumb_path and thumb_path.exists():
            thumb_key = build_key("renders", project.workspace_id, f"{job_id}.jpg")
            storage.put_file(thumb_path, thumb_key, "image/jpeg")

    elapsed = time.monotonic() - started
    logger.info(
        "Render done job=%s size=%s bytes encode=%.2fs",
        job_id, size, elapsed,
    )
    if on_progress:
        on_progress(100.0)
    return RenderResult(
        output_key=output_key,
        thumbnail_key=thumb_key,
        size_bytes=size,
        width=info.width or width,
        height=info.height or height,
        duration_ms=int(info.duration * 1000) or duration_ms,
        render_seconds=round(elapsed, 2),
    )


def _content_type(fmt: str) -> str:
    return {
        "mp4": "video/mp4",
        "mov": "video/quicktime",
        "webm": "video/webm",
    }.get(fmt, "video/mp4")


def cleanup_temp(job_id: str) -> None:
    workdir = settings.data_dir / "tmp" / f"render-{job_id}"
    if workdir.exists():
        shutil.rmtree(workdir, ignore_errors=True)
