"""campaigns and live automation

Revision ID: 6499d17ad7d2
Revises: 9f2c41d7b8aa
Create Date: 2026-11-24 15:29:27.129632
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "6499d17ad7d2"
down_revision = "9f2c41d7b8aa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("workspace_id", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("brief", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("aspect_ratio", sa.String(length=12), nullable=False),
        sa.Column("target_duration_ms", sa.Integer(), nullable=False),
        sa.Column("clip_count", sa.Integer(), nullable=False),
        sa.Column("min_score", sa.Integer(), nullable=False),
        sa.Column("caption_style_id", sa.String(length=32), nullable=True),
        sa.Column("caption_overrides", sa.JSON(), nullable=False),
        sa.Column("auto_approve", sa.Boolean(), nullable=False),
        sa.Column("auto_render", sa.Boolean(), nullable=False),
        sa.Column("brand", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["caption_style_id"], ["caption_styles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_campaigns_status"), "campaigns", ["status"], unique=False)
    op.create_index(
        "ix_campaigns_workspace_created", "campaigns", ["workspace_id", "created_at"], unique=False
    )
    op.create_index(op.f("ix_campaigns_workspace_id"), "campaigns", ["workspace_id"], unique=False)

    with op.batch_alter_table("editing_projects") as batch:
        batch.add_column(sa.Column("campaign_id", sa.String(length=32), nullable=True))
        batch.create_index(op.f("ix_editing_projects_campaign_id"), ["campaign_id"], unique=False)
        batch.create_foreign_key(
            "fk_editing_projects_campaign_id",
            "campaigns",
            ["campaign_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("live_streams") as batch:
        batch.add_column(sa.Column("campaign_id", sa.String(length=32), nullable=True))
        batch.add_column(
            sa.Column("auto_record", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.add_column(
            sa.Column("auto_clip", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch.add_column(sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_index(op.f("ix_live_streams_campaign_id"), ["campaign_id"], unique=False)
        batch.create_foreign_key(
            "fk_live_streams_campaign_id",
            "campaigns",
            ["campaign_id"],
            ["id"],
            ondelete="SET NULL",
        )
    with op.batch_alter_table("live_streams") as batch:
        batch.alter_column("auto_record", server_default=None)
        batch.alter_column("auto_clip", server_default=None)

    with op.batch_alter_table("source_videos") as batch:
        batch.add_column(sa.Column("campaign_id", sa.String(length=32), nullable=True))
        batch.create_index(op.f("ix_source_videos_campaign_id"), ["campaign_id"], unique=False)
        batch.create_foreign_key(
            "fk_source_videos_campaign_id",
            "campaigns",
            ["campaign_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("source_videos") as batch:
        batch.drop_constraint("fk_source_videos_campaign_id", type_="foreignkey")
        batch.drop_index(op.f("ix_source_videos_campaign_id"))
        batch.drop_column("campaign_id")

    with op.batch_alter_table("live_streams") as batch:
        batch.drop_constraint("fk_live_streams_campaign_id", type_="foreignkey")
        batch.drop_index(op.f("ix_live_streams_campaign_id"))
        batch.drop_column("last_checked_at")
        batch.drop_column("auto_clip")
        batch.drop_column("auto_record")
        batch.drop_column("campaign_id")

    with op.batch_alter_table("editing_projects") as batch:
        batch.drop_constraint("fk_editing_projects_campaign_id", type_="foreignkey")
        batch.drop_index(op.f("ix_editing_projects_campaign_id"))
        batch.drop_column("campaign_id")

    op.drop_index(op.f("ix_campaigns_workspace_id"), table_name="campaigns")
    op.drop_index("ix_campaigns_workspace_created", table_name="campaigns")
    op.drop_index(op.f("ix_campaigns_status"), table_name="campaigns")
    op.drop_table("campaigns")
