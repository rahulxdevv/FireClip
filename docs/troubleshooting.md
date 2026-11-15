# Troubleshooting

[← Back to README](../README.md)

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

## Known limitations

- No stock B-roll or music library - no fake licensing.
- Smart crop is a static face anchor, not per-frame speaker tracking.
- Diarization is approximate unless pyannote is installed; it is labelled.
- TikTok posting is gated by app approval; metrics need additional scopes.
- Instagram Reels need a public HTTPS media URL.
- No payments, email verification, password reset or notification emails.
- Local speech recognition needs Python 3.10-3.12; Python 3.13+ cannot install PyAV.
- Render free plan sleeps, has 512 MB RAM and ephemeral media.

## What was verified, and what wasn't

Checked in the development environment on **2026-11-15**:

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

**Not verified here:** Docker images and the Render Blueprint could not be launched (Docker is unavailable in this environment); live OAuth, live AI providers and live platform analytics need real credentials. No browser screenshot/E2E pass is included.
