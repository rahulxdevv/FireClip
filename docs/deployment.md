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

## Resource limits

Compose limits every container by default so the stack cannot take the whole VPS: Postgres 0.5 CPU / 512 MB, Redis 0.25 CPU / 256 MB, API 1 CPU / 1 GB, worker 2 CPU / 4 GB, web 0.75 CPU / 768 MB. Change any of them in `.env`:

```dotenv
WORKER_CPUS=3.0
WORKER_MEMORY=6G
POSTGRES_MEMORY=1G
```

The worker cap is the one that matters most for transcription and FFmpeg. Keep it above the memory your Whisper model needs, or lower `WHISPER_MODEL` and `WORKER_CONCURRENCY`. Media is also capped per workspace at 50 GB (`MAX_WORKSPACE_STORAGE_GB`) and uploads at 4 GB (`MAX_UPLOAD_MB`).

## Admin account

The first account is the owner of its workspace. To promote another existing account after it has registered:

```bash
docker compose exec api python -m app.cli make-admin you@example.com
```

The command defaults to the `owner` role, which is the highest level. Add `--workspace <slug>` to change one workspace only, or `--role admin` to grant admin without ownership.

## Any VPS with Docker

```bash
git clone https://github.com/rahulxdevv/FireClip.git
cd FireClip
cp .env.example .env
# set JWT_SECRET, FRONTEND_URL, BACKEND_PUBLIC_URL, COOKIE_SECURE=true
docker compose up --build -d
```

Put Caddy, Nginx or Traefik in front of the published host ports (`3000` and `8000` by default, or `WEB_PORT`/`API_PORT` if you changed them), terminate TLS there, and set the OAuth callback base URL to your public web origin. Details are in [Production self-hosting](#production-self-hosting).

## Dokploy

Dokploy can deploy this repository in either of two ways. The short answer: **yes, a Docker Compose deployment works with only `JWT_SECRET` set**, because PostgreSQL and Redis are created as services inside the Compose stack. No external database or Redis is required for the core product. A single-container deployment of the root `Dockerfile` also works with only `JWT_SECRET`, using SQLite and inline jobs.

### Recommended: Compose application

1. In Dokploy, create a **Compose** application and connect `github.com/rahulxdevv/FireClip`.
2. Use the repository `docker-compose.yml`.
3. Add `JWT_SECRET` (32+ random bytes) in the environment editor.
4. Attach your domain to the **web** service with container port `WEB_CONTAINER_PORT` (`3000` by default). If Dokploy already uses host port `3000`, set `WEB_PORT=3009`; this changes only the published host port, not the domain target. Set `API_PORT=8008` too if host port `8000` is taken. If you deliberately change `WEB_CONTAINER_PORT`, update the domain port to match and rebuild.
5. Deploy. The stack starts PostgreSQL, Redis, the API, the worker and the web app automatically.

A 502 from Dokploy usually means the domain points at the wrong container port. The web domain must target `WEB_CONTAINER_PORT` (`3000` by default), regardless of `WEB_PORT`.

For a public production install, also set:

```dotenv
FRONTEND_URL=https://your-domain.example
BACKEND_PUBLIC_URL=https://your-domain.example
CORS_ORIGINS=https://your-domain.example
COOKIE_SECURE=true
POSTGRES_PASSWORD=<a real password>
```

The web container proxies `/api` and `/health` to the internal API at `http://fireclip-api:API_CONTAINER_PORT` (the unique network alias of the `api` service), so you do not need a public API domain. The alias exists because Dokploy attaches every project to the shared `dokploy-network`, where a generic `api` name can belong to another app's container; the generic name still resolves inside this stack, but only `fireclip-api` is guaranteed to be this stack's API. If you enable publishing, use the same public web origin as `BACKEND_PUBLIC_URL`; the OAuth callback path is proxied by Next.js. Do not enable `AUTO_MIGRATE=true` with Compose, because the API entrypoint already runs Alembic.

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
    request_body {
        max_size 4GB
    }
}
```

The proxy targets the container ports: web `3000` and API `8000` by default, or `WEB_CONTAINER_PORT`/`API_CONTAINER_PORT` if you changed them. `WEB_PORT` and `API_PORT` change only the published host ports. The web app proxies `/api` and `/health`, so the API does not need its own public hostname.

Nginx: set `client_max_body_size 4g;` and `proxy_request_buffering off;` for large uploads. Uvicorn already runs with `--proxy-headers`. Set `COOKIE_SECURE=true`, real public URLs and matching CORS origins when TLS is enabled.

OAuth callbacks must match exactly:

```text
https://app.example.com/api/publishing/callback/{platform}
```

Use the same origin as `BACKEND_PUBLIC_URL`. If you intentionally expose a separate API domain, replace the host with that domain.

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
