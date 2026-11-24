"""Video source detection and ingestion (uploads + supported URLs).

URL downloads use yt-dlp when installed. We only expose public, permitted
content: authentication cookies, DRM bypass and paywall circumvention are not
implemented, by design.
"""
from __future__ import annotations

import ipaddress
import json
import logging
import re
import shutil
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import httpx

from ..config import settings
from .media import MediaError

logger = logging.getLogger("fireclip.sources")

ProgressCallback = Callable[[float], None]

YOUTUBE_RE = re.compile(r"(youtube\.com|youtu\.be)", re.I)
TWITCH_RE = re.compile(r"twitch\.tv", re.I)
KICK_RE = re.compile(r"kick\.com", re.I)


class SourceError(RuntimeError):
    pass


@dataclass
class SourceInfo:
    platform: str
    title: str = ""
    duration: float = 0.0
    thumbnail_url: str = ""
    description: str = ""
    uploader: str = ""


def detect_platform(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if YOUTUBE_RE.search(host):
        return "youtube"
    if TWITCH_RE.search(host):
        return "twitch"
    if KICK_RE.search(host):
        return "kick"
    return "direct"


def _is_public_host(hostname: str) -> bool:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True


def validate_url(url: str, allow_private: bool = False) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise SourceError("Only http(s) URLs are supported")
    if not parsed.hostname:
        raise SourceError("URL has no hostname")
    if not allow_private and not _is_public_host(parsed.hostname):
        raise SourceError("This host is not publicly reachable. Local/private addresses are blocked.")
    if len(url) > 2000:
        raise SourceError("URL is too long")
    return url.strip()


def ytdlp_available() -> bool:
    return shutil.which(settings.ytdlp_bin) is not None or _ytdlp_module_available()


def _ytdlp_module_available() -> bool:
    try:
        import yt_dlp  # noqa: F401

        return True
    except Exception:
        return False


def _ytdlp_command(*args: str) -> list[str]:
    if shutil.which(settings.ytdlp_bin):
        return [settings.ytdlp_bin, *args]
    return ["python", "-m", "yt_dlp", *args]


def fetch_live_state(url: str) -> bool | None:
    """Ask yt-dlp whether a public URL is broadcasting right now.

    Returns True/False when the platform reports a definitive state and None
    when it cannot be determined (private, geo-blocked, unsupported page).
    """
    if not ytdlp_available():
        return None
    try:
        result = subprocess.run(
            _ytdlp_command("--simulate", "--no-warnings", "--no-playlist", "--print", "%(is_live)s", url),
            capture_output=True,
            text=True,
            timeout=45,
        )
    except subprocess.TimeoutExpired:
        logger.warning("Live state check timed out for %s", url)
        return None
    if result.returncode != 0:
        logger.info("Live state check failed for %s: %s", url, _clean_ytdlp_error(result.stderr))
        return None
    value = (result.stdout or "").strip().splitlines()
    if not value:
        return None
    state = value[-1].strip().lower()
    if state in {"true", "live", "is_live"}:
        return True
    if state in {"false", "offline", "not_live"}:
        return False
    return None


def fetch_source_info(url: str) -> SourceInfo:
    platform = detect_platform(url)
    validate_url(url)
    if platform in {"youtube", "twitch", "kick"}:
        if not ytdlp_available():
            raise SourceError(
                "URL import for this platform requires yt-dlp. Install it with "
                "`pip install yt-dlp` (or set YTDLP_BIN) and retry."
            )
        try:
            result = subprocess.run(
                _ytdlp_command("--dump-single-json", "--no-playlist", "--skip-download", url),
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired as exc:
            raise SourceError("Timed out while reading video metadata") from exc
        if result.returncode != 0:
            raise SourceError(_clean_ytdlp_error(result.stderr))
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise SourceError("Could not parse metadata returned by yt-dlp") from exc
        duration = float(data.get("duration") or 0)
        if duration and duration > settings.max_import_minutes * 60:
            raise SourceError(
                f"Video is longer than the {settings.max_import_minutes} minute import limit"
            )
        return SourceInfo(
            platform=platform,
            title=(data.get("title") or "Imported video")[:300],
            duration=duration,
            thumbnail_url=data.get("thumbnail") or "",
            description=(data.get("description") or "")[:4000],
            uploader=(data.get("uploader") or "")[:200],
        )
    return SourceInfo(platform="direct", title=Path(urlparse(url).path).stem or "Imported video")


def _clean_ytdlp_error(stderr: str) -> str:
    lines = [line for line in stderr.strip().splitlines() if line.strip()]
    tail = lines[-3:] if lines else []
    message = " ".join(tail)
    message = re.sub(r"\x1b\[[0-9;]*m", "", message)
    return f"Import failed: {message[:600]}" if message else "Import failed (yt-dlp error)"


def download_video(
    url: str,
    destination: Path,
    *,
    on_progress: ProgressCallback | None = None,
    cancel_check: Callable[[], None] | None = None,
) -> Path:
    platform = detect_platform(url)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if platform == "direct":
        return _download_direct(url, destination, on_progress, cancel_check)
    if not ytdlp_available():
        raise SourceError("yt-dlp is required for this platform")
    template = "PROGRESS|%(progress.downloaded_bytes)s|%(progress.total_bytes)s|%(progress.total_bytes_estimate)s"
    args = [
        "-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b",
        "--merge-output-format", "mp4",
        "--no-playlist",
        "--newline",
        "--no-warnings",
        "--progress-template", template,
        "-o", str(destination),
        url,
    ]
    proc = subprocess.Popen(
        _ytdlp_command(*args),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            if cancel_check:
                cancel_check()
            if line.startswith("PROGRESS|"):
                parts = line.strip().split("|")
                downloaded = float(parts[1]) if len(parts) > 1 and parts[1] not in {"NA", "None"} else 0
                total_raw = parts[2] if len(parts) > 2 else "NA"
                if total_raw in {"NA", "None", ""} and len(parts) > 3:
                    total_raw = parts[3]
                total = float(total_raw) if total_raw not in {"NA", "None", ""} else 0
                if total > 0 and on_progress:
                    on_progress(min(99.0, downloaded / total * 100))
        stderr = proc.stderr.read() if proc.stderr else ""
        code = proc.wait()
    finally:
        if proc.poll() is None:
            proc.kill()
    if code != 0:
        raise SourceError(_clean_ytdlp_error(stderr))
    if not destination.exists():
        # yt-dlp may append a container extension
        candidates = list(destination.parent.glob(destination.name + "*"))
        if not candidates:
            raise SourceError("Download finished but no file was produced")
        candidates[0].rename(destination)
    if on_progress:
        on_progress(100.0)
    return destination


def _download_direct(
    url: str,
    destination: Path,
    on_progress: ProgressCallback | None,
    cancel_check: Callable[[], None] | None,
) -> Path:
    limit = settings.max_upload_mb * 1024 * 1024
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=60.0) as response:
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if content_type and not (
                content_type.startswith("video/")
                or content_type.startswith("audio/")
                or content_type == "application/octet-stream"
            ):
                raise SourceError(f"URL did not return a video (content-type: {content_type})")
            total = int(response.headers.get("content-length") or 0)
            if total > limit:
                raise SourceError("File exceeds the configured maximum size")
            received = 0
            started = time.monotonic()
            with open(destination, "wb") as handle:
                for chunk in response.iter_bytes(1024 * 512):
                    if cancel_check:
                        cancel_check()
                    handle.write(chunk)
                    received += len(chunk)
                    if received > limit:
                        raise SourceError("File exceeds the configured maximum size")
                    if on_progress and total:
                        on_progress(min(99.0, received / total * 100))
                    if time.monotonic() - started > 3600:
                        raise SourceError("Download timed out")
    except httpx.HTTPError as exc:
        raise SourceError(f"Download failed: {exc}") from exc
    if not destination.exists() or destination.stat().st_size == 0:
        raise SourceError("Downloaded file is empty")
    if on_progress:
        on_progress(100.0)
    return destination


def guess_mime(path: Path) -> str:
    import mimetypes

    return mimetypes.guess_type(str(path))[0] or "video/mp4"


def audio_only(path: Path) -> bool:
    return path.suffix.lower() in settings.allowed_audio_ext


def assert_media_extension(filename: str) -> None:
    suffix = Path(filename).suffix.lower()
    allowed = set(settings.allowed_video_ext) | set(settings.allowed_audio_ext)
    if suffix not in allowed:
        raise SourceError(f"Unsupported file type '{suffix or 'unknown'}'")
