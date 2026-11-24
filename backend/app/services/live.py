"""Background live-stream automation.

The monitor only checks public URLs. It records when a stream is actually
live, using the same yt-dlp capture path as a manual recording. No platform
authentication, DRM or paywall bypass is attempted.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select

from ..database import session_scope
from ..jobs import create_pipeline_job, enqueue
from ..models import Campaign, LiveStream, SourceVideo
from . import sources

logger = logging.getLogger("fireclip.live")

CHECK_INTERVAL_SECONDS = 60


def check_due_live_streams() -> int:
    """Start recording for monitored streams that are live right now."""
    if not sources.ytdlp_available():
        return 0
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=CHECK_INTERVAL_SECONDS)
    started = 0
    with session_scope() as db:
        due = list(
            db.scalars(
                select(LiveStream).where(
                    LiveStream.status == "monitoring",
                    LiveStream.auto_record.is_(True),
                    or_(LiveStream.last_checked_at.is_(None), LiveStream.last_checked_at <= cutoff),
                )
            )
        )
        for stream in due:
            stream.last_checked_at = now
            db.commit()
            if stream.campaign_id:
                campaign = db.get(Campaign, stream.campaign_id)
                if campaign and campaign.status != "active":
                    continue
            try:
                state = sources.fetch_live_state(stream.url)
            except Exception:  # pragma: no cover - network failures are expected
                logger.exception("Could not check live state for stream %s", stream.id)
                continue
            if state is not True:
                continue
            video = SourceVideo(
                workspace_id=stream.workspace_id,
                campaign_id=stream.campaign_id,
                created_by=stream.created_by,
                title=stream.title or "Live recording",
                source_type=stream.platform,
                source_url=stream.url,
                mime_type="video/mp4",
                status="downloading",
            )
            db.add(video)
            db.flush()
            stream.status = "recording"
            stream.started_at = now
            stream.recording_video_id = video.id
            stream.error_message = None
            db.commit()
            job = create_pipeline_job(
                db,
                workspace_id=stream.workspace_id,
                video_id=video.id,
                kind="live",
                task_name="record_live",
                payload={
                    "video_id": video.id,
                    "live_stream_id": stream.id,
                    "auto_clip": stream.auto_clip,
                },
            )
            enqueue(job.id)
            started += 1
            logger.info("Auto-recording live stream %s", stream.id)
    return started
