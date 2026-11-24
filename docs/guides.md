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

## Campaigns

A campaign is a production brief, not a folder. Give it an audience and editorial direction (what to prefer, what to avoid), a target clip length, a clip count, a minimum score, an aspect ratio, a caption style and optional brand fields. Attach existing videos or import new ones with the campaign preselected.

**Run analysis** uses the campaign brief for every attached video, applies the target length and score floor, and can automatically approve and render strong clips. The accent color drives the caption highlight, and the optional brand mark is drawn as a text watermark or an uploaded top-corner logo on automatic renders; headline, hashtags and CTA become timed text overlays. Automatic rendering only runs when the campaign is **active**, both **auto-approve** and **auto-render** are on, and the workspace has render minutes left. Each automatic render is a real editor project and render job, not a preview.

## Campaign discovery and Content Rewards

The **Campaigns** page can show live campaigns from a JSON feed. FireClip does not scrape a marketing site or invent a campaign API: set a feed URL that your Content Rewards provider (or your own middleware) exposes, then restart the API.

```dotenv
CAMPAIGN_FEED_URL=https://rewards.example.com/api/campaigns
CAMPAIGN_FEED_TOKEN=
CAMPAIGN_FEED_LABEL=Content Rewards
```

The feed can be a JSON list or an object with `campaigns`, `data` or `items`. Each campaign needs an `id` (or `campaign_id`/`slug`) and a `name`/`title`. Optional fields include `description`, `guidelines`, `brief`, `url`, `hashtags`, `ends_at`, `clip_count`, `min_score`, `target_duration_ms` and a `brand` object (`accent_color`, `headline`, `cta`, `logo_text`, `hashtags`, and so on).

**Add to My Campaigns** copies one feed campaign into the workspace as a normal campaign, preserving its brief, hashtags, brand colors and source link. It is a one-click import, not a hidden sync: later feed changes do not overwrite the workspace copy. Without `CAMPAIGN_FEED_URL` the page says the feed is not configured and offers manual campaign creation.

Whop Content Rewards does not publish a general "list every active campaign" endpoint in its public API. To use Whop, place its creator campaign data behind your own signed JSON feed and point `CAMPAIGN_FEED_URL` at that feed, or create the campaign manually. Never enter a Whop session cookie or scrape the dashboard.

## Automated publishing

A campaign can publish completed renders without another click. Open the campaign and enable **Auto-publish** after **Auto-approve** and **Auto-render**; choose connected accounts, a minimum virality score, a privacy setting and either **Post now** or **Next preferred slot**. The preferred hour is UTC.

Every publish is still a real `PublishingJob` through the same platform OAuth code used by manual publishing. FireClip skips the job when the campaign is paused, the score is below the floor, no selected account is connected, or auto-render is off. Scheduled jobs are released by the scheduler/worker when their time arrives. Nothing is marked published until the platform accepts it, and failures keep the platform error.

The **Schedule** page is the single timeline for queued, scheduled, published and failed posts. It links to the live post when the platform returns a URL and supports cancel and retry.

## Streamers

**Streamers** is a roster view over live sources. Add a public channel or live URL, optionally bind it to a campaign, and turn on auto-record and auto-clip. Start and stop capture from the same page. Only public streams are supported; private, DRM-protected and paywalled streams are rejected rather than bypassed. Capture is real yt-dlp recording followed by the normal ingest → transcribe → analyze pipeline; it is not incremental clipping while the stream is live.

## Live stream recording

Add a public YouTube, Twitch or Kick live URL under **Live streams** or **Streamers**, then **Start recording**. FireClip records with yt-dlp and routes the result into the normal ingest → transcribe → clip pipeline. Stop cancels the active job. DRM/private streams are not bypassed.

To automate capture, enable **auto-record** on a stream and optionally choose a campaign. A background check runs about once a minute, asks the platform whether the URL is live, and only then starts a capture; offline or scheduled pages are skipped. When the capture ends, **auto-clip** sends it through transcription and campaign analysis, and the entry returns to monitoring for the next session. Stopping a capture yourself leaves it finished rather than immediately restarting. This is recording and post-capture clipping, not incremental clipping while the stream is still running.

## Rendering presets and captions

| Preset | Output |
| --- | --- |
| TikTok / Reels / Shorts | 1080×1920 |
| Square | 1080×1080 |
| Landscape | 1920×1080 |
| Portrait | 1080×1350 |
| Custom | width/height you choose |

Captions burn in through libass with word-level karaoke when timed words exist. The editor preview approximates crop and captions; the FFmpeg output is the source of truth. Smart crop uses a static face anchor from OpenCV Haar detection, with manual keyframes available.

## Framing layouts

Every editor project has a **Layout** setting:

- **Fill** - crop the source to fill the output frame. This is the default and uses the face/focus crop.
- **Fit** - keep the whole source visible, with a blurred, cropped copy filling the background.
- **Face cam** - crop the speaker camera and overlay it on the main frame. Choose bottom right, bottom left, top right, top left, bottom center, **bottom half**, or manual X/Y. The overlay size is adjustable, and the source camera crop has its own X/Y/width/height controls. **Detect subject** fills those camera values from the largest detected face.

Layouts are stored per project, so changing one clip does not move every other clip.

## Caption headings, presets and translation

The **Captions** tab includes a separate heading line above the captions: text, color, size, uppercase, and a hide toggle. Hiding it removes the heading from the rendered ASS file instead of leaving a blank style behind. Caption presets are reusable styles with font, size, colors, outline, shadow, box, alignment, margins, animation, letter spacing and scaling. The preset grid previews each style and switches the current project to it; **Save current style** creates a workspace preset.

**Translate captions** rewrites the active transcript range into another language with the configured LLM provider. Pick one of the supported languages and press Translate. The translated segments are shown in the preview and used by the renderer; **Clear translation** returns to the source transcript. Translation requires an AI provider. Without one, the API returns a clear error rather than copying the source or pretending to translate. The same limitation applies to AI metadata generation: with the heuristic provider it produces deterministic titles, captions and hashtags; with an LLM it uses the provider; it never invents platform results.
