#!/bin/sh
set -eu

# Report API reachability once before serving. Next proxies /api and /health to
# API_BASE_URL, so a hostname that lands on the wrong container shows up here
# instead of only as 500s in the access log.
node /app/check-api.mjs || true

exec "$@"
