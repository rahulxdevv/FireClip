"""Refuse work that would exhaust the disk or a workspace storage cap."""
from __future__ import annotations

import shutil

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import ExportedVideo, SourceVideo

GIGABYTE = 1024 ** 3


class StorageGuardError(RuntimeError):
    pass


def workspace_bytes(db: Session, workspace_id: str) -> int:
    uploads = int(
        db.scalar(
            select(func.coalesce(func.sum(SourceVideo.size_bytes), 0)).where(
                SourceVideo.workspace_id == workspace_id
            )
        )
        or 0
    )
    exports = int(
        db.scalar(
            select(func.coalesce(func.sum(ExportedVideo.size_bytes), 0)).where(
                ExportedVideo.workspace_id == workspace_id
            )
        )
        or 0
    )
    return uploads + exports


def check_disk(incoming_bytes: int = 0) -> None:
    """Raise when the local media volume is below its reserve."""
    if settings.storage_backend.lower() == "s3" or settings.min_free_disk_gb <= 0:
        return
    try:
        free = shutil.disk_usage(settings.data_dir).free
    except OSError:
        return
    reserve = int(settings.min_free_disk_gb * GIGABYTE)
    if free - max(0, int(incoming_bytes)) < reserve:
        raise StorageGuardError(
            f"The media volume is low on space ({free / GIGABYTE:.2f} GB free). "
            "Free space before starting more work."
        )


def check_capacity(db: Session, workspace_id: str, incoming_bytes: int = 0) -> None:
    """Raise before an upload, render or export fills the volume."""
    incoming = max(0, int(incoming_bytes))
    if settings.max_workspace_storage_gb > 0:
        used = workspace_bytes(db, workspace_id)
        limit = int(settings.max_workspace_storage_gb * GIGABYTE)
        if used + incoming > limit:
            raise StorageGuardError(
                f"This workspace would exceed its {settings.max_workspace_storage_gb:g} GB storage "
                f"limit ({used / GIGABYTE:.2f} GB used). Delete old exports or raise the limit."
            )
    check_disk(incoming)

