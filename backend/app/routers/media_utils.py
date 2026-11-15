"""Authenticated media streaming with HTTP Range support."""
from __future__ import annotations

import mimetypes
import re
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse

from ..storage import get_storage

RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")


def serve_key(request: Request, key: str, *, filename: str | None = None, inline: bool = True):
    storage = get_storage()
    if not storage.exists(key):
        raise HTTPException(status_code=404, detail="File not found")
    content_type = mimetypes.guess_type(filename or key)[0] or "application/octet-stream"
    path = storage.local_path(key)
    if path is None:
        return StreamingResponse(storage.open(key), media_type=content_type)

    size = path.stat().st_size
    range_header = request.headers.get("range")
    if range_header:
        match = RANGE_RE.match(range_header.strip())
        if not match:
            raise HTTPException(status_code=416, detail="Invalid Range header")
        start_raw, end_raw = match.groups()
        start = int(start_raw) if start_raw else 0
        end = int(end_raw) if end_raw else size - 1
        end = min(end, size - 1)
        if start >= size or start > end:
            raise HTTPException(status_code=416, detail="Requested range not satisfiable")
        length = end - start + 1
        with open(path, "rb") as handle:
            handle.seek(start)
            data = handle.read(length)
        headers = {
            "Content-Range": f"bytes {start}-{end}/{size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
            "Cache-Control": "private, max-age=60",
        }
        return Response(content=data, status_code=206, media_type=content_type, headers=headers)

    headers = {"Accept-Ranges": "bytes", "Cache-Control": "private, max-age=300"}
    disposition = "inline" if inline else "attachment"
    if filename:
        headers["Content-Disposition"] = f'{disposition}; filename="{Path(filename).name}"'
    return FileResponse(path, media_type=content_type, headers=headers)
