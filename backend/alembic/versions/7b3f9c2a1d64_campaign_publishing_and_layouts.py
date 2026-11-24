"""campaign publishing, discovery and clip layouts

Revision ID: 7b3f9c2a1d64
Revises: 6499d17ad7d2
Create Date: 2026-11-24 17:10:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "7b3f9c2a1d64"
down_revision = "6499d17ad7d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("campaigns") as batch:
        batch.add_column(sa.Column("auto_publish", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("auto_publish_min_score", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("publish_account_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
        batch.add_column(sa.Column("publish_mode", sa.String(length=16), nullable=False, server_default="now"))
        batch.add_column(sa.Column("publish_hour_utc", sa.Integer(), nullable=False, server_default="18"))
        batch.add_column(sa.Column("publish_privacy", sa.String(length=24), nullable=False, server_default="public"))
        batch.add_column(sa.Column("source", sa.String(length=24), nullable=False, server_default="internal"))
        batch.add_column(sa.Column("source_url", sa.Text(), nullable=True))
        batch.add_column(sa.Column("external_id", sa.String(length=160), nullable=True))
        batch.create_index(op.f("ix_campaigns_external_id"), ["external_id"], unique=False)
    with op.batch_alter_table("campaigns") as batch:
        for name in ("auto_publish", "auto_publish_min_score", "publish_account_ids", "publish_mode", "publish_hour_utc", "publish_privacy", "source"):
            batch.alter_column(name, server_default=None)

    with op.batch_alter_table("editing_projects") as batch:
        batch.add_column(sa.Column("caption_translation", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
        batch.add_column(sa.Column("layout", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    with op.batch_alter_table("editing_projects") as batch:
        batch.alter_column("caption_translation", server_default=None)
        batch.alter_column("layout", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("editing_projects") as batch:
        batch.drop_column("layout")
        batch.drop_column("caption_translation")

    with op.batch_alter_table("campaigns") as batch:
        batch.drop_index(op.f("ix_campaigns_external_id"))
        batch.drop_column("external_id")
        batch.drop_column("source_url")
        batch.drop_column("source")
        batch.drop_column("publish_privacy")
        batch.drop_column("publish_hour_utc")
        batch.drop_column("publish_mode")
        batch.drop_column("publish_account_ids")
        batch.drop_column("auto_publish_min_score")
        batch.drop_column("auto_publish")
