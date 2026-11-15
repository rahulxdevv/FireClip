# Guides

[← Back to README](../README.md)

## Enable real speech recognition

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

Without a model key the heuristic analyzer still produces explainable clips. If local ASR is unavailable, transcription fails with a clear message instead of inventing a transcript. For UI demos only, `ALLOW_MOCK_TRANSCRIPTION=true` produces clearly labelled mock transcripts.

## Choose an AI provider

The default `heuristic` engine needs no network and produces deterministic, explainable candidates. To use an LLM:

```dotenv
AI_PROVIDER=openai          # or anthropic | gemini | ollama
OPENAI_API_KEY=sk-...
```

You can also store a workspace key in **AI & transcription**; it is encrypted with AES-GCM derived from `JWT_SECRET` and never returned to the browser. Ollama is only used when explicitly selected - never as an automatic fallback. The **Test** button makes a real request and shows latency or the provider's error.

## Connect YouTube, Facebook, Instagram or TikTok

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

## Use S3-compatible storage

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

## Live stream recording

Add a public YouTube, Twitch or Kick live URL under **Live streams**, then **Start recording**. FireClip records with yt-dlp and routes the result into the normal ingest → transcribe → clip pipeline. Stop cancels the active job. DRM/private streams are not bypassed.

## Rendering presets and captions

| Preset | Output |
| --- | --- |
| TikTok / Reels / Shorts | 1080×1920 |
| Square | 1080×1080 |
| Landscape | 1920×1080 |
| Portrait | 1080×1350 |
| Custom | width/height you choose |

Captions burn in through libass with word-level karaoke when timed words exist. The editor preview approximates crop and captions; the FFmpeg output is the source of truth. Smart crop uses a static face anchor from OpenCV Haar detection, with manual keyframes available.
