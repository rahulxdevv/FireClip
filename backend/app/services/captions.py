"""Caption generation.

Captions are authored as ASS so libass can burn word-level karaoke highlighting,
boxes, outlines and positioned text overlays without drawtext escaping pain.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .transcription import SegmentData

DEFAULT_STYLE: dict = {
    "font": "Arial",
    "font_size": 64,
    "text_color": "#ffffff",
    "highlight_color": "#ff6a1f",
    "outline_color": "#0b0b0f",
    "outline_width": 4,
    "shadow": 1,
    "bold": True,
    "uppercase": False,
    "position": "bottom",
    "max_words_per_line": 4,
    "max_chars_per_line": 28,
    "animation": "karaoke",
    "highlight_mode": "word",
    "box": True,
    "box_opacity": 0.28,
    "margin_v": 110,
}

BUILTIN_STYLES = [
    (
        "Fire",
        {
            **DEFAULT_STYLE,
            "highlight_color": "#ff6a1f",
            "uppercase": True,
            "box": False,
            "outline_width": 5,
        },
    ),
    (
        "Clean",
        {
            **DEFAULT_STYLE,
            "font": "Arial",
            "font_size": 56,
            "text_color": "#f7f7fb",
            "highlight_color": "#ffb347",
            "outline_width": 2,
            "box": True,
            "box_opacity": 0.55,
            "animation": "fade",
            "uppercase": False,
        },
    ),
    (
        "Boxed",
        {
            **DEFAULT_STYLE,
            "font": "Arial",
            "font_size": 58,
            "text_color": "#0b0b0f",
            "highlight_color": "#ff6a1f",
            "outline_color": "#ffffff",
            "outline_width": 0,
            "box": True,
            "box_opacity": 1.0,
            "animation": "none",
            "uppercase": True,
        },
    ),
    (
        "Minimal",
        {
            **DEFAULT_STYLE,
            "font_size": 48,
            "text_color": "#ffffff",
            "highlight_color": "#ffffff",
            "outline_width": 0,
            "box": True,
            "box_opacity": 0.65,
            "animation": "none",
            "highlight_mode": "none",
            "uppercase": False,
        },
    ),
]


def _ass_color(hex_color: str, alpha: float = 0.0, *, box_opacity: float | None = None) -> str:
    value = (hex_color or "#ffffff").lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        value = "ffffff"
    r, g, b = value[0:2], value[2:4], value[4:6]
    if box_opacity is not None:
        alpha_fraction = 1 - max(0.0, min(1.0, box_opacity))
    else:
        alpha_fraction = max(0.0, min(1.0, alpha))
    ass_alpha = f"{int(round(alpha_fraction * 255)):02X}"
    return f"&H{ass_alpha}{b}{g}{r}"


def ass_time(ms: float) -> str:
    ms = max(0, int(ms))
    hours, rem = divmod(ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1000)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{millis // 10:02d}"


def _escape(text: str) -> str:
    text = text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")
    text = text.replace("\r", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", text).strip()


def _wrap_words(words: list[dict], style: dict) -> list[list[dict]]:
    max_words = max(1, int(style.get("max_words_per_line", 4)))
    max_chars = max(8, int(style.get("max_chars_per_line", 28)))
    lines: list[list[dict]] = []
    current: list[dict] = []
    length = 0
    for word in words:
        token = word["word"]
        if current and (len(current) >= max_words or length + len(token) + 1 > max_chars):
            lines.append(current)
            current = []
            length = 0
        current.append(word)
        length += len(token) + 1
    if current:
        lines.append(current)
    return lines


def _group_words(segments: list[SegmentData], clip_start: int, clip_end: int) -> list[dict]:
    words: list[dict] = []
    for segment in segments:
        if segment.end_ms <= clip_start or segment.start_ms >= clip_end:
            continue
        segment_words = segment.words or []
        if not segment_words:
            text_words = segment.text.split()
            if not text_words:
                continue
            duration = max(1, segment.end_ms - segment.start_ms)
            per = duration / len(text_words)
            segment_words = [
                {
                    "word": token,
                    "start_ms": int(segment.start_ms + i * per),
                    "end_ms": int(segment.start_ms + (i + 1) * per),
                }
                for i, token in enumerate(text_words)
            ]
        for word in segment_words:
            start = int(word.get("start_ms", segment.start_ms))
            end = int(word.get("end_ms", start + 250))
            if end <= clip_start or start >= clip_end:
                continue
            words.append(
                {
                    "word": str(word.get("word", "")).strip(),
                    "start_ms": max(clip_start, start) - clip_start,
                    "end_ms": min(clip_end, end) - clip_start,
                }
            )
    return [w for w in words if w["word"]]


def build_caption_ass(
    segments: list[SegmentData],
    style: dict,
    *,
    clip_start_ms: int,
    clip_end_ms: int,
    width: int,
    height: int,
) -> str:
    merged = {**DEFAULT_STYLE, **(style or {})}
    scale = height / 1920 if height else 1.0
    font_size = max(18, int(int(merged.get("font_size", 64)) * scale))
    outline = max(0, int(int(merged.get("outline_width", 4)) * scale))
    alignment = {"bottom": 2, "middle": 5, "top": 8}.get(str(merged.get("position", "bottom")), 2)
    margin_v = max(10, int(int(merged.get("margin_v", 110)) * scale))

    primary = _ass_color(merged.get("highlight_color", "#ff6a1f"))
    secondary = _ass_color(merged.get("text_color", "#ffffff"))
    outline_color = _ass_color(merged.get("outline_color", "#0b0b0f"))
    if merged.get("box"):
        back_color = _ass_color(merged.get("outline_color", "#0b0b0f"), box_opacity=float(merged.get("box_opacity", 0.28)))
        border_style = 3
        outline = 0
    else:
        back_color = _ass_color("#000000", alpha=1.0)
        border_style = 1

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Fire,{merged.get('font', 'Arial')},{font_size},{primary},{secondary},{outline_color},{back_color},{1 if merged.get('bold') else 0},0,0,0,100,100,0,0,{border_style},{outline},{int(merged.get('shadow', 1))},{alignment},40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    words = _group_words(segments, clip_start_ms, clip_end_ms)
    if not words:
        return header
    lines = _wrap_words(words, merged)
    highlight_mode = str(merged.get("highlight_mode", "word"))
    uppercase = bool(merged.get("uppercase", False))
    animation = str(merged.get("animation", "karaoke"))

    events: list[str] = []
    previous_end = 0.0
    for index, line in enumerate(lines):
        line_start = max(previous_end, float(line[0]["start_ms"]))
        line_end = float(line[-1]["end_ms"])
        if index + 1 < len(lines):
            line_end = min(line_end, float(lines[index + 1][0]["start_ms"]))
        line_end = max(line_start + 180, line_end)
        previous_end = line_end
        pieces: list[str] = []
        fade = ""
        if animation == "fade":
            fade = r"{\fad(120,120)}"
        for word in line:
            token = _escape(word["word"])
            if uppercase:
                token = token.upper()
            duration_cs = max(8, int((word["end_ms"] - word["start_ms"]) / 10))
            if highlight_mode == "word" and animation == "karaoke":
                pieces.append(f"{{\\kf{duration_cs}}}{token}")
            else:
                pieces.append(token)
        text = fade + " ".join(pieces) if fade else " ".join(pieces)
        events.append(
            f"Dialogue: 0,{ass_time(line_start)},{ass_time(line_end)},Fire,,0,0,0,,{text}"
        )
    return header + "\n".join(events) + "\n"


def build_overlay_ass(
    overlays: list[dict],
    *,
    clip_start_ms: int,
    clip_end_ms: int,
    width: int,
    height: int,
) -> str:
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Overlay,Arial,48,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,0,0,5,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for overlay in overlays or []:
        if str(overlay.get("type", "text")) != "text":
            continue
        text = _escape(str(overlay.get("text", "")))
        if not text:
            continue
        start = max(0, int(overlay.get("start_ms", 0)) - clip_start_ms)
        end = min(clip_end_ms - clip_start_ms, int(overlay.get("end_ms", clip_end_ms)) - clip_start_ms)
        if end <= start:
            continue
        x = float(overlay.get("x", 0.5))
        y = float(overlay.get("y", 0.18))
        size = max(14, int(float(overlay.get("font_size", 56)) * (height / 1920 if height else 1)))
        color = _ass_color(str(overlay.get("color", "#ffffff")))
        style_bits = (
            f"\\an5\\pos({int(width * x)},{int(height * y)})\\fs{size}\\c{color}"
            f"\\bord{max(0, int(overlay.get('outline_width', 3)))}\\shad0"
        )
        if overlay.get("background"):
            box = _ass_color(str(overlay.get("background")), box_opacity=float(overlay.get("background_opacity", 0.5)))
            style_bits += f"\\bord0\\shad0\\3c{box}\\4c{box}"
        fade = "\\fad(150,150)" if overlay.get("animation", "fade") == "fade" else ""
        events.append(
            f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Overlay,,0,0,0,,{{{style_bits}{fade}}}{text}"
        )
    return header + "\n".join(events) + "\n"


def write_ass(content: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


@dataclass
class CaptionRenderPlan:
    caption_file: Path | None
    overlay_file: Path | None
    font_size: int


def plan_captions(
    segments: list[SegmentData],
    style: dict,
    overlays: list[dict],
    *,
    clip_start_ms: int,
    clip_end_ms: int,
    width: int,
    height: int,
    workdir: Path,
    captions_enabled: bool = True,
) -> CaptionRenderPlan:
    captions_path = None
    overlays_path = None
    if captions_enabled and segments:
        content = build_caption_ass(
            segments,
            style,
            clip_start_ms=clip_start_ms,
            clip_end_ms=clip_end_ms,
            width=width,
            height=height,
        )
        captions_path = write_ass(content, workdir / "captions.ass")
    if overlays:
        overlaid = build_overlay_ass(
            overlays,
            clip_start_ms=clip_start_ms,
            clip_end_ms=clip_end_ms,
            width=width,
            height=height,
        )
        overlays_path = write_ass(overlaid, workdir / "overlays.ass")
    return CaptionRenderPlan(
        caption_file=captions_path,
        overlay_file=overlays_path,
        font_size=int(style.get("font_size", 64)),
    )
