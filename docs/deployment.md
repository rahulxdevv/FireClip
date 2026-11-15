# Deployment

[← Back to README](../README.md)

## Render (one-click demo)

1. Push this repository to `github.com/rahulxdevv/FireClip` (the button in the README uses that repo).
2. Click **Deploy to Render** and approve the Blueprint.
3. Wait for the Docker build (FFmpeg + faster-whisper make it a few minutes).
4. Open the service URL and register.

What the Blueprint provisions:

- One Docker service running the web app, API and inline job runner
- A generated `JWT_SECRET`
- A free Render PostgreSQL database, wired through `DATABASE_URL`
- Alembic migrations on startup
- `/health` probe through the Next.js rewrite
- `COOKIE_SECURE=true`, production CORS and public URLs

Before you rely on it:

- **The free plan sleeps** after inactivity and has 512 MB RAM. Whisper `tiny` may still be slow or hit memory limits. Use a paid instance or hosted Whisper for real work.
- **Media storage is ephemeral** on the free plan. Uploads survive while the instance runs, then disappear on redeploy/restart. Attach a paid disk or configure S3 (`STORAGE_BACKEND=s3`) for persistence.
- **No OAuth or AI keys are included.** Add them in the Render dashboard after the first deploy.
- If Render says the service name is taken, rename `fireclip-rahulxdevv` in `render.yaml` and update `FRONTEND_URL`, `BACKEND_PUBLIC_URL` and `CORS_ORIGINS` to match.

For a production deployment with a separate worker, use Docker Compose instead. The all-in-one image is intentionally a low-friction demo, not the recommended scale-out topology.

## Any VPS with Docker

```bash
git clone https://github.com/rahulxdevv/FireClip.git
cd FireClip
cp .env.example .env
# set JWT_SECRET, FRONTEND_URL, BACKEND_PUBLIC_URL, COOKIE_SECURE=true
docker compose up --build -d
```

Put Caddy, Nginx or Traefik in front of ports `3000` and `8000` (`WEB_PORT` and `API_PORT` if you changed them), terminate TLS there, and set the OAuth callback base URL to your API domain. Details are in [Production self-hosting](#production-self-hosting).

## Dokploy

Dokploy can deploy this repository in either of two ways. The short answer: **yes, a Docker Compose deployment works with only `JWT_SECRET` set**, because PostgreSQL and Redis are created as services inside the Compose stack. No external database or Redis is required for the core product. A single-container deployment of the root `Dockerfile` also works with only `JWT_SECRET`, using SQLite and inline jobs.

### Recommended: Compose application

1. In Dokploy, create a **Compose** application and connect `github.com/rahulxdevv/FireClip`.
2. Use the repository `docker-compose.yml`.
3. Add `JWT_SECRET` (32+ random bytes) in the environment editor.
4. Attach your domain to the **web** service. The port must be the one the container listens on: `3000` by default, or your `WEB_PORT` if you changed it. Set `WEB_PORT` and `API_PORT` in the same environment editor when 3000/8000 are already taken on the host; the containers bind to those numbers, so the domain port matches.
5. Deploy. The stack starts PostgreSQL, Redis, the API, the worker and the web app automatically.

A 502 from Dokploy usually means the domain points at a port nothing is listening on inside the container. The host mapping (`WEB_PORT:WEB_PORT`) and the domain port must agree.

For a public production install, also set:

```dotenv
FRONTEND_URL=https://your-domain.example
BACKEND_PUBLIC_URL=https://your-domain.example
CORS_ORIGINS=https://your-domain.example
COOKIE_SECURE=true
POSTGRES_PASSWORD=<a real password>
```

The web container proxies `/api` to the internal `api` service, so you do not need to publish the API port. If you enable publishing, use the same public web origin as `BACKEND_PUBLIC_URL`; the OAuth callback path is proxied by Next.js. Do not enable `AUTO_MIGRATE=true` with Compose, because the API entrypoint already runs Alembic.

### Single application: root Dockerfile

1. Create an **Application** in Dokploy and select Dockerfile mode with `./Dockerfile`.
2. Set `JWT_SECRET` only.
3. Mount a persistent volume at `/data` (recommended).
4. Expose container port `10000` (or set `PORT`).

This runs Next.js and FastAPI in one container with SQLite and inline jobs. It needs no PostgreSQL or Redis, but it has no separate worker and no scale-out. Without a `/data` volume, the database and uploads are lost on redeploy.

**Do not** split only the API or only the web app into separate Dokploy applications unless you also provide the missing database, Redis, API URL and CORS configuration yourself.

## Production self-hosting

### Reverse proxy, TLS and uploads

Example Caddy:

```caddy
app.example.com {
    reverse_proxy web:3000
}
api.example.com {
    reverse_proxy api:8000
    request_body {
        max_size 4GB
    }
}
```

The proxy targets the container port, which follows `WEB_PORT`/`API_PORT`: if you set `WEB_PORT=3009` and `API_PORT=8008`, use `reverse_proxy web:3009` and `reverse_proxy api:8008`.

Nginx: set `client_max_body_size 4g;` and `proxy_request_buffering off;` for large uploads. Uvicorn already runs with `--proxy-headers`. Set `COOKIE_SECURE=true`, real public URLs and matching CORS origins when TLS is enabled.

OAuth callbacks must match exactly:

```text
https://api.example.com/api/publishing/callback/{platform}
```

### Storage, scaling and backups

- Compose uses a named `media` volume. For multiple hosts or Instagram Reels, use S3.
- The API enqueues jobs in Redis; workers consume them. Scale workers horizontally; FFmpeg is CPU-heavy, so prefer more workers over raising concurrency.
- The worker cron enqueues due scheduled posts every minute. Without a worker, scheduled posts remain scheduled and the UI shows that.
- Back up PostgreSQL, the media volume/S3 bucket, and `.env` separately.
- `job_timeout` is 3600 seconds; increase it in `app/worker.py` for very long sources.

```bash
docker compose exec -T postgres pg_dump -U fireclip fireclip > backup.sql
docker run --rm -v fireclip_media:/data -v "$PWD":/backup alpine \
  tar czf /backup/media.tgz -C /data .
```

### Upgrades and operations checklist

```bash
git pull
docker compose build
docker compose up -d
docker compose logs -f api      # migrations run before the API starts
```

- [ ] Unique `JWT_SECRET` stored in a secret manager
- [ ] `COOKIE_SECURE=true` behind TLS
- [ ] `ALLOW_MOCK_TRANSCRIPTION=false`
- [ ] Real `FRONTEND_URL`, `BACKEND_PUBLIC_URL`, `CORS_ORIGINS`
- [ ] OAuth callback URLs registered with each platform
- [ ] Worker running and Redis reachable
- [ ] Media volume/S3 backed up
- [ ] Proxy upload limit matches `MAX_UPLOAD_MB`
- [ ] FFmpeg built with libass and libx264
