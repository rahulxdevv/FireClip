"""Pydantic request/response contracts for the FireClip API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

AspectRatio = Literal["9:16", "1:1", "16:9", "4:5", "custom"]
Platform = Literal["youtube", "tiktok", "instagram", "facebook"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Auth -----------------------------------------------------------------


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(default="", max_length=120)
    workspace_name: str = Field(default="", max_length=120)

    @field_validator("password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        if value.isdigit() or value.isalpha():
            raise ValueError("Password must mix letters and numbers")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(ORMModel):
    id: str
    email: str
    name: str
    avatar_color: str
    created_at: datetime
    email_verified_at: datetime | None = None


class ProfileUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        if value.isdigit() or value.isalpha():
            raise ValueError("Password must mix letters and numbers")
        return value


class WorkspaceOut(ORMModel):
    id: str
    name: str
    slug: str
    plan: str
    monthly_clip_limit: int
    monthly_render_minutes: int
    created_at: datetime


class WorkspaceSummary(WorkspaceOut):
    role: str
    member_count: int = 0


class SessionOut(BaseModel):
    user: UserOut
    workspaces: list[WorkspaceSummary]
    active_workspace_id: str | None = None


class RegisterOut(SessionOut):
    """Session plus honest delivery status for the verification email."""

    verification_email_sent: bool = False
    verification_link: str | None = None
    verification_required: bool = False


class CheckoutRequest(BaseModel):
    plan: Literal["starter", "studio", "agency"]
    interval: Literal["month", "year"] = "month"


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        if value.isdigit() or value.isalpha():
            raise ValueError("Password must mix letters and numbers")
        return value


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256)


class InvitePreviewOut(BaseModel):
    workspace_id: str
    email: str
    workspace_name: str
    workspace_slug: str
    role: str
    account_exists: bool


class InviteSignup(BaseModel):
    name: str = Field(default="", max_length=120)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        if value.isdigit() or value.isalpha():
            raise ValueError("Password must mix letters and numbers")
        return value


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)


class MemberAdd(BaseModel):
    email: EmailStr
    role: Literal["admin", "editor", "viewer"] = "editor"


class MemberOut(BaseModel):
    id: str
    user_id: str
    email: str
    name: str
    role: str
    created_at: datetime


class ApiKeyOut(BaseModel):
    id: str
    name: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None


class ApiKeyCreated(ApiKeyOut):
    key: str


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


# --- Projects -------------------------------------------------------------


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = ""


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None


class ProjectOut(ORMModel):
    id: str
    name: str
    description: str
    created_at: datetime
    video_count: int = 0


# --- Videos ---------------------------------------------------------------


class VideoOut(ORMModel):
    id: str
    workspace_id: str
    project_id: str | None
    title: str
    description: str
    source_type: str
    source_url: str | None
    original_filename: str | None
    mime_type: str
    size_bytes: int
    duration_seconds: float
    width: int
    height: int
    fps: float
    has_audio: bool
    language: str
    status: str
    progress: float
    error_message: str | None
    thumbnail_key: str | None
    created_at: datetime
    updated_at: datetime


class VideoDetail(VideoOut):
    has_transcript: bool = False
    transcript_language: str | None = None
    clip_count: int = 0
    approved_clip_count: int = 0
    analysis_provider: str | None = None
    metadata: dict | None = None


class ImportUrlRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2000)
    project_id: str | None = None
    title: str | None = None


class VideoUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    project_id: str | None = None


class TranscribeRequest(BaseModel):
    engine: Literal["auto", "faster_whisper", "openai", "mock"] = "auto"
    language: str | None = Field(default=None, max_length=16)
    force: bool = False


class AnalyzeRequest(BaseModel):
    provider: Literal["auto", "heuristic", "openai", "anthropic", "gemini", "ollama"] = "auto"
    target_duration_ms: int = Field(default=45000, ge=5000, le=180000)
    clip_count: int = Field(default=6, ge=1, le=20)
    replace_existing: bool = True


class WordOut(BaseModel):
    word: str
    start_ms: int
    end_ms: int
    confidence: float | None = None


class SegmentOut(ORMModel):
    id: str
    start_ms: int
    end_ms: int
    text: str
    speaker_id: str | None
    confidence: float
    words: list[dict] = []


class SpeakerOut(ORMModel):
    id: str
    label: str
    display_name: str | None
    color: str
    method: str


class TranscriptOut(BaseModel):
    id: str
    video_id: str
    language: str
    engine: str
    model: str
    status: str
    full_text: str
    word_count: int
    error_message: str | None = None
    segments: list[SegmentOut] = []
    speakers: list[SpeakerOut] = []


class SegmentUpdate(BaseModel):
    text: str = Field(min_length=0, max_length=4000)
    speaker_id: str | None = None
    start_ms: int | None = Field(default=None, ge=0)
    end_ms: int | None = Field(default=None, ge=0)


class SpeakerUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)


# --- Clips ----------------------------------------------------------------


class ClipOut(ORMModel):
    id: str
    video_id: str
    workspace_id: str
    start_ms: int
    end_ms: int
    duration_ms: int
    title: str
    description: str
    hook: str
    transcript_text: str
    explanation: str
    virality_score: float
    engagement_potential: float
    signals: dict
    aspect_ratio: str
    source: str
    status: str
    created_at: datetime


class ClipDetail(ClipOut):
    video_title: str = ""
    video_duration_seconds: float = 0
    has_editing_project: bool = False
    editing_project_id: str | None = None
    render_count: int = 0
    comment_count: int = 0
    open_comment_count: int = 0


class ClipUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = None
    hook: str | None = Field(default=None, max_length=300)
    start_ms: int | None = Field(default=None, ge=0)
    end_ms: int | None = Field(default=None, ge=0)
    aspect_ratio: AspectRatio | None = None
    status: Literal["suggested", "approved", "rejected"] | None = None


class ClipCreate(BaseModel):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=1)
    title: str = Field(default="Manual cut", max_length=240)
    aspect_ratio: AspectRatio = "9:16"


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)

    @field_validator("body")
    @classmethod
    def _comment_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Comment cannot be empty")
        return value.strip()


class CommentUpdate(BaseModel):
    body: str | None = Field(default=None, min_length=1, max_length=4000)
    resolved: bool | None = None

    @field_validator("body")
    @classmethod
    def _edit_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Comment cannot be empty")
        return value.strip() if value is not None else None


class CommentOut(BaseModel):
    id: str
    clip_id: str
    user_id: str
    author_name: str
    author_email: str
    body: str
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime
    mine: bool = False


class BulkClipRequest(BaseModel):
    action: Literal["approve", "reject", "delete", "merge"]
    clip_ids: list[str] = Field(min_length=1, max_length=50)


class WebhookCreate(BaseModel):
    url: str = Field(min_length=8, max_length=2000)
    description: str = Field(default="", max_length=160)
    events: list[str] = Field(default_factory=lambda: ["*"], max_length=50)
    enabled: bool = True


class WebhookUpdate(BaseModel):
    url: str | None = Field(default=None, min_length=8, max_length=2000)
    description: str | None = Field(default=None, max_length=160)
    events: list[str] | None = None
    enabled: bool | None = None


class WebhookOut(BaseModel):
    id: str
    url: str
    description: str
    events: list[str]
    enabled: bool
    secret: str
    created_at: datetime


class ShareCreate(BaseModel):
    expires_in_days: int | None = Field(default=None, ge=1, le=365)
    password: str | None = Field(default=None, max_length=128)


class ShareUnlock(BaseModel):
    password: str = ""


class ShareOut(BaseModel):
    id: str
    token: str
    url: str
    has_password: bool
    expires_at: datetime | None
    view_count: int
    created_at: datetime


class ClipContentOut(BaseModel):
    titles: list[str]
    hooks: list[str]
    descriptions: list[str]
    hashtags: list[str]
    captions: dict[str, str]
    thumbnail_ideas: list[str]
    calls_to_action: list[str]
    summary: str
    provider: str
    model: str


# --- Editor / rendering ---------------------------------------------------


class CaptionStyleOut(ORMModel):
    id: str
    name: str
    is_builtin: bool
    config: dict


class CaptionStyleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    config: dict


class EditorCreate(BaseModel):
    clip_id: str | None = None
    video_id: str | None = None
    name: str = Field(default="", max_length=160)
    aspect_ratio: AspectRatio = "9:16"


class EditorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    aspect_ratio: AspectRatio | None = None
    width: int | None = Field(default=None, ge=240, le=3840)
    height: int | None = Field(default=None, ge=240, le=3840)
    trim_start_ms: int | None = Field(default=None, ge=0)
    trim_end_ms: int | None = Field(default=None, ge=0)
    focus_x: float | None = Field(default=None, ge=0, le=1)
    focus_y: float | None = Field(default=None, ge=0, le=1)
    caption_style_id: str | None = None
    captions_enabled: bool | None = None
    caption_overrides: dict | None = None
    overlays: list[dict] | None = None
    music: dict | None = None
    audio: dict | None = None
    operations: list[dict] | None = None


class EditorOut(ORMModel):
    id: str
    workspace_id: str
    video_id: str
    clip_id: str | None
    name: str
    aspect_ratio: str
    width: int
    height: int
    trim_start_ms: int
    trim_end_ms: int
    focus_x: float
    focus_y: float
    caption_style_id: str | None
    captions_enabled: bool
    caption_overrides: dict
    overlays: list
    music: dict | None
    audio: dict
    operations: list
    status: str
    created_at: datetime
    updated_at: datetime


class EditorDetail(EditorOut):
    video_title: str = ""
    video_duration_seconds: float = 0
    video_width: int = 0
    video_height: int = 0
    transcript: TranscriptOut | None = None
    latest_render: "RenderOut | None" = None


class RenderRequest(BaseModel):
    preset: Literal["tiktok", "reels", "shorts", "square", "landscape", "portrait", "custom"] = "tiktok"
    format: Literal["mp4", "mov", "webm"] = "mp4"
    width: int | None = Field(default=None, ge=240, le=3840)
    height: int | None = Field(default=None, ge=240, le=3840)


class RenderOut(ORMModel):
    id: str
    editing_project_id: str
    preset: str
    format: str
    status: str
    progress: float
    attempts: int
    error_message: str | None
    output_size_bytes: int
    render_seconds: float
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class RenderDetail(RenderOut):
    export_id: str | None = None
    download_url: str | None = None
    thumbnail_url: str | None = None
    project_name: str = ""
    video_title: str = ""


class ExportOut(ORMModel):
    id: str
    render_job_id: str
    clip_id: str | None
    title: str
    filename: str
    format: str
    width: int
    height: int
    duration_ms: int
    size_bytes: int
    created_at: datetime
    download_url: str = ""
    thumbnail_url: str | None = None


# --- Publishing -----------------------------------------------------------


class SocialAccountOut(ORMModel):
    id: str
    platform: str
    account_name: str
    external_id: str
    status: str
    scopes: str
    token_expires_at: datetime | None
    last_error: str | None
    created_at: datetime


class ConnectStartOut(BaseModel):
    platform: str
    configured: bool
    authorize_url: str | None = None
    message: str = ""


class PublishRequest(BaseModel):
    exported_video_id: str
    social_account_id: str
    title: str = Field(default="", max_length=240)
    caption: str = Field(default="", max_length=5000)
    hashtags: str = Field(default="", max_length=500)
    privacy: Literal["public", "unlisted", "private"] = "public"
    scheduled_for: datetime | None = None
    publish_now: bool = False


class PublishingJobOut(ORMModel):
    id: str
    exported_video_id: str
    social_account_id: str
    platform: str
    title: str
    caption: str
    hashtags: str
    privacy: str
    scheduled_for: datetime | None
    status: str
    external_post_id: str | None
    external_url: str | None
    attempts: int
    error_message: str | None
    published_at: datetime | None
    created_at: datetime
    account_name: str = ""
    video_title: str = ""


class PublishAttemptResult(BaseModel):
    status: str
    detail: str
    external_post_id: str | None = None
    external_url: str | None = None


# --- Analytics ------------------------------------------------------------


class AnalyticsOverview(BaseModel):
    totals: dict[str, Any]
    platform_breakdown: list[dict[str, Any]]
    series: list[dict[str, Any]]
    top_posts: list[dict[str, Any]]
    data_sources: list[str]
    notes: list[str]


class AnalyticsEntry(BaseModel):
    publishing_job_id: str
    views: int = Field(default=0, ge=0)
    likes: int = Field(default=0, ge=0)
    comments: int = Field(default=0, ge=0)
    shares: int = Field(default=0, ge=0)
    watch_time_seconds: float = Field(default=0, ge=0)
    retention_pct: float = Field(default=0, ge=0, le=100)


class AnalyticsSyncOut(BaseModel):
    synced: int
    skipped: int
    messages: list[str]


# --- AI settings ----------------------------------------------------------


class AiProviderOut(BaseModel):
    provider: str
    label: str
    model: str
    base_url: str
    configured: bool
    has_workspace_key: bool
    enabled: bool
    is_default: bool
    capabilities: list[str]
    local: bool


class AiProviderUpdate(BaseModel):
    provider: Literal["openai", "anthropic", "gemini", "ollama"]
    model: str = ""
    base_url: str = ""
    api_key: str | None = None
    enabled: bool = True
    is_default: bool = False


class AiTestRequest(BaseModel):
    provider: Literal["openai", "anthropic", "gemini", "ollama", "heuristic"] = "heuristic"


class AiTestResult(BaseModel):
    provider: str
    ok: bool
    message: str
    latency_ms: int


# --- Misc -----------------------------------------------------------------


class NotificationOut(ORMModel):
    id: str
    type: str
    title: str
    body: str
    read_at: datetime | None
    created_at: datetime


class ActivityOut(BaseModel):
    id: str
    action: str
    target_type: str
    target_id: str
    user_email: str | None
    created_at: datetime
    meta: dict = {}


class SystemStatus(BaseModel):
    ffmpeg: bool
    ffmpeg_version: str
    transcription_engines: dict[str, Any]
    ai_providers: dict[str, Any]
    redis: bool
    storage: str
    database: str
    job_runner: str
    ytdlp: bool


class DashboardOut(BaseModel):
    counts: dict[str, int]
    storage_bytes: int
    processing: list[dict[str, Any]]
    recent_videos: list[VideoOut]
    recent_clips: list[ClipOut]
    recent_activity: list[ActivityOut]
    usage: dict[str, Any]
    renders: list[RenderOut]
    notifications: list[NotificationOut]


class Paginated(BaseModel):
    items: list[Any]
    total: int
    limit: int
    offset: int


EditorDetail.model_rebuild()
RenderDetail.model_rebuild()