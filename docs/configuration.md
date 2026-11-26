# Configuration

[← Back to README](../README.md)

FireClip runs on ordinary CPUs. Local Whisper and FFmpeg are the heavy parts, so size the host around those.

## System requirements

| Profile | CPU | RAM | Free disk | Good for |
| --- | --- | --- | --- | --- |
| Minimum | 2 vCPU | 2 GB | 10 GB | UI and API, 720p clips, hosted or tiny Whisper, one job at a time |
| Recommended | 4 vCPU | 8 GB | 30 GB SSD | Self-host with base Whisper, 1080p renders, one render at a time |
| High volume | 8 vCPU | 16 GB+ | 100 GB+ | Multiple workers, medium Whisper model, parallel renders |

- **OS:** Linux with Docker is recommended for servers. macOS and Windows work through Docker Desktop or the local developer setup.
- **Local toolchain:** Python 3.10-3.12, Node 20+, FFmpeg 6+ with libx264 and libass, and a current Chrome, Firefox, Safari or Edge.
- **Network:** outbound HTTPS for AI providers, URL imports and publishing; inbound 80/443 when self-hosting.
- **Disk budget:** media plus exports typically need about 1.5x the source size. Docker images plus Whisper models add roughly 4 GB.
- **GPU:** optional. NVENC can speed up H.264 rendering, but CPU encoding works everywhere.
- **Render free plan:** 512 MB is a demo environment, not a production target. Use the Compose stack or a paid instance for real transcription.

There is no hardware combination that makes every workload instant. FireClip limits concurrent ASR to one per process and caps concurrent renders, so jobs wait in a queue instead of exhausting RAM and failing unpredictably.

## Environment variables

Copy [`.env.example`](../.env.example) to `.env`. The essentials:

| Variable | Default | Description |
| --- | --- | --- |
| `JWT_SECRET` | generated in dev | **Required in production.** Signs sessions and derives the AES key for stored secrets. 32+ bytes. |
| `DATABASE_URL` | SQLite | `postgresql+psycopg://…`; plain `postgres://` URLs are normalized automatically. |
| `REDIS_URL` | empty | Enables ARQ. Without it, jobs run inline. |
| `JOB_RUNNER` | `auto` | `auto`, `inline` or `arq`. |
| `FRONTEND_URL` | `http://localhost:3000` | Web origin used for OAuth redirects and CORS. |
| `BACKEND_PUBLIC_URL` | `http://localhost:8000` | Public app origin used to build OAuth callbacks. In Compose, use the web origin (`http://localhost:3000`); Next proxies the callback to the API. |
| `COOKIE_SECURE` | `false` | Set `true` behind HTTPS. |
| `TRANSCRIPTION_ENGINE` | `auto` | `faster_whisper`, `whisper`, `openai`, `auto`. |
| `AI_PROVIDER` | `auto` | `heuristic`, `openai`, `anthropic`, `gemini`, `ollama`. |
| `WHISPER_MODEL` | `base` | `tiny` for low-memory hosts, `small`/`medium` for quality. |
| `STORAGE_BACKEND` | `local` | `local` or `s3`. |
| `MAX_UPLOAD_MB` | `4096` | Enforced by the API; match your proxy body limit. |
| `MIN_FREE_DISK_GB` | `2` (Compose: `5`) | Refuse uploads and renders below this much free local media space. |
| `MAX_WORKSPACE_STORAGE_GB` | `0` (Compose: `50`) | Per-workspace media cap; `0` disables it. |
| `STATIC_SCREEN_FILTER` | `true` | Skip frozen screens, slates and ad cards when proposing clips. |
| `STATIC_SCREEN_THRESHOLD` | `1.0` | Motion threshold for still-screen detection. |
| `STATIC_SCREEN_MIN_SECONDS` | `6` | Minimum still duration before a range is skipped. |
| `STATIC_SCREEN_MAX_OVERLAP` | `0.35` | Skip a candidate when this share of it is still. |
| `PLAN_CLIP_LIMIT` | `300` | Monthly clip allowance for new workspaces; overrides the entry plan. |
| `PLAN_RENDER_MINUTES` | `300` | Monthly render-minute allowance for new workspaces; overrides the entry plan. |
| `REQUIRE_EMAIL_VERIFICATION` | `false` | Block sign-in until the email link is confirmed. Requires SMTP. |
| `SMTP_HOST`, `SMTP_PORT` | empty, `587` | Transactional email for verification, reset and invitations. |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | empty | SMTP credentials; STARTTLS or implicit SSL is supported. |
| `MAIL_FROM`, `MAIL_FROM_NAME` | `no-reply@fireclip.local`, `FireClip` | Sender identity on outgoing mail. |
| `STRIPE_SECRET_KEY` | empty | Enables Checkout and the customer portal. |
| `STRIPE_WEBHOOK_SECRET` | empty | Required to verify subscription and invoice webhooks. |
| `CAMPAIGN_FEED_URL` | empty | JSON feed used by Campaign discovery; http(s), public hosts only. Without it discovery reports "not configured". |
| `CAMPAIGN_FEED_TOKEN` | empty | Optional bearer token for the campaign feed. |
| `CAMPAIGN_FEED_LABEL` | `Content Rewards` | Display label for the feed on the Campaigns page. |
| `ALLOW_MOCK_TRANSCRIPTION` | `false` | Tests/demos only. Mock output is labelled in the UI. |
| `API_HOST` | `127.0.0.1` | Local API bind address. Use `0.0.0.0` only when exposing it directly. |
| `API_PORT` | `8000` | API port for the local runner, and the published host port for Compose. |
| `WEB_PORT` | `3000` | Web port for the local runner, and the published host port for Compose. |
| `API_CONTAINER_PORT` | `8000` | Internal API container port in Compose. Rebuild after changing it, because Next bakes the API origin into its rewrites. |
| `WEB_CONTAINER_PORT` | `3000` | Internal web container port in Compose. Point the Dokploy domain or reverse proxy at this port. |
| `PORT` | `10000` | Public web port for the all-in-one Dockerfile and cloud hosts. |
| `WORKER_CONCURRENCY` | `2` | Jobs processed concurrently by a worker or inline pool. |
| `RENDER_CONCURRENCY` | `1` | Concurrent FFmpeg encodes per process. |
| `WHISPER_BEAM_SIZE` | `5` | Lower is faster; `1` is the low-power option. |
| `WHISPER_CPU_THREADS` | `0` | `0` lets CTranslate2 choose; set a number on shared hosts. |
| `RENDER_CRF` | `20` | Higher is smaller and faster; `23` is a good low-power default. |
| `RENDER_X264_PRESET` | `veryfast` | `ultrafast` or `superfast` for slower hardware. |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR`. |

Compose caps each container with `POSTGRES_CPUS`/`POSTGRES_MEMORY`, `REDIS_CPUS`/`REDIS_MEMORY`, `API_CPUS`/`API_MEMORY`, `WORKER_CPUS`/`WORKER_MEMORY` and `WEB_CPUS`/`WEB_MEMORY`. Defaults are listed in `.env.example`; they do not affect a non-Docker run. OAuth, S3, AI and watermark options are documented inline in [`.env.example`](../.env.example).

### Email, sharing and billing

- **Email is optional.** With no SMTP host, verification, reset and invitation links are written to the backend log in debug mode. The API reports `sent: false` and never pretends a message was delivered. Set `SMTP_HOST` and `MAIL_FROM` to send real mail.
- **Verification is opt-in.** `REQUIRE_EMAIL_VERIFICATION=true` rejects password login until the address is confirmed. Accounts created while it is off remain usable; they can confirm later from **My settings**.
- **Share links are self-contained.** A link can carry a bcrypt-hashed password and an expiry. Public media is served through short-lived signed URLs; private workspace media is never exposed without a valid link token.
- **Payments are optional.** Checkout appears only when `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` and the matching price ID are set; checkout stays disabled without a webhook secret so a payment can always be fulfilled. Point a Stripe webhook at `{BACKEND_PUBLIC_URL}/api/billing/webhook`. Without Stripe, plan limits and usage metering still work.
- **Webhooks are signed.** Each endpoint gets its own secret. Verify `X-FireClip-Signature` as HMAC-SHA256 over the raw body. Private and loopback URLs are rejected.

## Ports by deployment type

| Setup | Change it with | Notes |
| --- | --- | --- |
| Local dev runner | `API_PORT`, `WEB_PORT` in `.env` | API and Next both read the values. |
| Docker Compose | `API_PORT`, `WEB_PORT`; optionally `API_CONTAINER_PORT`, `WEB_CONTAINER_PORT` | The first pair changes host-published ports only. The second pair changes the internal listener ports; rebuild after changing the API container port and update the domain/proxy to the new web container port. |
| Root Dockerfile / Render | `PORT` | Next.js public port. FastAPI stays internal on 8000. |
| Reverse proxy | Your proxy config | Point the web domain at the web container's port, not directly at the API. |

With the defaults, `http://localhost:3000` is the app and `http://localhost:8000` the API. If you move to `WEB_PORT=3009`, `API_PORT=8008`, the app is on `http://localhost:3009` and the API on `http://localhost:8008`; the containers can still stay on 3000/8000 internally. Set `FRONTEND_URL=http://localhost:3009`, `BACKEND_PUBLIC_URL=http://localhost:3009` (OAuth callbacks go through the web proxy) and `CORS_ORIGINS=http://localhost:3009`. In production, use your HTTPS web origin for both URL values. If you also change `WEB_CONTAINER_PORT`, the domain must use that new port; if you change `API_CONTAINER_PORT`, rebuild the web image.

## Performance tuning

These settings are read at startup:

| Goal | Settings |
| --- | --- |
| Lowest RAM and fastest start | `WHISPER_MODEL=tiny`, `WHISPER_BEAM_SIZE=1`, `WORKER_CONCURRENCY=1` |
| Fast renders on weak CPUs | `RENDER_X264_PRESET=superfast`, `RENDER_CRF=23` |
| Better transcript quality | `WHISPER_MODEL=base` or `small`, `WHISPER_BEAM_SIZE=5` |
| More throughput | Raise `WORKER_CONCURRENCY` only after checking CPU and RAM; keep `RENDER_CONCURRENCY=1` unless the host is dedicated |
| No local ASR at all | Use OpenAI Whisper (`TRANSCRIPTION_ENGINE=openai`) and keep the worker small |

Built-in safeguards:

- One faster-whisper inference per process; model weights are cached after first load.
- A separate render semaphore, so a queue of render jobs does not start multiple FFmpeg encodes at once.
- Job retries only for transient timeout/connection/429/503 errors; real failures keep their exact error text.
- Request IDs in API access logs, stack traces for unhandled errors, and job failure logs with task names.
