# FireClip all-in-one image for one-click hosts (Render, Fly.io, a single VM).
# It runs the Next.js web app and the FastAPI API in one container with the
# inline job runner. For a multi-service production setup use docker-compose.yml.

FROM node:22-bookworm-slim AS webbuild
WORKDIR /web
ENV NEXT_TELEMETRY_DISABLED=1 \
    API_BASE_URL=http://127.0.0.1:8000
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production \
    DATA_DIR=/data \
    AUTO_MIGRATE=false \
    JOB_RUNNER=inline \
    NEXT_TELEMETRY_DISABLED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        fonts-dejavu-core \
        supervisor \
        curl \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# The Next.js standalone server needs Node at runtime. Copy the same Node 22
# binary used for the build into this Debian-based Python image.
COPY --from=node:22-bookworm-slim /usr/local/bin/node /usr/local/bin/node

WORKDIR /app/backend

COPY backend/requirements.txt backend/requirements-postgres.txt backend/requirements-transcription.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt -r requirements-postgres.txt -r requirements-transcription.txt

COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/app ./app

COPY --from=webbuild /web/.next/standalone /web
COPY --from=webbuild /web/.next/static /web/.next/static
COPY --from=webbuild /web/public /web/public

COPY deploy/supervisord.conf /etc/supervisor/conf.d/fireclip.conf
COPY deploy/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh \
    && addgroup --system fireclip \
    && adduser --system --ingroup fireclip --home /home/fireclip fireclip \
    && mkdir -p /data /home/fireclip/.cache \
    && chown -R fireclip:fireclip /app /web /data /home/fireclip

USER fireclip

ENV HOME=/home/fireclip \
    PORT=10000

EXPOSE 10000

HEALTHCHECK --interval=25s --timeout=5s --start-period=50s --retries=5 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/health" || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
