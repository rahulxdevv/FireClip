"""Pipeline tasks executed by the worker (ARQ) or the inline thread runner."""
from __future__ import annotations

import hashlib
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, func, select

from .config import settings
from .database import session_scope
from .jobs import JobCancelled, JobReporter, create_pipeline_job, enqueue, task
from .models import (
    AiAnalysis,
    Campaign,
    CandidateClip,
    CaptionStyle,
    EditingProject,
    ExportedVideo,
    PipelineJob,
    RenderJob,
    SourceVideo,
    Speaker,
    Transcript,
    TranscriptSegment,
    UsageRecord,
    VideoMetadata,
    Workspace,
)
from .services import ai as ai_service
from .services import billing, highlights, media, sources, transcription
from .services.render import cleanup_temp, render_project
from .services.webhooks import emit as emit_webhook
from .storage import build_key, get_storage

logger = logging.getLogger("fireclip.tasks")
# Inline runners can have several jobs in flight. Rendering is the most CPU
# hungry task, so cap concurrent encodes independently of the job pool.
_render_slots = threading.BoundedSemaphore(max(1, settings.render_concurrency))


def _now():
    return datetime.now(timezone.utc)


def _update_video(video_id: str, **fields) -> None:
    with session_scope() as db:
        video = db.get(SourceVideo, video_id)
        if not video:
            return
        for key, value in fields.items():
            setattr(video, key, value)


def _chain_transcription(video_id: str, workspace_id: str, *, engine: str = "auto", auto_analyze: bool = True) -> None:
    with session_scope() as db:
        existing = db.scalar(
            select(PipelineJob).where(
                PipelineJob.video_id == video_id,
                PipelineJob.task_name == "transcribe_video",
                PipelineJob.status.in_(["queued", "running"]),
            )
        )
        if existing:
            return
        job = create_pipeline_job(
            db,
            workspace_id=workspace_id,
            video_id=video_id,
            kind="transcription",
            task_name="transcribe_video",
            payload={"video_id": video_id, "engine": engine, "auto_analyze": auto_analyze},
        )
    enqueue(job.id)


def _chain_analysis(
    video_id: str, workspace_id: str, *, replace_existing: bool = True
) -> None:
    with session_scope() as db:
        existing = db.scalar(
            select(PipelineJob).where(
                PipelineJob.video_id == video_id,
                PipelineJob.task_name == "analyze_video",
                PipelineJob.status.in_(["queued", "running"]),
            )
        )
        if existing:
            return
        job = create_pipeline_job(
            db,
            workspace_id=workspace_id,
            video_id=video_id,
            kind="analysis",
            task_name="analyze_video",
            payload={
                "video_id": video_id,
                "provider": "auto",
                "replace_existing": replace_existing,
            },
        )
    enqueue(job.id)


# --- Ingestion ------------------------------------------------------------


@task("ingest_video")
def ingest_video(reporter: JobReporter) -> None:
    payload = reporter.payload
    video_id = payload["video_id"]
    storage = get_storage()
    with session_scope() as db:
        video = db.get(SourceVideo, video_id)
        if not video:
            raise RuntimeError("Video record not found")
        workspace_id = video.workspace_id
        source_url = video.source_url
        source_type = video.source_type

    local_path: Path | None = None
    try:
        if source_url and source_type != "upload":
            reporter.progress(2, "downloading")
            suffix = ".mp4"
            target = settings.data_dir / "tmp" / f"download-{video_id}{suffix}"
            sources.download_video(
                source_url,
                target,
                on_progress=lambda pct: reporter.progress(2 + pct * 0.68, "downloading"),
                cancel_check=reporter.check_cancelled,
            )
            local_path = target
            reporter.progress(72, "probing")
            key = build_key("uploads", workspace_id, f"{video_id}{suffix}")
            storage.put_file(target, key, "video/mp4")
            checksum = _sha256_file(storage.local_path(key)) if storage.local_path(key) else None
            _update_video(video_id, storage_key=key, checksum=checksum, size_bytes=storage.size(key))
        else:
            with session_scope() as db:
                video = db.get(SourceVideo, video_id)
                if not video or not video.storage_key:
                    raise RuntimeError("Uploaded file is missing")
                key = video.storage_key
            checksum = _sha256_file(storage.local_path(key)) if storage.local_path(key) else None
            if checksum:
                _update_video(video_id, checksum=checksum, size_bytes=storage.size(key))
            reporter.progress(20, "probing")

        with storage.temp_copy(key) as media_path:
            info = media.probe(media_path)
            reporter.check_cancelled()
            reporter.progress(80, "probing")
            thumb_local = settings.data_dir / "tmp" / f"thumb-{video_id}.jpg"
            thumb_key = None
            if info.has_video:
                try:
                    media.extract_thumbnail(media_path, thumb_local, at_seconds=min(1.0, info.duration / 3))
                    thumb_key = build_key("thumbnails", workspace_id, f"{video_id}.jpg")
                    storage.put_file(thumb_local, thumb_key, "image/jpeg")
                except media.MediaError:
                    logger.warning("Thumbnail generation failed for %s", video_id)

        reporter.progress(92, "probing")
        with session_scope() as db:
            video = db.get(SourceVideo, video_id)
            if not video:
                raise RuntimeError("Video record disappeared")
            video.duration_seconds = info.duration
            video.width = info.width
            video.height = info.height
            video.fps = info.fps
            video.has_audio = info.has_audio
            video.mime_type = sources.guess_mime(Path(key))
            video.thumbnail_key = thumb_key
            video.status = "ready"
            video.progress = 100.0
            video.error_message = None
            video.metadata_extra = {
                **(video.metadata_extra or {}),
                "source": source_type,
                "imported_from": source_url or "",
            }
            row = video.metadata_row
            if row is None:
                row = VideoMetadata(video_id=video.id)
                db.add(row)
            row.container = info.container
            row.video_codec = info.video_codec
            row.audio_codec = info.audio_codec
            row.bitrate = info.bitrate
            row.sample_rate = info.sample_rate
            row.channels = info.channels
            row.raw_json = info.raw
            db.add(
                UsageRecord(
                    workspace_id=workspace_id,
                    kind="storage",
                    quantity=float(info.duration),
                    detail={"video_id": video_id, "size_bytes": video.size_bytes},
                )
            )
            emit_webhook(
                db,
                workspace_id,
                "video.ready",
                {
                    "video_id": video.id,
                    "title": video.title,
                    "duration_seconds": info.duration,
                    "thumbnail_key": thumb_key,
                    "source": source_type,
                },
            )
        if not info.has_audio:
            logger.info("Video %s has no audio; skipping transcription", video_id)
            return
        if settings.auto_pipeline and payload.get("auto_pipeline", True):
            _chain_transcription(video_id, workspace_id, auto_analyze=True)
    finally:
        try:
            if local_path and local_path.exists():
                local_path.unlink()
        except OSError:
            pass


def _sha256_file(path: Path | None) -> str | None:
    if not path or not path.exists():
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# --- Transcription --------------------------------------------------------


@task("transcribe_video")
def transcribe_video(reporter: JobReporter) -> None:
    payload = reporter.payload
    video_id = payload["video_id"]
    engine = payload.get("engine", "auto")
    force = bool(payload.get("force", False))
    language = payload.get("language") or None
    auto_analyze = bool(payload.get("auto_analyze", True))
    storage = get_storage()

    with session_scope() as db:
        video = db.get(SourceVideo, video_id)
        if not video:
            raise RuntimeError("Video not found")
        workspace_id = video.workspace_id
        if not video.storage_key:
            raise RuntimeError("Source file is missing")
        if not video.has_audio:
            raise RuntimeError("This video has no audio track to transcribe")
        existing = db.scalar(
            select(Transcript)
            .where(Transcript.video_id == video_id, Transcript.status == "completed")
            .order_by(Transcript.created_at.desc())
        )
        if existing and not force:
            reporter.progress(100, "ready")
            if auto_analyze:
                _chain_analysis(
                    video_id,
                    workspace_id,
                    replace_existing=bool(payload.get("replace_existing", True)),
                )
            return
        if existing:
            db.delete(existing)
            db.commit()
        transcript_row = Transcript(
            video_id=video_id,
            workspace_id=workspace_id,
            engine=engine,
            status="processing",
        )
        db.add(transcript_row)
        db.commit()
        transcript_id = transcript_row.id
        storage_key = video.storage_key
        video.status = "transcribing"
        video.progress = 0
        video.error_message = None

    try:
        reporter.progress(4, "transcribing")
        with storage.temp_copy(storage_key) as media_path:
            audio_path = settings.data_dir / "audio" / f"{video_id}.wav"
            media.extract_audio(media_path, audio_path)
            reporter.progress(14, "transcribing")
            result = transcription.transcribe(audio_path, engine=engine, language=language)
            try:
                audio_path.unlink(missing_ok=True)
            except OSError:
                pass
        reporter.progress(78, "transcribing")
        method = transcription.diarize(result.segments)
        reporter.progress(85, "transcribing")

        with session_scope() as db:
            row = db.get(Transcript, transcript_id)
            if not row:
                raise RuntimeError("Transcript record disappeared")
            row.engine = result.engine
            row.model = result.model
            row.language = result.language or settings.default_language
            row.status = "completed"
            row.full_text = result.text
            row.word_count = result.word_count
            row.error_message = None
            db.flush()

            speakers: dict[str, Speaker] = {}
            for label in transcription.speaker_labels(result.segments):
                speaker = Speaker(
                    video_id=video_id,
                    label=label,
                    display_name=None,
                    method=method,
                    color="#ff6a1f" if label.endswith("1") else "#ffb347",
                )
                db.add(speaker)
                db.flush()
                speakers[label] = speaker

            for segment in result.segments:
                speaker = speakers.get(segment.speaker)
                db.add(
                    TranscriptSegment(
                        transcript_id=transcript_id,
                        speaker_id=speaker.id if speaker else None,
                        start_ms=segment.start_ms,
                        end_ms=segment.end_ms,
                        text=segment.text,
                        confidence=segment.confidence,
                        words=segment.words,
                    )
                )
            video = db.get(SourceVideo, video_id)
            if video:
                video.language = row.language
                video.status = "ready"
                video.progress = 100.0
            db.add(
                UsageRecord(
                    workspace_id=workspace_id,
                    kind="transcription",
                    quantity=float(sum(s.end_ms - s.start_ms for s in result.segments)) / 1000,
                    provider=result.engine,
                    detail={"video_id": video_id, "model": result.model},
                )
            )
        reporter.progress(100, "ready")
        if auto_analyze:
            _chain_analysis(
                video_id,
                workspace_id,
                replace_existing=bool(payload.get("replace_existing", True)),
            )
    except Exception as exc:
        with session_scope() as db:
            row = db.get(Transcript, transcript_id)
            if row:
                row.status = "failed"
                row.error_message = str(exc)[:2000]
            video = db.get(SourceVideo, video_id)
            if video:
                video.status = "error"
                video.error_message = str(exc)[:2000]
        raise


# --- Analysis -------------------------------------------------------------


@task("analyze_video")
def analyze_video(reporter: JobReporter) -> None:
    payload = reporter.payload
    video_id = payload["video_id"]
    requested_provider = payload.get("provider", "auto")
    target_duration_ms = int(payload.get("target_duration_ms") or settings.default_clip_duration_ms)
    clip_count = int(payload.get("clip_count") or settings.default_clip_count)
    replace_existing = bool(payload.get("replace_existing", True))
    auto_render_jobs: list[str] = []

    with session_scope() as db:
        video = db.get(SourceVideo, video_id)
        if not video:
            raise RuntimeError("Video not found")
        workspace_id = video.workspace_id
        campaign = db.get(Campaign, video.campaign_id) if video.campaign_id else None
        campaign_id = campaign.id if campaign else None
        campaign_brief = campaign.brief if campaign else ""
        campaign_min_score = float(campaign.min_score) if campaign else 0.0
        campaign_automation = bool(campaign and campaign.status == "active")
        if campaign:
            target_duration_ms = campaign.target_duration_ms
            clip_count = campaign.clip_count
        transcript = db.scalar(
            select(Transcript)
            .where(Transcript.video_id == video_id, Transcript.status == "completed")
            .order_by(Transcript.created_at.desc())
        )
        if not transcript:
            raise RuntimeError("Transcribe this video before analysing it")
        segments = [
            transcription.SegmentData(
                start_ms=s.start_ms, end_ms=s.end_ms, text=s.text, words=s.words or [], confidence=s.confidence
            )
            for s in db.scalars(
                select(TranscriptSegment)
                .where(TranscriptSegment.transcript_id == transcript.id)
                .order_by(TranscriptSegment.start_ms)
            )
        ]
        if not segments:
            raise RuntimeError("Transcript has no segments to analyse")
        analysis = AiAnalysis(
            video_id=video_id,
            workspace_id=workspace_id,
            provider=requested_provider,
            status="processing",
            target_duration_ms=target_duration_ms,
        )
        db.add(analysis)
        db.commit()
        analysis_id = analysis.id
        video.status = "analyzing"
        video.progress = 15
        total_duration_ms = int(video.duration_seconds * 1000)
        usage_ratio = len(transcript.full_text) / 4  # rough token estimate

    try:
        reporter.progress(25, "analyzing")
        with session_scope() as db:
            try:
                provider = ai_service.build_provider(db, workspace_id, requested_provider)
            except ai_service.AIError as exc:
                raise RuntimeError(str(exc)) from exc
            result = highlights.analyze(
                db,
                workspace_id,
                segments,
                provider=provider,
                target_duration_ms=target_duration_ms,
                clip_count=clip_count,
                total_duration_ms=total_duration_ms,
                brief=campaign_brief,
            )
        reporter.progress(85, "analyzing")
        with session_scope() as db:
            analysis = db.get(AiAnalysis, analysis_id)
            video = db.get(SourceVideo, video_id)
            if not analysis or not video:
                raise RuntimeError("Analysis records disappeared")
            if replace_existing:
                db.execute(
                    delete(CandidateClip).where(
                        CandidateClip.video_id == video_id,
                        CandidateClip.status == "suggested",
                    )
                )
            workspace = db.get(Workspace, workspace_id)
            remaining = max(
                0,
                (workspace.monthly_clip_limit if workspace else 0)
                - billing.clips_used_this_month(db, workspace_id),
            )
            selected = [
                clip for clip in result.clips if clip.virality_score >= campaign_min_score
            ][:remaining]

            month_start = _now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            render_seconds_used = float(
                db.scalar(
                    select(func.coalesce(func.sum(UsageRecord.quantity), 0)).where(
                        UsageRecord.workspace_id == workspace_id,
                        UsageRecord.kind == "render_seconds",
                        UsageRecord.created_at >= month_start,
                    )
                )
                or 0
            )
            render_minutes_used = render_seconds_used / 60
            render_minutes_left = max(
                0.0,
                float(workspace.monthly_render_minutes if workspace else 0) - render_minutes_used,
            )
            aspect_sizes = {
                "9:16": (1080, 1920, "tiktok"),
                "1:1": (1080, 1080, "square"),
                "4:5": (1080, 1350, "portrait"),
                "16:9": (1920, 1080, "landscape"),
            }
            brand = dict(campaign.brand or {}) if campaign else {}
            brand_mark = str(brand.get("logo_text") or "").strip()[:80]
            brand_accent = str(brand.get("accent_color") or "#ff6a1f")
            for clip in selected:
                status = "approved" if campaign and campaign.auto_approve and campaign_automation else "suggested"
                row = CandidateClip(
                    workspace_id=workspace_id,
                    video_id=video_id,
                    analysis_id=analysis_id,
                    start_ms=clip.start_ms,
                    end_ms=clip.end_ms,
                    duration_ms=clip.end_ms - clip.start_ms,
                    title=clip.title,
                    description=clip.description,
                    hook=clip.hook,
                    transcript_text=clip.transcript_text,
                    explanation=clip.explanation,
                    virality_score=clip.virality_score,
                    engagement_potential=clip.engagement_potential,
                    signals=clip.signals,
                    aspect_ratio=campaign.aspect_ratio if campaign else "9:16",
                    status=status,
                    source="ai",
                )
                db.add(row)
                db.flush()
                if not (
                    campaign
                    and campaign.auto_render
                    and campaign_automation
                    and status == "approved"
                ):
                    continue
                estimated_minutes = max(0.1, (clip.end_ms - clip.start_ms) / 60000)
                if estimated_minutes > render_minutes_left:
                    continue
                width, height, preset = aspect_sizes.get(campaign.aspect_ratio, (1080, 1920, "tiktok"))
                project = EditingProject(
                    workspace_id=workspace_id,
                    video_id=video_id,
                    campaign_id=campaign.id,
                    clip_id=row.id,
                    created_by=video.created_by,
                    name=clip.title,
                    aspect_ratio=campaign.aspect_ratio,
                    width=width,
                    height=height,
                    trim_start_ms=clip.start_ms,
                    trim_end_ms=clip.end_ms,
                    caption_style_id=campaign.caption_style_id,
                    captions_enabled=True,
                    caption_overrides=dict(campaign.caption_overrides or {}),
                    overlays=(
                        [
                            {
                                "type": "text",
                                "text": brand_mark,
                                "x": 0.5,
                                "y": 0.07,
                                "font_size": 38,
                                "color": "#ffffff",
                                "outline_color": brand_accent,
                                "outline_width": 4,
                                "start_ms": clip.start_ms,
                                "end_ms": clip.end_ms,
                                "animation": "none",
                            }
                        ]
                        if brand_mark
                        else []
                    ),
                    music=None,
                    audio={},
                    operations=[],
                    status="ready",
                )
                db.add(project)
                db.flush()
                render = RenderJob(
                    workspace_id=workspace_id,
                    editing_project_id=project.id,
                    created_by=video.created_by,
                    preset=preset,
                    format="mp4",
                    status="queued",
                )
                db.add(render)
                db.flush()
                pipeline = PipelineJob(
                    workspace_id=workspace_id,
                    video_id=video_id,
                    kind="rendering",
                    task_name="render_video",
                    payload={
                        "render_job_id": render.id,
                        "preset": preset,
                        "format": "mp4",
                        "width": width,
                        "height": height,
                        "campaign_id": campaign.id,
                    },
                    status="queued",
                    stage="queued",
                )
                db.add(pipeline)
                db.flush()
                auto_render_jobs.append(pipeline.id)
                render_minutes_left -= estimated_minutes
            analysis.status = "completed"
            analysis.provider = result.provider
            analysis.model = result.model
            analysis.summary = result.summary
            analysis.topics = result.topics
            analysis.clip_count = len(selected)
            video.status = "ready"
            video.progress = 100.0
            video.error_message = None
            db.add(
                UsageRecord(
                    workspace_id=workspace_id,
                    kind="ai",
                    quantity=float(usage_ratio),
                    provider=result.provider,
                    detail={"video_id": video_id, "clips": len(result.clips)},
                )
            )
        for pipeline_id in auto_render_jobs:
            enqueue(pipeline_id)
        reporter.progress(100, "ready")
    except Exception as exc:
        with session_scope() as db:
            analysis = db.get(AiAnalysis, analysis_id)
            if analysis:
                analysis.status = "failed"
                analysis.error_message = str(exc)[:2000]
            video = db.get(SourceVideo, video_id)
            if video:
                video.status = "error"
                video.error_message = str(exc)[:2000]
        raise


# --- Rendering ------------------------------------------------------------


@task("render_video")
def render_video(reporter: JobReporter) -> None:
    payload = reporter.payload
    render_id = payload["render_job_id"]
    storage = get_storage()
    with session_scope() as db:
        render = db.get(RenderJob, render_id)
        if not render:
            raise RuntimeError("Render job not found")
        if render.status == "cancelled":
            raise JobCancelled()
        project = db.get(EditingProject, render.editing_project_id)
        if not project:
            raise RuntimeError("Editing project not found")
        video = db.get(SourceVideo, project.video_id)
        if not video:
            raise RuntimeError("Source video not found")
        transcript = db.scalar(
            select(Transcript)
            .where(Transcript.video_id == video.id, Transcript.status == "completed")
            .order_by(Transcript.created_at.desc())
        )
        segments: list[transcription.SegmentData] = []
        if transcript:
            for row in db.scalars(
                select(TranscriptSegment)
                .where(TranscriptSegment.transcript_id == transcript.id)
                .order_by(TranscriptSegment.start_ms)
            ):
                segments.append(
                    transcription.SegmentData(
                        start_ms=row.start_ms, end_ms=row.end_ms, text=row.text, words=row.words or []
                    )
                )
        style_row = db.get(CaptionStyle, project.caption_style_id) if project.caption_style_id else None
        render.status = "running"
        render.started_at = _now()
        render.progress = 1.0
        render.attempts += 1
        render.error_message = None
        video.status = "rendering"
        workspace_id = render.workspace_id
        created_by = render.created_by
        preset, fmt = render.preset, render.format
        project_id, clip_id = project.id, project.clip_id
        project_name = project.name
        db.commit()
        # Detach simple values so the session can close before the long encode.
        project_snapshot = EditingProject(
            id=project.id,
            workspace_id=project.workspace_id,
            video_id=project.video_id,
            clip_id=project.clip_id,
            created_by=project.created_by,
            name=project.name,
            aspect_ratio=project.aspect_ratio,
            width=project.width,
            height=project.height,
            trim_start_ms=project.trim_start_ms,
            trim_end_ms=project.trim_end_ms,
            focus_x=project.focus_x,
            focus_y=project.focus_y,
            caption_style_id=project.caption_style_id,
            captions_enabled=project.captions_enabled,
            caption_overrides=dict(project.caption_overrides or {}),
            overlays=list(project.overlays or []),
            music=dict(project.music or {}) if project.music else None,
            audio=dict(project.audio or {}),
            operations=list(project.operations or []),
        )
        video_snapshot = SourceVideo(
            id=video.id,
            workspace_id=video.workspace_id,
            created_by=video.created_by,
            title=video.title,
            storage_key=video.storage_key,
            has_audio=video.has_audio,
            duration_seconds=video.duration_seconds,
        )
        style_snapshot = (
            CaptionStyle(id=style_row.id, name=style_row.name, is_builtin=style_row.is_builtin, config=dict(style_row.config or {}))
            if style_row
            else None
        )

    def progress(pct: float) -> None:
        reporter.progress(pct, "rendering")
        with session_scope() as db:
            render = db.get(RenderJob, render_id)
            if render:
                render.progress = pct

    def tick() -> None:
        reporter.check_cancelled()

    try:
        if not _render_slots.acquire(timeout=2):
            reporter.stage("waiting_for_render_slot")
            logger.info("Render %s waiting for a free encode slot", render_id)
            while not _render_slots.acquire(timeout=2):
                reporter.check_cancelled()
        try:
            result = render_project(
                project_snapshot,
                video_snapshot,
                segments,
                style_snapshot,
                job_id=render_id,
                preset=preset,
                fmt=fmt,
                on_progress=progress,
                on_tick=tick,
            )
        finally:
            _render_slots.release()
    except JobCancelled:
        with session_scope() as db:
            render = db.get(RenderJob, render_id)
            if render:
                render.status = "cancelled"
                render.finished_at = _now()
            video = db.get(SourceVideo, video_snapshot.id)
            if video:
                video.status = "ready"
        cleanup_temp(render_id)
        raise
    except Exception as exc:
        with session_scope() as db:
            render = db.get(RenderJob, render_id)
            if render:
                render.status = "failed"
                render.error_message = str(exc)[:3000]
                render.finished_at = _now()
            video = db.get(SourceVideo, video_snapshot.id)
            if video:
                video.status = "ready"
                video.error_message = f"Render failed: {str(exc)[:300]}"
        cleanup_temp(render_id)
        raise

    with session_scope() as db:
        render = db.get(RenderJob, render_id)
        if not render:
            raise RuntimeError("Render job disappeared")
        render.status = "cancelled" if render.status == "cancelled" else "completed"
        render.progress = 100.0
        render.output_key = result.output_key
        render.thumbnail_key = result.thumbnail_key
        render.output_size_bytes = result.size_bytes
        render.render_seconds = result.render_seconds
        render.finished_at = _now()
        export = ExportedVideo(
            workspace_id=workspace_id,
            render_job_id=render_id,
            clip_id=clip_id,
            title=project_name or "FireClip export",
            filename=f"{project_name.replace(' ', '-').lower()[:60] or 'fireclip'}.{fmt}",
            storage_key=result.output_key,
            thumbnail_key=result.thumbnail_key,
            format=fmt,
            width=result.width,
            height=result.height,
            duration_ms=result.duration_ms,
            size_bytes=result.size_bytes,
        )
        db.add(export)
        video = db.get(SourceVideo, video_snapshot.id)
        if video:
            video.status = "ready"
        db.add(
            UsageRecord(
                workspace_id=workspace_id,
                kind="render_seconds",
                quantity=float(result.duration_ms) / 1000,
                detail={"render_job_id": render_id, "preset": preset, "format": fmt},
            )
        )
        if project_snapshot.clip_id:
            clip = db.get(CandidateClip, project_snapshot.clip_id)
            if clip:
                clip.status = "approved"
        emit_webhook(
            db,
            workspace_id,
            "clip.rendered",
            {
                "render_job_id": render_id,
                "clip_id": clip_id,
                "export_id": export.id,
                "title": export.title,
                "format": fmt,
                "duration_ms": result.duration_ms,
                "size_bytes": result.size_bytes,
            },
        )
    cleanup_temp(render_id)
    reporter.progress(100, "ready")


# --- Publishing -----------------------------------------------------------


@task("publish_video")
def publish_video(reporter: JobReporter) -> None:
    from .services import publishing

    payload = reporter.payload
    job_id = payload["publishing_job_id"]
    reporter.progress(10)
    try:
        publishing.execute_publish(job_id)
    finally:
        with session_scope() as db:
            job = db.get(PipelineJob, reporter.job_id)
            if job:
                job.progress = 100
    reporter.progress(100)


# --- Live streams ---------------------------------------------------------


@task("record_live")
def record_live(reporter: JobReporter) -> None:
    payload = reporter.payload
    video_id = payload["video_id"]
    live_id = payload.get("live_stream_id")
    storage = get_storage()
    with session_scope() as db:
        video = db.get(SourceVideo, video_id)
        if not video or not video.source_url:
            raise RuntimeError("Live stream video record is missing its URL")
        workspace_id = video.workspace_id
        source_url = video.source_url
    target = settings.data_dir / "tmp" / f"live-{video_id}.mp4"
    reporter.progress(2, "downloading")
    try:
        sources.download_video(
            source_url,
            target,
            on_progress=lambda pct: reporter.progress(2 + pct * 0.8, "downloading"),
            cancel_check=reporter.check_cancelled,
        )
    except JobCancelled:
        raise
    except Exception as exc:
        if live_id:
            with session_scope() as db:
                from .models import LiveStream

                live = db.get(LiveStream, live_id)
                if live and live.status == "recording":
                    live.status = "error"
                    live.error_message = f"Live capture failed: {str(exc)[:600]}"
                    live.ended_at = _now()
        raise
    reporter.progress(85, "probing")
    key = build_key("uploads", workspace_id, f"{video_id}.mp4")
    storage.put_file(target, key, "video/mp4")
    try:
        with storage.temp_copy(key) as media_path:
            info = media.probe(media_path)
            thumb_local = settings.data_dir / "tmp" / f"livethumb-{video_id}.jpg"
            media.extract_thumbnail(media_path, thumb_local, 0.5)
            thumb_key = build_key("thumbnails", workspace_id, f"{video_id}.jpg")
            storage.put_file(thumb_local, thumb_key, "image/jpeg")
    finally:
        target.unlink(missing_ok=True)
    with session_scope() as db:
        video = db.get(SourceVideo, video_id)
        if video:
            video.storage_key = key
            video.duration_seconds = info.duration
            video.width = info.width
            video.height = info.height
            video.fps = info.fps
            video.has_audio = info.has_audio
            video.thumbnail_key = thumb_key
            video.status = "ready"
            video.progress = 100
        if live_id:
            from .models import LiveStream

            live = db.get(LiveStream, live_id)
            if live:
                # A standing auto-record entry goes back to monitoring so the next
                # time this URL goes live it is captured again. Manual entries
                # stay in the finished state.
                live.status = "monitoring" if live.auto_record else "recorded"
                live.ended_at = _now()
                live.recording_video_id = video_id
    if info.has_audio:
        _chain_transcription(
            video_id, workspace_id, auto_analyze=bool(payload.get("auto_clip", True))
        )
    reporter.progress(100, "ready")
