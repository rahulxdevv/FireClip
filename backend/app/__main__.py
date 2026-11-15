"""Run the API with ports from .env: ``python -m app``."""
from __future__ import annotations

import uvicorn

from .config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
