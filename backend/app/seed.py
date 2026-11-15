"""Idempotent startup seeding (built-in caption styles)."""
from __future__ import annotations

import logging

from sqlalchemy import select

from .database import session_scope
from .models import CaptionStyle
from .services.captions import BUILTIN_STYLES

logger = logging.getLogger("fireclip.seed")


def seed_builtin_caption_styles() -> None:
    with session_scope() as db:
        existing = {
            style.name
            for style in db.scalars(select(CaptionStyle).where(CaptionStyle.is_builtin.is_(True)))
        }
        for name, config in BUILTIN_STYLES:
            if name in existing:
                continue
            db.add(CaptionStyle(workspace_id=None, name=name, is_builtin=True, config=config))
        logger.info("Built-in caption styles are ready")
