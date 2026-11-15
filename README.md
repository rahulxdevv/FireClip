<p align="center">
  <img src="./frontend/public/icon.svg" width="76" height="76" alt="FireClip logo" />
</p>

<h1 align="center">FireClip</h1>

<p align="center">
  <strong>Turn long videos into ready-to-post clips - on your own infrastructure.</strong><br />
  Self-hosted AI clipping, editing, rendering and publishing. Bring any AI provider, or use the built-in offline analyzer.
</p>

<p align="center">
  <a href="https://github.com/rahulxdevv/FireClip/stargazers"><img src="https://img.shields.io/github/stars/rahulxdevv/FireClip?style=flat-square&logo=github&label=stars" alt="GitHub stars" /></a>
  <a href="https://github.com/rahulxdevv/FireClip/network/members"><img src="https://img.shields.io/github/forks/rahulxdevv/FireClip?style=flat-square&logo=github&label=forks" alt="GitHub forks" /></a>
  <img src="https://img.shields.io/badge/tests-36%20passed-2ea043?style=flat-square" alt="36 tests passing" />
  <img src="https://img.shields.io/badge/status-MVP-f59e0b?style=flat-square" alt="MVP status" />
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0-blue?style=flat-square" alt="License AGPL-3.0" /></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Next.js-16-000000?style=flat-square&logo=nextdotjs" alt="Next.js 16" />
  <img src="https://img.shields.io/badge/React-19-149ECA?style=flat-square&logo=react" alt="React 19" />
  <img src="https://img.shields.io/badge/FastAPI-Python%203.12-009688?style=flat-square&logo=fastapi" alt="FastAPI" />
  <img src="https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat-square&logo=postgresql" alt="PostgreSQL" />
  <img src="https://img.shields.io/badge/Docker-ready-2496ED?style=flat-square&logo=docker" alt="Docker ready" />
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="#features">Features</a> ·
  <a href="#one-click-deploy">Deploy</a> ·
  <a href="#how-it-works">How it works</a> ·
  <a href="#configuration-and-ports">Configuration</a> ·
  <a href="#roadmap">Roadmap</a> ·
  <a href="#troubleshooting">Troubleshooting</a>
</p>

---

FireClip takes a podcast, interview, webinar or stream and turns it into short-form vertical clips: it transcribes the source, scores candidate moments with an explanation you can audit, gives you a real editing timeline, renders with FFmpeg, and publishes to YouTube, Facebook, Instagram or TikTok when you connect your own OAuth apps.

It is built for people who want to **own the pipeline** and see exactly why a clip was chosen, not a black box that invents engagement numbers. The project combines the discovery, editing, rendering, publishing, analytics and live-recording workflows of both reference builds in one independent codebase. No third-party application source is vendored.

> **Honesty by design:** if a model, API key or platform permission is missing, FireClip says so and records the real error. It never fabricates clips, analytics, uploads or connections.

## Contents

- [System requirements](#system-requirements)
- [Quick start](#quick-start)
- [One-click deploy](#one-click-deploy)
- [Deploy with Dokploy](#deploy-with-dokploy)
- [Features](#features)
- [How it works](#how-it-works)
- [Guides](#guides)
- [Configuration and ports](#configuration-and-ports)
- [Performance tuning](#performance-tuning)
- [How FireClip compares](#how-fireclip-compares)
- [Project status & tests](#project-status--tests)
- [Roadmap](#roadmap)
- [Troubleshooting](#troubleshooting)
- [Security](#security)
- [Project structure](#project-structure)
- [Self-hosting in production](#self-hosting-in-production)
- [License](#license)
- [Third-party licenses](#third-party-licenses)

## System requirements

FireClip runs on ordinary CPUs. Local Whisper and FFmpeg are the heavy parts, so size the host around those.

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

## Quick start

| I want to… | Use | First run |
| --- | --- | --- |
| Try it in the cloud | [One-click Render](#one-click-deploy) | ~5 min build, no local install |
| Self-host with a worker | [Docker Compose](#option-a-one-command-with-docker-recommended-for-self-hosting) | ~2-4 min build |
| Change the code | [Local development](#option-b-local-development-without-docker) | ~2 min setup |

### Option A: one command with Docker (recommended for self-hosting)

Requires Docker + Compose v2. This starts PostgreSQL, Redis, the API, a background worker and the web app.

```bash
git clone https://github.com/rahulxdevv/FireClip.git
cd fireclip
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"   # paste into JWT_SECRET
docker compose up --build -d
```

Open **http://localhost:3000** and register. The first account becomes owner of a personal workspace.

| Service | URL |
| --- | --- |
| Web app | http://localhost:3000 |
| API | http://localhost:8000 |
| OpenAPI docs | http://localhost:8000/docs |
| Health | http://localhost:8000/health |

### Option B: local development without Docker

Requires Python 3.10-3.12 for local speech recognition, Node 20+, and FFmpeg/ffprobe on `PATH`.

```bash
# one-time setup
cd backend
python -m venv .venv
./.venv/Scripts/pip install -r requirements.txt        # Windows
# .venv/bin/pip install -r requirements.txt            # macOS / Linux
cd ../frontend
npm install
cd ..
cp .env.example .env        # set JWT_SECRET, optionally API_PORT and WEB_PORT

# start API + web together, reading ports from .env
node scripts/dev.mjs
```

Open **http://localhost:3000** (or your `WEB_PORT`). The API listens on `API_PORT`, and the Next proxy is pointed at it automatically.

Prefer separate terminals?

```bash
cd backend && ./.venv/Scripts/python -m app
cd frontend && npm run dev -- -p 3000
```

If you change `API_PORT` while starting Next manually, set `API_BASE_URL=http://127.0.0.1:<API_PORT>` for the frontend. `scripts/dev.mjs` does this for you.

Optional local Whisper (Python 3.12 recommended):

```bash
cd backend
./.venv/Scripts/pip install -r requirements-transcription.txt
# set TRANSCRIPTION_ENGINE=faster_whisper in backend/.env
```

No model key? The heuristic analyzer still produces explainable clips. If local ASR is unavailable, transcription fails with a clear message instead of inventing a transcript. For UI demos only, `ALLOW_MOCK_TRANSCRIPTION=true` produces clearly labelled mock transcripts.

### Option C: one-click cloud demo

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/rahulxdevv/FireClip)

The included `render.yaml` creates one Docker web service and a free PostgreSQL database. It builds an all-in-one image (Next.js + FastAPI, inline jobs) so the whole product runs on one URL with same-origin cookies and uploads.

Read [One-click deploy](#one-click-deploy) before using it - the free plan has real limits.

### Your first clip in five minutes

1. Register - a workspace is created automatically.
2. Go to **Upload video** and pick an MP4/MOV, or **Import from URL** for a public video.
3. Wait for ingest → transcription → analysis. The video page shows each stage and any real error.
4. Open **Clip discovery**, approve a candidate, then **Open in editor**.
5. Adjust crop/captions, choose a preset and click **Render**. Download it from **Exports**.

## One-click deploy

### Render

1. Push this repository to `github.com/rahulxdevv/FireClip` (the button above uses that repo).
2. Click **Deploy to Render** and approve the Blueprint.
3. Wait for the Docker build (FFmpeg + faster-whisper make it a few minutes).
4. Open `https://fireclip-rahulxdevv.onrender.com` and register.

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

### Any VPS with Docker

```bash
git clone https://github.com/rahulxdevv/FireClip.git
cd fireclip
cp .env.example .env
# set JWT_SECRET, FRONTEND_URL, BACKEND_PUBLIC_URL, COOKIE_SECURE=true
docker compose up --build -d
```

Put Caddy, Nginx or Traefik in front of ports `3000` and `8000`, terminate TLS there, and set the OAuth callback base URL to your API domain. Full proxy, backup and scaling notes are in [Self-hosting in production](#self-hosting-in-production).

## Deploy with Dokploy

Dokploy can deploy this repository in either of two ways. The short answer: **yes, a Docker Compose deployment works with only `JWT_SECRET` set**, because PostgreSQL and Redis are created as services inside the Compose stack. No external database or Redis is required for the core product. A single-container deployment of the root `Dockerfile` also works with only `JWT_SECRET`, using SQLite and inline jobs.

### Recommended: Compose application

1. In Dokploy, create a **Compose** application and connect `github.com/rahulxdevv/FireClip`.
2. Use the repository `docker-compose.yml`.
3. Add `JWT_SECRET` (32+ random bytes) in the environment editor.
4. Attach your domain to the **web** service on port `3000`.
5. Deploy. The stack starts PostgreSQL, Redis, the API, the worker and the web app automatically.

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

## Features

**Ready** = works with the default stack. **Keys** = implemented, needs your credentials/permissions. **Later** = explicitly not included.

| Area | What you get | Status |
| --- | --- | --- |
| Auth | Registration, login, HTTP-only JWT cookies, refresh, API keys, rate limits | Ready |
| Teams | Workspaces, owner/admin/editor/viewer roles, invitations by email, audit log | Ready |
| Ingest | Streamed uploads with validation, URL import via yt-dlp, SSRF protection | Ready |
| Media | FFprobe metadata, thumbnails, audio extraction, sprite previews | Ready |
| Transcription | faster-whisper, openai-whisper, hosted OpenAI Whisper, word timestamps, editable segments | Keys / install |
| Speakers | Off, pause-based estimate (labelled), optional pyannote; manual speaker names | Ready / optional |
| Clip discovery | Explainable heuristic scoring + OpenAI, Anthropic, Gemini or Ollama | Ready / Keys |
| Clip review | Approve/reject, manual cuts, merge, content generation (titles, hooks, captions, hashtags) | Ready |
| Editor | Timeline, trim, crop keyframes, face-based auto-focus, caption styles, overlays, music, fades, undo/redo | Ready |
| Rendering | 9:16, 1:1, 16:9, 4:5 presets; MP4/MOV/WebM; burned ASS captions; loudness normalization | Ready |
| Queue | Progress, cancel, retry, render-minute limits, ARQ worker or inline runner | Ready |
| Exports | Download library, thumbnails, HTTP Range streaming | Ready |
| Publishing | YouTube, Facebook, Instagram Reels and TikTok uploads, scheduling, retries | Keys |
| Analytics | Platform metrics sync plus clearly labelled manual measurement | Ready / Keys |
| Live | Record public YouTube/Twitch/Kick live streams via yt-dlp | Ready / environment |
| Dashboard | Usage, processing jobs, recent activity, notifications | Ready |
| Billing | Plan limits and usage metering | Ready (no checkout) |
| Payments | Stripe/checkout, invoices | Later |
| Email | Verification, password reset, notification emails | Later |

## How it works

```
Browser
  │  same-origin /api/* (Next rewrite)
  ▼
Next.js 16 ─────────────────────────────► FastAPI
  App Router, Tailwind 4, Zustand            │
                                             ├─► SQLAlchemy ─► PostgreSQL / SQLite
                                             ├─► local storage / S3
                                             ├─► FFmpeg / ffprobe / yt-dlp
                                             ├─► ASR engines (local or hosted)
                                             ├─► LLM providers (optional)
                                             └─► Redis + ARQ ─► worker
```

The pipeline is a sequence of real jobs, not synchronous request handlers:

1. **Ingest** - validate, probe, extract audio, create thumbnails.
2. **Transcribe** - segment/word timestamps; optional speaker labels.
3. **Analyze** - score transcript and audio signals; store a per-signal breakdown and a readable reason.
4. **Cut** - candidate clips with scores, hooks and transcript excerpts.
5. **Edit** - a declarative project: trim, crop keyframes, captions, overlays, music, fades.
6. **Render** - FFmpeg graph, output probed before it is marked complete.
7. **Publish** - official platform APIs; failures stored verbatim.
8. **Measure** - platform metrics or manual numbers, each labelled by source.

The same task callables run through ARQ in Docker and inline locally, so the UI behaves identically.

## Guides

<details>
<summary><strong>Enable real speech recognition</strong></summary>

**Docker (recommended):** the image installs faster-whisper. Set:

```dotenv
TRANSCRIPTION_ENGINE=faster_whisper
WHISPER_MODEL=base
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

**Hosted Whisper:** set `TRANSCRIPTION_ENGINE=openai` and `OPENAI_API_KEY`. Requests are limited to 25 MB.

**Local Python:** use Python 3.10-3.12 and install `requirements-transcription.txt`. PyAV has no wheels for 3.13+ yet.

Engine availability is shown in **AI & transcription** and at `/api/system/status`.
</details>

<details>
<summary><strong>Choose an AI provider</strong></summary>

The default `heuristic` engine needs no network and produces deterministic, explainable candidates. To use an LLM:

```dotenv
AI_PROVIDER=openai          # or anthropic | gemini | ollama
OPENAI_API_KEY=sk-...
```

You can also store a workspace key in **AI & transcription**; it is encrypted with AES-GCM derived from `JWT_SECRET` and never returned to the browser. Ollama is only used when explicitly selected - never as an automatic fallback. The **Test** button makes a real request and shows latency or the provider's error.
</details>

<details>
<summary><strong>Connect YouTube, Facebook, Instagram or TikTok</strong></summary>

Create OAuth apps with the platforms and set the credentials in `.env`:

```dotenv
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
FACEBOOK_CLIENT_ID=
FACEBOOK_CLIENT_SECRET=
INSTAGRAM_CLIENT_ID=
INSTAGRAM_CLIENT_SECRET=
TIKTOK_CLIENT_KEY=
TIKTOK_CLIENT_SECRET=
```

Register this callback for each platform:

```text
{BACKEND_PUBLIC_URL}/api/publishing/callback/{youtube|facebook|instagram|tiktok}
```

Then connect from **Social accounts**. Notes:

- **Instagram Reels** require an Instagram Business account linked to a Facebook page and a publicly reachable video URL. Configure S3 and `MEDIA_PUBLIC_BASE_URL`.
- **TikTok** direct posting requires an approved developer app with the content-posting scope. This implementation supports single-chunk uploads up to 64 MB.
- **YouTube/Facebook** upload the rendered file directly.
- Expired tokens are refreshed automatically when a refresh token exists; otherwise reconnect.
</details>

<details>
<summary><strong>Use S3-compatible storage</strong></summary>

```dotenv
STORAGE_BACKEND=s3
S3_BUCKET=fireclip-media
S3_ENDPOINT_URL=              # optional for R2/MinIO
S3_REGION=us-east-1
S3_ACCESS_KEY_ID=
S3_SECRET_ACCESS_KEY=
S3_PREFIX=fireclip
MEDIA_PUBLIC_BASE_URL=https://cdn.example.com
```

`MEDIA_PUBLIC_BASE_URL` is only needed for platforms (Instagram) that fetch media themselves. Local storage is authenticated and not public by design.
</details>

<details>
<summary><strong>Live stream recording</strong></summary>

Add a public YouTube, Twitch or Kick live URL under **Live streams**, then **Start recording**. FireClip records with yt-dlp and routes the result into the normal ingest → transcribe → clip pipeline. Stop cancels the active job. DRM/private streams are not bypassed.
</details>

<details>
<summary><strong>Rendering presets and captions</strong></summary>

| Preset | Output |
| --- | --- |
| TikTok / Reels / Shorts | 1080×1920 |
| Square | 1080×1080 |
| Landscape | 1920×1080 |
| Portrait | 1080×1350 |
| Custom | width/height you choose |

Captions burn in through libass with word-level karaoke when timed words exist. The editor preview approximates crop and captions; the FFmpeg output is the source of truth. Smart crop uses a static face anchor from OpenCV Haar detection, with manual keyframes available.
</details>

## Configuration and ports

Copy [`.env.example`](.env.example) to `.env`. The essentials:

| Variable | Default | Description |
| --- | --- | --- |
| `JWT_SECRET` | generated in dev | **Required in production.** Signs sessions and derives the AES key for stored secrets. 32+ bytes. |
| `DATABASE_URL` | SQLite | `postgresql+psycopg://…`; plain `postgres://` URLs are normalized automatically. |
| `REDIS_URL` | empty | Enables ARQ. Without it, jobs run inline. |
| `JOB_RUNNER` | `auto` | `auto`, `inline` or `arq`. |
| `FRONTEND_URL` | `http://localhost:3000` | Web origin used for OAuth redirects and CORS. |
| `BACKEND_PUBLIC_URL` | `http://localhost:8000` | Public API URL, used to build OAuth callbacks. |
| `COOKIE_SECURE` | `false` | Set `true` behind HTTPS. |
| `TRANSCRIPTION_ENGINE` | `auto` | `faster_whisper`, `whisper`, `openai`, `auto`. |
| `AI_PROVIDER` | `auto` | `heuristic`, `openai`, `anthropic`, `gemini`, `ollama`. |
| `WHISPER_MODEL` | `base` | `tiny` for low-memory hosts, `small`/`medium` for quality. |
| `STORAGE_BACKEND` | `local` | `local` or `s3`. |
| `MAX_UPLOAD_MB` | `4096` | Enforced by the API; match your proxy body limit. |
| `PLAN_CLIP_LIMIT` | `500` | Default monthly clip allowance for new workspaces. |
| `PLAN_RENDER_MINUTES` | `600` | Default monthly render-minute allowance. |
| `ALLOW_MOCK_TRANSCRIPTION` | `false` | Tests/demos only. Mock output is labelled in the UI. |
| `API_HOST` | `127.0.0.1` | Local API bind address. Use `0.0.0.0` only when exposing it directly. |
| `API_PORT` | `8000` | Local API port (`python -m app`) and Docker Compose host port. |
| `WEB_PORT` | `3000` | Local web port and Docker Compose host port. |
| `PORT` | `10000` | Public web port for the all-in-one Dockerfile and cloud hosts. |
| `WORKER_CONCURRENCY` | `2` | Jobs processed concurrently by a worker or inline pool. |
| `RENDER_CONCURRENCY` | `1` | Concurrent FFmpeg encodes per process. |
| `WHISPER_BEAM_SIZE` | `5` | Lower is faster; `1` is the low-power option. |
| `WHISPER_CPU_THREADS` | `0` | `0` lets CTranslate2 choose; set a number on shared hosts. |
| `RENDER_CRF` | `20` | Higher is smaller and faster; `23` is a good low-power default. |
| `RENDER_X264_PRESET` | `veryfast` | `ultrafast` or `superfast` for slower hardware. |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR`. |

### Ports by deployment type

| Setup | Change it with | Notes |
| --- | --- | --- |
| Local dev runner | `API_PORT`, `WEB_PORT` in `.env` | API and Next both read the values. |
| Docker Compose | `API_PORT`, `WEB_PORT` in `.env` | Only host ports change; containers stay on 8000/3000. |
| Root Dockerfile / Render | `PORT` | Next.js public port. FastAPI stays internal on 8000. |
| Reverse proxy | Your proxy config | Point the web domain at the web container, not directly at the API. |

OAuth, S3, AI and watermark options are documented inline in `.env.example`.

## Performance tuning

FireClip does not pretend that one default fits every machine. These settings are read at startup:

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

## How FireClip compares

This is a category-level comparison, not a claim about a specific vendor; check current terms before choosing.

| | **FireClip** | Typical hosted clipper | Manual editing |
| --- | --- | --- | --- |
| Where media is processed | Your machine or server | Vendor cloud | Your machine |
| AI choice | 4 hosted providers + offline heuristic | Vendor-selected | None |
| Source code | Self-hosted, inspectable | Closed | N/A |
| Data ownership | Your database and storage | Vendor account | Local files |
| Analytics | Measured only, manual entries labelled | Usually measured | N/A |
| Pricing model | Infrastructure + your API usage | Subscription | Your time |
| Setup | One command or one-click demo | Sign up | Install an NLE |
| Best for | Teams that need control and auditability | Fastest zero-ops start | Maximum creative control |

FireClip does **not** try to win on a stock footage library or one-click virality. It wins on transparency, provider freedom and self-hosting.

## Project status & tests

Verified in the development environment on **2026-11-15**:

| Check | Result |
| --- | --- |
| Backend test suite | **36 passed** |
| TypeScript + production build | **Passed**, 22 routes |
| Fresh Alembic migration | Applied; `alembic check` clean |
| API contract sweep | All page-used endpoints returned expected shapes |
| Production Next proxy | Registration and cookie auth work; multipart upload returns 201 |
| End-to-end pipeline | Upload → mock ASR → analysis → 1080×1920 render with audio and captions |

```bash
# backend tests
cd backend && ./.venv/Scripts/python -m pytest

# frontend type-check + build
cd frontend && npm run build
```

**Not verified here:** Docker images and the Render Blueprint could not be launched (Docker is unavailable in this environment); live OAuth, live AI providers, and live platform analytics need real credentials. No browser screenshot/E2E pass is included.

### Known limitations

- No stock B-roll or music library - no fake licensing.
- Smart crop is a static face anchor, not per-frame speaker tracking.
- Diarization is approximate unless pyannote is installed; it is labelled.
- TikTok posting is gated by app approval; metrics need additional scopes.
- Instagram Reels need a public HTTPS media URL.
- No payments, email verification, password reset or notification emails.
- Local speech recognition needs Python 3.10-3.12; Python 3.13+ cannot install PyAV.
- Render free plan sleeps, has 512 MB RAM and ephemeral media.

## Roadmap

Planned work, not promises. Order may change.

| Horizon | Item |
| --- | --- |
| Next | Browser E2E tests for auth, upload, editor and render |
| Next | Multi-select merge directly in the clip library |
| Next | Live OAuth verification against each platform's sandbox |
| Later | Stripe checkout and plan-to-workspace mapping |
| Later | Frame-by-frame speaker tracking and active-speaker crop |
| Later | Licensed B-roll/music integrations |
| Later | Email verification, password reset, notification emails |
| Exploring | Team comments and approval workflows |
| Exploring | Localization of transcripts and burned captions |

Have a different priority? Open an issue with the workflow you need.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Jobs stay queued | Start the worker (`docker compose ps`, logs) or use `JOB_RUNNER=inline`. |
| `alembic: relation already exists` | Don't enable `AUTO_MIGRATE` together with the migration entrypoint. |
| Login redirects immediately | Cookie blocked: check `FRONTEND_URL`, `COOKIE_SECURE` and TLS. |
| Upload fails around 1 MB | Raise the reverse proxy body limit and disable request buffering. |
| Captions missing | FFmpeg must include libass, and the clip needs timed segments. |
| Local ASR won't install | Use Docker or a Python 3.12 venv. |
| OAuth callback error | Callback URL mismatch or expired state (15 minutes). |
| Instagram publish fails | Public media URL missing or account is not a linked Business account. |
| Render build fails on memory | Upgrade the instance or use hosted Whisper. |

## Security

- bcrypt password hashing; signed JWT HTTP-only cookies; refresh cookie.
- API keys stored as SHA-256 hashes with a visible prefix only.
- Provider and OAuth tokens encrypted with AES-GCM derived from `JWT_SECRET`.
- Workspace-scoped media access; downloads stream through authenticated endpoints with Range support.
- URL imports reject private/link-local targets and redirects (SSRF protection).
- Rate limits and audit logs for security-relevant actions.
- Production CORS/Origin checks for state-changing requests.
- Back up `JWT_SECRET`: losing it invalidates sessions and makes encrypted tokens unrecoverable.

## Project structure

```text
backend/
  app/
    routers/       auth, workspaces, projects, videos, assets, clips, editors,
                   renders/exports/jobs, publishing, analytics, ai, dashboard, live
    services/      media, transcription, highlights, content, captions, face,
                   render, publishing, analytics, ai, sources
    models.py      26 tables
    tasks.py       ingest, transcribe, analyze, render, publish, live recording
    jobs.py        inline + ARQ queue and recovery
    worker.py      ARQ worker + scheduled publishing cron
  alembic/         initial migration
  tests/           pytest suite (36 tests)
frontend/
  app/(app)/       dashboard, videos, upload, import, live, clips, editor,
                   renders, exports, publish, accounts, analytics, ai-settings,
                   workspace, billing, settings, docs
  components/      UI kit, app shell, charts, timeline, clip cards
  lib/             API client, hooks, types, store, formatting
Dockerfile         all-in-one image used by the Render blueprint
docker-compose.yml multi-service self-host stack
render.yaml        one-click Render Blueprint
deploy/            supervisord + entrypoint for the all-in-one image
scripts/dev.mjs    cross-platform local runner using API_PORT/WEB_PORT
```

## Self-hosting in production

<details>
<summary><strong>Reverse proxy, TLS and uploads</strong></summary>

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

Nginx: set `client_max_body_size 4g;` and `proxy_request_buffering off;` for large uploads. Uvicorn already runs with `--proxy-headers`. Set `COOKIE_SECURE=true`, real public URLs and matching CORS origins when TLS is enabled.

OAuth callbacks must match exactly:

```text
https://api.example.com/api/publishing/callback/{platform}
```
</details>

<details>
<summary><strong>Storage, scaling and backups</strong></summary>

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
</details>

<details>
<summary><strong>Upgrades and operations checklist</strong></summary>

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
</details>

## License

FireClip is released under the **GNU Affero General Public License v3.0**. The full text is in [LICENSE](./LICENSE).

Copyright (C) 2026 Rahul (rahulxdevv)

In short:

- **Self-host it, modify it, use it commercially** inside your own business, at no cost and with no obligation to publish anything.
- **If you run a modified FireClip as a network service for others, offer them your changes.** Section 13 treats network use as distribution, so the source of your modified version must be available to the people using it.
- **No warranty.** The software is provided as is, without warranty of any kind.

If AGPL-3.0 does not fit your organisation - for example because your policy bans copyleft licenses - a separate commercial license can be arranged: [rahulxdevv@proton.me](mailto:rahulxdevv@proton.me).

## Third-party licenses

FireClip's own code is AGPL-3.0 (see [License](#license)); the components it depends on keep their own licenses:

| Component | License |
| --- | --- |
| Next.js, React, Tailwind CSS, Framer Motion, Zustand | MIT |
| lucide-react | ISC |
| clsx, tailwind-merge | MIT |
| class-variance-authority | Apache-2.0 |
| FastAPI, SQLAlchemy, Alembic, ARQ, Pydantic, Uvicorn (BSD-3), PyJWT | MIT / BSD-3 |
| bcrypt, python-multipart | Apache-2.0 |
| HTTPX | BSD-3-Clause |
| cryptography | Apache-2.0 / BSD-3-Clause |
| yt-dlp | Unlicense |
| boto3 | Apache-2.0 |
| OpenCV | Apache-2.0 |
| psycopg | LGPL-3.0 |
| faster-whisper / CTranslate2 | MIT |
| PyAV | BSD-3-Clause |
| FFmpeg | Executed as a separate binary; your build's LGPL/GPL terms apply |
| PostgreSQL | PostgreSQL License |
| Redis | RSALv2 / SSPLv1 (Redis 7) - review before offering it as a service |

Transitive dependencies carry their own licenses. Generate a full report with `pip-licenses` and `license-checker` before redistribution.

---

<p align="center">
  Built and maintained by <a href="https://github.com/rahulxdevv">Rahul (@rahulxdevv)</a>.<br />
  If FireClip saves you an editing session, a star helps other people find it.
</p>
