# Architecture

[← Back to README](../README.md)

## How it works

```text
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

## Feature status

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
docs/              this documentation
```

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

## Security model

- bcrypt password hashing; signed JWT HTTP-only cookies; refresh cookie.
- API keys stored as SHA-256 hashes with a visible prefix only.
- Provider and OAuth tokens encrypted with AES-GCM derived from `JWT_SECRET`.
- Workspace-scoped media access; downloads stream through authenticated endpoints with Range support.
- URL imports reject private/link-local targets and redirects (SSRF protection).
- Rate limits and audit logs for security-relevant actions.
- Production CORS/Origin checks for state-changing requests.
- Back up `JWT_SECRET`: losing it invalidates sessions and makes encrypted tokens unrecoverable.
