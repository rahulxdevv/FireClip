"""remove the free plan

Revision ID: b7a1c4d2e9f0
Revises: 7b3f9c2a1d64
Create Date: 2026-11-27 10:00:00.000000
"""
from __future__ import annotations

from alembic import op


revision = "b7a1c4d2e9f0"
down_revision = "7b3f9c2a1d64"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing free workspaces move to the entry plan and its limits.
    op.execute(
        "UPDATE workspaces SET plan = 'starter', "
        "monthly_clip_limit = 300, monthly_render_minutes = 300 "
        "WHERE plan = 'free'"
    )


def downgrade() -> None:
    # The free plan is intentionally not restored.
    pass
