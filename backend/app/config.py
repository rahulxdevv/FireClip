"""Application configuration.

Everything is environment driven so the same image can run in development,
Docker Compose, or a production deployment without code changes.
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader (avoids an extra dependency).

    Existing environment variables always win over file values.
    """
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(BASE_DIR / ".env")
_load_dotenv(BASE_DIR.parent / ".env")


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _database_url() -> str:
    """Read DATABASE_URL and use the installed psycopg 3 driver for Postgres.

    Hosted providers (Render, Railway, Heroku) hand out ``postgres://`` or
    ``postgresql://`` URLs. SQLAlchemy would otherwise look for psycopg2, which
    this image does not install. Normalising here keeps every provider working
    with one dependency.
    """
    raw = os.getenv(
        "DATABASE_URL", f"sqlite:///{(BASE_DIR / 'data' / 'fireclip.db').as_posix()}"
    ).strip()
    if raw.startswith("postgres://"):
        return "postgresql+psycopg://" + raw[len("postgres://") :]
    if raw.startswith("postgresql://"):
        return "postgresql+psycopg://" + raw[len("postgresql://") :]
    return raw


@dataclass
class Settings:
    app_name: str = "FireClip"
    environment: str = os.getenv("APP_ENV", "development")
    debug: bool = _bool("DEBUG", True)

    # Storage / data
    data_dir: Path = field(
        default_factory=lambda: Path(os.getenv("DATA_DIR", str(BASE_DIR / "data"))).resolve()
    )
    storage_backend: str = os.getenv("STORAGE_BACKEND", "local")  # local | s3
    s3_bucket: str = os.getenv("S3_BUCKET", "")
    s3_endpoint_url: str = os.getenv("S3_ENDPOINT_URL", "")
    s3_region: str = os.getenv("S3_REGION", "us-east-1")
    s3_access_key: str = os.getenv("S3_ACCESS_KEY_ID", "")
    s3_secret_key: str = os.getenv("S3_SECRET_ACCESS_KEY", "")
    s3_prefix: str = os.getenv("S3_PREFIX", "fireclip")
    media_public_base_url: str = os.getenv("MEDIA_PUBLIC_BASE_URL", "")

    # Database
    database_url: str = field(default_factory=_database_url)
    auto_migrate: bool = _bool("AUTO_MIGRATE", True)

    # Redis / workers
    redis_url: str = os.getenv("REDIS_URL", "")
    job_runner: str = os.getenv("JOB_RUNNER", "auto")  # auto | inline | arq
    worker_concurrency: int = _int("WORKER_CONCURRENCY", 2)
    render_concurrency: int = _int("RENDER_CONCURRENCY", 1)

    # Local server (used by python -m app and the dev script)
    api_host: str = os.getenv("API_HOST", "127.0.0.1")
    api_port: int = _int("API_PORT", 8000)

    # Auth
    jwt_secret: str = os.getenv("JWT_SECRET", "")
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = _int("ACCESS_TOKEN_MINUTES", 60)
    refresh_token_days: int = _int("REFRESH_TOKEN_DAYS", 30)
    cookie_secure: bool = _bool("COOKIE_SECURE", False)
    cookie_domain: str = os.getenv("COOKIE_DOMAIN", "")
    session_cookie: str = "fireclip_session"
    refresh_cookie: str = "fireclip_refresh"
    allow_registration: bool = _bool("ALLOW_REGISTRATION", True)
    require_email_verification: bool = _bool("REQUIRE_EMAIL_VERIFICATION", False)
    email_verification_hours: int = _int("EMAIL_VERIFICATION_HOURS", 48)
    password_reset_minutes: int = _int("PASSWORD_RESET_MINUTES", 60)
    invite_expiry_days: int = _int("INVITE_EXPIRY_DAYS", 7)

    # Transactional email (SMTP). Without it, links are written to the log so a
    # self-hosted install still works end to end.
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = _int("SMTP_PORT", 587)
    smtp_username: str = os.getenv("SMTP_USERNAME", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_starttls: bool = _bool("SMTP_STARTTLS", True)
    smtp_ssl: bool = _bool("SMTP_SSL", False)
    smtp_timeout: int = _int("SMTP_TIMEOUT_SECONDS", 15)
    mail_from: str = os.getenv("MAIL_FROM", "no-reply@fireclip.local")
    mail_from_name: str = os.getenv("MAIL_FROM_NAME", "FireClip")

    # Billing (Stripe). Optional: self-hosted installs can stay on the free plan.
    stripe_secret_key: str = os.getenv("STRIPE_SECRET_KEY", "")
    stripe_webhook_secret: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    stripe_portal_configuration: str = os.getenv("STRIPE_PORTAL_CONFIGURATION_ID", "")
    stripe_api_base: str = os.getenv("STRIPE_API_BASE", "https://api.stripe.com")
    stripe_price_starter_month: str = os.getenv("STRIPE_PRICE_STARTER_MONTH", "")
    stripe_price_starter_year: str = os.getenv("STRIPE_PRICE_STARTER_YEAR", "")
    stripe_price_studio_month: str = os.getenv("STRIPE_PRICE_STUDIO_MONTH", "")
    stripe_price_studio_year: str = os.getenv("STRIPE_PRICE_STUDIO_YEAR", "")
    stripe_price_agency_month: str = os.getenv("STRIPE_PRICE_AGENCY_MONTH", "")
    stripe_price_agency_year: str = os.getenv("STRIPE_PRICE_AGENCY_YEAR", "")

    # CORS / URLs
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    backend_public_url: str = os.getenv("BACKEND_PUBLIC_URL", "http://localhost:8000")
    cors_origins: list[str] = field(
        default_factory=lambda: [
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
            ).split(",")
            if origin.strip()
        ]
    )

    # Media
    ffmpeg_bin: str = os.getenv("FFMPEG_BIN", "ffmpeg")
    ffprobe_bin: str = os.getenv("FFPROBE_BIN", "ffprobe")
    ytdlp_bin: str = os.getenv("YTDLP_BIN", "yt-dlp")
    max_upload_mb: int = _int("MAX_UPLOAD_MB", 4096)
    max_import_minutes: int = _int("MAX_IMPORT_MINUTES", 600)
    allowed_video_ext: tuple[str, ...] = (
        ".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".mpg", ".mpeg", ".flv", ".ts",
    )
    allowed_audio_ext: tuple[str, ...] = (
        ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".opus",
    )
    allowed_image_ext: tuple[str, ...] = (".png", ".jpg", ".jpeg", ".webp", ".gif")
    # Optional campaign discovery feed (JSON). Used for Content Rewards-style
    # campaign imports; there is no scraping fallback when this is unset.
    campaign_feed_url: str = os.getenv("CAMPAIGN_FEED_URL", "")
    campaign_feed_token: str = os.getenv("CAMPAIGN_FEED_TOKEN", "")
    campaign_feed_label: str = os.getenv("CAMPAIGN_FEED_LABEL", "Content Rewards")
    hwaccel: str = os.getenv("HWACCEL", "")  # e.g. nvenc, vaapi, videotoolbox
    loudness_target: float = _float("LOUDNESS_TARGET", -16.0)
    render_crf: int = _int("RENDER_CRF", 20)
    render_x264_preset: str = os.getenv("RENDER_X264_PRESET", "veryfast")
    auto_pipeline: bool = _bool("AUTO_PIPELINE", True)
    default_clip_count: int = _int("DEFAULT_CLIP_COUNT", 6)
    default_clip_duration_ms: int = _int("DEFAULT_CLIP_DURATION_MS", 45000)

    # Transcription
    transcription_engine: str = os.getenv("TRANSCRIPTION_ENGINE", "auto")
    whisper_model: str = os.getenv("WHISPER_MODEL", "base")
    whisper_device: str = os.getenv("WHISPER_DEVICE", "cpu")
    whisper_compute_type: str = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    whisper_beam_size: int = _int("WHISPER_BEAM_SIZE", 5)
    whisper_cpu_threads: int = _int("WHISPER_CPU_THREADS", 0)
    allow_mock_transcription: bool = _bool("ALLOW_MOCK_TRANSCRIPTION", False)
    default_language: str = os.getenv("DEFAULT_LANGUAGE", "en")
    diarization_mode: str = os.getenv("DIARIZATION_MODE", "off")

    # AI
    ai_provider: str = os.getenv("AI_PROVIDER", "auto")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_base_url: str = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_base_url: str = os.getenv(
        "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
    )
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.1")
    ai_timeout_seconds: int = _int("AI_TIMEOUT_SECONDS", 90)

    # OAuth / publishing
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    facebook_client_id: str = os.getenv("FACEBOOK_CLIENT_ID", "")
    facebook_client_secret: str = os.getenv("FACEBOOK_CLIENT_SECRET", "")
    instagram_client_id: str = os.getenv("INSTAGRAM_CLIENT_ID", "")
    instagram_client_secret: str = os.getenv("INSTAGRAM_CLIENT_SECRET", "")
    tiktok_client_key: str = os.getenv("TIKTOK_CLIENT_KEY", "")
    tiktok_client_secret: str = os.getenv("TIKTOK_CLIENT_SECRET", "")

    # Limits
    rate_limit_auth_per_minute: int = _int("RATE_LIMIT_AUTH_PER_MINUTE", 20)
    rate_limit_api_per_minute: int = _int("RATE_LIMIT_API_PER_MINUTE", 240)
    plan_clip_limit: int = _int("PLAN_CLIP_LIMIT", 500)
    plan_render_minutes: int = _int("PLAN_RENDER_MINUTES", 600)

    def __post_init__(self) -> None:
        if not self.jwt_secret:
            if self.environment == "production":
                raise RuntimeError("JWT_SECRET must be set in production")
            self.jwt_secret = "dev-only-insecure-secret-change-me"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        for sub in ("uploads", "renders", "thumbnails", "audio", "assets", "tmp"):
            (self.data_dir / sub).mkdir(parents=True, exist_ok=True)

    @property
    def secrets_encryption_key(self) -> bytes:
        # Derived from JWT secret so a single secret bootstraps encrypted storage.
        import hashlib

        return hashlib.sha256(f"fireclip-secrets::{self.jwt_secret}".encode()).digest()

    def provider_key(self, provider: str) -> str:
        return {
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
            "gemini": self.gemini_api_key,
            "ollama": "local",
        }.get(provider, "")

    @property
    def email_configured(self) -> bool:
        return bool(self.smtp_host and self.mail_from)

    @property
    def billing_configured(self) -> bool:
        return bool(self.stripe_secret_key and self.price_map)

    @property
    def price_map(self) -> dict[str, str]:
        return {
            "starter:month": self.stripe_price_starter_month,
            "starter:year": self.stripe_price_starter_year,
            "studio:month": self.stripe_price_studio_month,
            "studio:year": self.stripe_price_studio_year,
            "agency:month": self.stripe_price_agency_month,
            "agency:year": self.stripe_price_agency_year,
        }

    @property
    def use_arq(self) -> bool:
        if self.job_runner == "arq":
            return True
        if self.job_runner == "inline":
            return False
        return bool(self.redis_url)


settings = Settings()

# Surface a generated dev secret so cookies survive a restart in local dev.
if settings.environment != "production" and not os.getenv("JWT_SECRET"):
    _DEV_SECRET_FILE = settings.data_dir / ".dev_jwt_secret"
    if _DEV_SECRET_FILE.exists():
        settings.jwt_secret = _DEV_SECRET_FILE.read_text(encoding="utf-8").strip()
    else:
        settings.jwt_secret = secrets.token_urlsafe(48)
        _DEV_SECRET_FILE.write_text(settings.jwt_secret, encoding="utf-8")