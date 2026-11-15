"""Normalized domain model for FireClip.

Entities: users, workspaces, memberships, API keys, projects, source videos,
metadata, transcripts, speakers, AI analyses, candidate clips, editing
projects, caption styles, render jobs, exports, social accounts, publishing
jobs, analytics, AI provider configs, usage, notifications, pipeline jobs,
live streams and audit logs.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def uid() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(120), default="")
    avatar_color: Mapped[str] = mapped_column(String(16), default="#ff6a1f")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Workspace(TimestampMixin, Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    owner_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"))
    plan: Mapped[str] = mapped_column(String(32), default="studio")
    monthly_clip_limit: Mapped[int] = mapped_column(Integer, default=500)
    monthly_render_minutes: Mapped[int] = mapped_column(Integer, default=600)

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id", name="uq_membership"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16), default="editor")  # owner|admin|editor|viewer
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="memberships")
    workspace: Mapped[Workspace] = relationship(back_populates="memberships")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"))
    workspace_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    prefix: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    key_hash: Mapped[str] = mapped_column(String(128))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Project(TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (Index("ix_projects_workspace_created", "workspace_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"))


class SourceVideo(TimestampMixin, Base):
    __tablename__ = "source_videos"
    __table_args__ = (
        Index("ix_videos_workspace_created", "workspace_id", "created_at"),
        Index("ix_videos_workspace_checksum", "workspace_id", "checksum"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("projects.id", ondelete="SET NULL"), index=True
    )
    created_by: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    source_type: Mapped[str] = mapped_column(String(24), default="upload")
    source_url: Mapped[str | None] = mapped_column(Text)
    original_filename: Mapped[str | None] = mapped_column(String(300))
    storage_key: Mapped[str | None] = mapped_column(String(400))
    thumbnail_key: Mapped[str | None] = mapped_column(String(400))
    mime_type: Mapped[str] = mapped_column(String(120), default="video/mp4")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    checksum: Mapped[str | None] = mapped_column(String(64))
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    fps: Mapped[float] = mapped_column(Float, default=0.0)
    has_audio: Mapped[bool] = mapped_column(Boolean, default=True)
    language: Mapped[str] = mapped_column(String(16), default="en")
    status: Mapped[str] = mapped_column(String(24), default="uploaded", index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    error_message: Mapped[str | None] = mapped_column(Text)
    metadata_extra: Mapped[dict] = mapped_column(JSON, default=dict)

    metadata_row: Mapped["VideoMetadata | None"] = relationship(
        back_populates="video", cascade="all, delete-orphan", uselist=False
    )


class VideoMetadata(Base):
    __tablename__ = "video_metadata"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    video_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("source_videos.id", ondelete="CASCADE"), unique=True
    )
    container: Mapped[str] = mapped_column(String(40), default="")
    video_codec: Mapped[str] = mapped_column(String(40), default="")
    audio_codec: Mapped[str] = mapped_column(String(40), default="")
    bitrate: Mapped[int] = mapped_column(Integer, default=0)
    sample_rate: Mapped[int] = mapped_column(Integer, default=0)
    channels: Mapped[int] = mapped_column(Integer, default=0)
    raw_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    video: Mapped[SourceVideo] = relationship(back_populates="metadata_row")


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    video_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("source_videos.id", ondelete="CASCADE"), index=True
    )
    workspace_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    language: Mapped[str] = mapped_column(String(16), default="en")
    engine: Mapped[str] = mapped_column(String(40), default="faster_whisper")
    model: Mapped[str] = mapped_column(String(80), default="")
    status: Mapped[str] = mapped_column(String(24), default="processing", index=True)
    full_text: Mapped[str] = mapped_column(Text, default="")
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    segments: Mapped[list["TranscriptSegment"]] = relationship(
        back_populates="transcript",
        cascade="all, delete-orphan",
        order_by="TranscriptSegment.start_ms",
    )


class Speaker(Base):
    __tablename__ = "speakers"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    video_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("source_videos.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(40))
    display_name: Mapped[str | None] = mapped_column(String(80))
    color: Mapped[str] = mapped_column(String(16), default="#ffb347")
    method: Mapped[str] = mapped_column(String(40), default="heuristic")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"
    __table_args__ = (Index("ix_segments_transcript_start", "transcript_id", "start_ms"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    transcript_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("transcripts.id", ondelete="CASCADE"), index=True
    )
    speaker_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("speakers.id", ondelete="SET NULL")
    )
    start_ms: Mapped[int] = mapped_column(Integer)
    end_ms: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    words: Mapped[list] = mapped_column(JSON, default=list)  # [{word,start_ms,end_ms,confidence}]

    transcript: Mapped[Transcript] = relationship(back_populates="segments")


class AiAnalysis(Base):
    __tablename__ = "ai_analyses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    video_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("source_videos.id", ondelete="CASCADE"), index=True
    )
    workspace_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(40), default="heuristic")
    model: Mapped[str] = mapped_column(String(80), default="fireclip-signals-v1")
    status: Mapped[str] = mapped_column(String(24), default="processing", index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    topics: Mapped[list] = mapped_column(JSON, default=list)
    target_duration_ms: Mapped[int] = mapped_column(Integer, default=45000)
    clip_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CandidateClip(TimestampMixin, Base):
    __tablename__ = "candidate_clips"
    __table_args__ = (Index("ix_clips_workspace_score", "workspace_id", "virality_score"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    video_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("source_videos.id", ondelete="CASCADE"), index=True
    )
    analysis_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("ai_analyses.id", ondelete="SET NULL")
    )
    start_ms: Mapped[int] = mapped_column(Integer)
    end_ms: Mapped[int] = mapped_column(Integer)
    duration_ms: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text, default="")
    hook: Mapped[str] = mapped_column(String(300), default="")
    transcript_text: Mapped[str] = mapped_column(Text, default="")
    explanation: Mapped[str] = mapped_column(Text, default="")
    virality_score: Mapped[float] = mapped_column(Float, default=0.0)
    engagement_potential: Mapped[float] = mapped_column(Float, default=0.0)
    signals: Mapped[dict] = mapped_column(JSON, default=dict)
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    aspect_ratio: Mapped[str] = mapped_column(String(12), default="9:16")
    source: Mapped[str] = mapped_column(String(24), default="ai")  # ai | manual
    status: Mapped[str] = mapped_column(String(16), default="suggested", index=True)


class CaptionStyle(TimestampMixin, Base):
    __tablename__ = "caption_styles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    workspace_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict)


class EditingProject(TimestampMixin, Base):
    __tablename__ = "editing_projects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    video_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("source_videos.id", ondelete="CASCADE"), index=True
    )
    clip_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("candidate_clips.id", ondelete="SET NULL")
    )
    created_by: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(160), default="Untitled clip")
    aspect_ratio: Mapped[str] = mapped_column(String(12), default="9:16")
    width: Mapped[int] = mapped_column(Integer, default=1080)
    height: Mapped[int] = mapped_column(Integer, default=1920)
    trim_start_ms: Mapped[int] = mapped_column(Integer, default=0)
    trim_end_ms: Mapped[int] = mapped_column(Integer, default=0)
    focus_x: Mapped[float] = mapped_column(Float, default=0.5)
    focus_y: Mapped[float] = mapped_column(Float, default=0.5)
    caption_style_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("caption_styles.id", ondelete="SET NULL")
    )
    captions_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    caption_overrides: Mapped[dict] = mapped_column(JSON, default=dict)
    overlays: Mapped[list] = mapped_column(JSON, default=list)
    music: Mapped[dict | None] = mapped_column(JSON)
    audio: Mapped[dict] = mapped_column(JSON, default=dict)
    operations: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default="draft")


class RenderJob(TimestampMixin, Base):
    __tablename__ = "render_jobs"
    __table_args__ = (Index("ix_renders_workspace_created", "workspace_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    editing_project_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("editing_projects.id", ondelete="CASCADE"), index=True
    )
    created_by: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"))
    preset: Mapped[str] = mapped_column(String(40), default="tiktok")
    format: Mapped[str] = mapped_column(String(8), default="mp4")
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    output_key: Mapped[str | None] = mapped_column(String(400))
    thumbnail_key: Mapped[str | None] = mapped_column(String(400))
    output_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    render_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExportedVideo(Base):
    __tablename__ = "exported_videos"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    render_job_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("render_jobs.id", ondelete="CASCADE"), index=True
    )
    clip_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("candidate_clips.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(240), default="")
    filename: Mapped[str] = mapped_column(String(260))
    storage_key: Mapped[str] = mapped_column(String(400))
    thumbnail_key: Mapped[str | None] = mapped_column(String(400))
    format: Mapped[str] = mapped_column(String(8), default="mp4")
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SocialAccount(TimestampMixin, Base):
    __tablename__ = "social_accounts"
    __table_args__ = (UniqueConstraint("workspace_id", "platform", "external_id", name="uq_social"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    platform: Mapped[str] = mapped_column(String(24))
    account_name: Mapped[str] = mapped_column(String(160), default="")
    external_id: Mapped[str] = mapped_column(String(160), default="")
    access_token_encrypted: Mapped[str] = mapped_column(Text, default="")
    refresh_token_encrypted: Mapped[str] = mapped_column(Text, default="")
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scopes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(24), default="connected")
    connected_by: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"))
    last_error: Mapped[str | None] = mapped_column(Text)


class PublishingJob(TimestampMixin, Base):
    __tablename__ = "publishing_jobs"
    __table_args__ = (Index("ix_publish_due", "status", "scheduled_for"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    exported_video_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("exported_videos.id", ondelete="CASCADE"), index=True
    )
    social_account_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("social_accounts.id", ondelete="CASCADE")
    )
    platform: Mapped[str] = mapped_column(String(24))
    title: Mapped[str] = mapped_column(String(240), default="")
    caption: Mapped[str] = mapped_column(Text, default="")
    hashtags: Mapped[str] = mapped_column(Text, default="")
    privacy: Mapped[str] = mapped_column(String(24), default="public")
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), default="scheduled", index=True)
    external_post_id: Mapped[str | None] = mapped_column(String(160))
    external_url: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"))


class AnalyticsRecord(Base):
    __tablename__ = "analytics_records"
    __table_args__ = (Index("ix_analytics_post_captured", "publishing_job_id", "captured_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    publishing_job_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("publishing_jobs.id", ondelete="CASCADE"), index=True
    )
    platform: Mapped[str] = mapped_column(String(24))
    views: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    watch_time_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    retention_pct: Mapped[float] = mapped_column(Float, default=0.0)
    source: Mapped[str] = mapped_column(String(24), default="platform_api")
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AiProviderConfig(TimestampMixin, Base):
    __tablename__ = "ai_provider_configs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(24))
    model: Mapped[str] = mapped_column(String(80), default="")
    base_url: Mapped[str] = mapped_column(Text, default="")
    api_key_encrypted: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class UsageRecord(Base):
    __tablename__ = "usage_records"
    __table_args__ = (Index("ix_usage_workspace_kind", "workspace_id", "kind", "created_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(32))  # transcription|ai|render_seconds|storage
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    provider: Mapped[str] = mapped_column(String(40), default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_created", "user_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(32), default="info")
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PipelineJob(Base):
    __tablename__ = "pipeline_jobs"
    __table_args__ = (Index("ix_pipeline_workspace_created", "workspace_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    video_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("source_videos.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(40))
    task_name: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    stage: Mapped[str] = mapped_column(String(80), default="")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LiveStream(TimestampMixin, Base):
    __tablename__ = "live_streams"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    created_by: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"))
    platform: Mapped[str] = mapped_column(String(24))
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(24), default="monitoring")
    recording_video_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("source_videos.id", ondelete="SET NULL")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_workspace_created", "workspace_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    workspace_id: Mapped[str | None] = mapped_column(String(32), index=True)
    user_id: Mapped[str | None] = mapped_column(String(32), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    target_type: Mapped[str] = mapped_column(String(60), default="")
    target_id: Mapped[str] = mapped_column(String(60), default="")
    ip_address: Mapped[str] = mapped_column(String(60), default="")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WebhookEndpoint(Base):
    """Outbound notification hook (documented, optional)."""

    __tablename__ = "webhook_endpoints"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(Text)
    secret: Mapped[str] = mapped_column(String(120), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
