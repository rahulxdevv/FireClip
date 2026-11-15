# Third-party licenses

[← Back to README](../README.md)

FireClip's own code is AGPL-3.0 (see [LICENSE](../LICENSE)); the components it depends on keep their own licenses:

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

The CI `licenses` job does this on every run and uploads `licenses/python.md` and `licenses/node.json` as a build artifact, so this table can be checked against generated output rather than memory.
