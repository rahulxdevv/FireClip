#!/bin/sh
set -eu

# Single-service deployment: FastAPI on 8000 (internal), Next.js on $PORT
# (public). Next rewrites /api and /health to the local API, so cookies and
# uploads stay same-origin without a separate reverse proxy.
export PORT="${PORT:-10000}"

cd /app/backend
echo "Applying database migrations..."
alembic upgrade head

exec supervisord -c /etc/supervisor/conf.d/fireclip.conf
