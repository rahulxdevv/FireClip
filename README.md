<p align="center">
  <img src="./frontend/public/icon.svg" width="76" height="76" alt="FireClip logo" />
</p>

<h1 align="center">FireClip</h1>

<p align="center">
  <strong>Turn long videos into ready-to-post clips, on your own infrastructure.</strong><br />
  Self-hosted AI clipping, editing, rendering and publishing.
</p>

<p align="center">
  <a href="https://github.com/rahulxdevv/FireClip/stargazers"><img src="https://img.shields.io/github/stars/rahulxdevv/FireClip?style=flat-square&logo=github&label=stars" alt="GitHub stars" /></a>
  <a href="https://github.com/rahulxdevv/FireClip/network/members"><img src="https://img.shields.io/github/forks/rahulxdevv/FireClip?style=flat-square&logo=github&label=forks" alt="GitHub forks" /></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0-blue?style=flat-square" alt="License AGPL-3.0" /></a>
  <a href="https://github.com/rahulxdevv/FireClip/actions/workflows/ci.yml"><img src="https://github.com/rahulxdevv/FireClip/actions/workflows/ci.yml/badge.svg" alt="CI status" /></a>
  <img src="https://img.shields.io/badge/Docker-ready-2496ED?style=flat-square&logo=docker" alt="Docker ready" />
</p>

Give FireClip a podcast, interview, webinar or stream. It transcribes it, scores the moments worth clipping with a reason you can audit, gives you a timeline to edit, renders vertical clips with FFmpeg, and publishes to YouTube, Facebook, Instagram or TikTok through your own OAuth apps.

> **Honesty by design.** If a model, API key or platform permission is missing, FireClip says so and records the real error. It never fabricates clips, analytics, uploads or connections.

## Quick start

Docker Compose starts PostgreSQL, Redis, the API, a worker and the web app:

```bash
git clone https://github.com/rahulxdevv/FireClip.git
cd FireClip
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"   # paste into JWT_SECRET
docker compose up --build -d
```

Open **http://localhost:3000** and register - the first account becomes owner of a workspace.

| Service | URL |
| --- | --- |
| Web app | http://localhost:3000 |
| API | http://localhost:8000 |
| OpenAPI docs | http://localhost:8000/docs |

Without Docker (Python 3.10-3.12, Node 20+, FFmpeg and ffprobe on `PATH`):

```bash
cd backend && python -m venv .venv && ./.venv/Scripts/pip install -r requirements.txt
cd ../frontend && npm install
cd .. && cp .env.example .env
node scripts/dev.mjs        # starts API and web together, ports read from .env
```

Want it in the cloud instead? The [Render blueprint](https://render.com/deploy?repo=https://github.com/rahulxdevv/FireClip) builds the included all-in-one image.

### Your first clip

1. Upload an MP4/MOV, or import a public video URL.
2. Wait for ingest, transcription and analysis - each stage and any real error is shown.
3. Open **Clip discovery**, approve a candidate, then **Open in editor**.
4. Adjust crop and captions, choose a preset, hit **Render**, download from **Exports**.

## Features

| Area | What you get |
| --- | --- |
| Ingest | Streamed uploads with validation, URL import via yt-dlp, SSRF protection |
| Transcription | faster-whisper or OpenAI Whisper, word timestamps, editable segments |
| Clip discovery | Explainable offline scoring, or OpenAI, Anthropic, Gemini, Ollama |
| Editor | Timeline, trim, crop keyframes, face-anchored auto-crop, caption styles, overlays, music, fades, undo/redo |
| Rendering | 9:16, 1:1, 16:9 and 4:5 presets, MP4/MOV/WebM, burned ASS captions, loudness normalization |
| Publishing | YouTube, Facebook, Instagram Reels and TikTok, with scheduling and retries |
| Analytics | Platform metric sync, plus manual numbers labelled by source |
| Live | Record public YouTube, Twitch or Kick streams into the same pipeline |
| Teams | Workspaces with owner/admin/editor/viewer roles, invitations, audit log |

Transcription, LLM providers and publishing need your own credentials. Payments, email notifications and stock footage are not included - the full status table is in [Architecture](docs/architecture.md#feature-status).

## How it works

```text
Browser ──same-origin /api──► Next.js 16 ──► FastAPI ─┬─► PostgreSQL / SQLite
                                                      ├─► local storage or S3
                                                      ├─► FFmpeg, ffprobe, yt-dlp
                                                      ├─► ASR and optional LLM
                                                      └─► Redis + ARQ worker
```

Ingest → transcribe → analyze → cut → edit → render → publish → measure. Each stage is a real background job, and failures keep their exact error text. More in [Architecture](docs/architecture.md).

## Configuration

Everything is environment-driven, and [`.env.example`](.env.example) documents each option. The ones that matter first:

| Variable | Default | Why it matters |
| --- | --- | --- |
| `JWT_SECRET` | dev value | **Required in production.** Signs sessions and derives the AES key for stored provider tokens. |
| `DATABASE_URL` | SQLite | Point it at PostgreSQL for anything beyond a demo. |
| `REDIS_URL` | empty | Enables the ARQ worker; without it jobs run inline. |
| `FRONTEND_URL`, `BACKEND_PUBLIC_URL` | localhost | Public origins used for OAuth callbacks and CORS. |
| `COOKIE_SECURE` | `false` | Set `true` behind TLS. |

Full variable list, ports by deployment type and performance tuning: [Configuration](docs/configuration.md).

## Deploy

| Target | How |
| --- | --- |
| VPS with Docker | `docker compose up --build -d`, then proxy 3000/8000 and terminate TLS |
| Render | [One-click blueprint](https://render.com/deploy?repo=https://github.com/rahulxdevv/FireClip) - the free plan sleeps, has 512 MB and ephemeral media |
| Dokploy | Compose application with `JWT_SECRET` set; PostgreSQL and Redis come with the stack |

Proxy examples, backups, scaling and an operations checklist: [Deployment](docs/deployment.md).

## Docs

- [Configuration](docs/configuration.md) - requirements, every variable, ports, tuning
- [Deployment](docs/deployment.md) - Render, VPS, Dokploy, production self-hosting
- [Guides](docs/guides.md) - speech recognition, AI providers, OAuth publishing, S3, live recording
- [Troubleshooting](docs/troubleshooting.md) - symptoms, fixes, known limitations
- [Architecture](docs/architecture.md) - pipeline, feature status, project structure
- [Roadmap](docs/roadmap.md) - what's next, what isn't planned
- [Third-party licenses](docs/licensing.md) - dependency licenses

## Security

- bcrypt password hashing, HTTP-only JWT cookies, API keys stored as hashes with a visible prefix.
- Provider and OAuth tokens encrypted with AES-GCM derived from `JWT_SECRET`.
- Workspace-scoped media, SSRF-guarded URL imports, audit logs and rate limits.
- Back up `JWT_SECRET`: losing it invalidates sessions and makes encrypted tokens unrecoverable.

## Status

The backend suite (36 tests), the TypeScript check and the production build pass, and a fresh Alembic migration applies cleanly. Docker images, the Render blueprint and live OAuth/AI calls were not exercised here because they need a Docker host or real credentials. Known gaps: [Troubleshooting](docs/troubleshooting.md#known-limitations).

## License

[AGPL-3.0](LICENSE). Self-host it, modify it and use it commercially; if you run a modified FireClip as a network service, offer your users the source. Commercial licensing: [rahulxdevv@proton.me](mailto:rahulxdevv@proton.me).

---

<p align="center">
  Built by <a href="https://github.com/rahulxdevv">Rahul (@rahulxdevv)</a>.<br />
  If FireClip saves you an editing session, a star helps other people find it.
</p>
