# FireClip API + worker image. Python 3.12 is required for faster-whisper/PyAV.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data \
    APP_ENV=production \
    AUTO_MIGRATE=false

# FFmpeg with libx264/libass, fonts for burned-in captions, OpenCV runtime libs.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        fonts-dejavu-core \
        libglib2.0-0 \
        libgomp1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements-transcription.txt requirements-postgres.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt -r requirements-postgres.txt -r requirements-transcription.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh \
    && addgroup --system fireclip \
    && adduser --system --ingroup fireclip fireclip \
    && mkdir -p /data \
    && chown -R fireclip:fireclip /app /data

USER fireclip

EXPOSE 8000

HEALTHCHECK --interval=20s --timeout=5s --start-period=40s --retries=5 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["api"]
