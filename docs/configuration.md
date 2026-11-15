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
| `API_PORT` | `8000` | API port for the local runner and, in Compose, both the container and the host binding. |
| `WEB_PORT` | `3000` | Web port for the local runner and, in Compose, both the container and the host binding. |
| `PORT` | `10000` | Public web port for the all-in-one Dockerfile and cloud hosts. |
| `WORKER_CONCURRENCY` | `2` | Jobs processed concurrently by a worker or inline pool. |
| `RENDER_CONCURRENCY` | `1` | Concurrent FFmpeg encodes per process. |
| `WHISPER_BEAM_SIZE` | `5` | Lower is faster; `1` is the low-power option. |
| `WHISPER_CPU_THREADS` | `0` | `0` lets CTranslate2 choose; set a number on shared hosts. |
| `RENDER_CRF` | `20` | Higher is smaller and faster; `23` is a good low-power default. |
| `RENDER_X264_PRESET` | `veryfast` | `ultrafast` or `superfast` for slower hardware. |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR`. |

OAuth, S3, AI and watermark options are documented inline in `.env.example`.

## Ports by deployment type

| Setup | Change it with | Notes |
| --- | --- | --- |
| Local dev runner | `API_PORT`, `WEB_PORT` in `.env` | API and Next both read the values. |
| Docker Compose | `API_PORT`, `WEB_PORT` in `.env` | Containers bind to the same numbers as the host mapping, so a proxy targets that port. Rebuild the web image after changing `API_PORT` (the API origin is compiled into Next rewrites). |
| Root Dockerfile / Render | `PORT` | Next.js public port. FastAPI stays internal on 8000. |
| Reverse proxy | Your proxy config | Point the web domain at the web container's port, not directly at the API. |

With the defaults, `http://localhost:3000` is the app and `http://localhost:8000` the API. If you move to `WEB_PORT=3009`, `API_PORT=8008`, the app is on `http://localhost:3009`, and you must set `FRONTEND_URL=http://localhost:3009`, `BACKEND_PUBLIC_URL=http://localhost:8008` and `CORS_ORIGINS=http://localhost:3009` so cookies, CORS and OAuth callbacks follow.

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
