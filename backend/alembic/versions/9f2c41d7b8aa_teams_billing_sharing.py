"""teams, billing, sharing and webhooks

Revision ID: 9f2c41d7b8aa
Revises: 87c08e60d597
Create Date: 2026-11-24 09:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "9f2c41d7b8aa"
down_revision = "87c08e60d597"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    for name, column in (
        ("plan_status", sa.Column("plan_status", sa.String(length=24), nullable=False, server_default="active")),
        ("plan_interval", sa.Column("plan_interval", sa.String(length=12), nullable=False, server_default="month")),
        ("plan_renews_at", sa.Column("plan_renews_at", sa.DateTime(timezone=True), nullable=True)),
        ("stripe_customer_id", sa.Column("stripe_customer_id", sa.String(length=80), nullable=True)),
        ("stripe_subscription_id", sa.Column("stripe_subscription_id", sa.String(length=80), nullable=True)),
    ):
        op.add_column("workspaces", column)
    op.add_column("webhook_endpoints", sa.Column("description", sa.String(length=160), nullable=True))
    op.add_column("webhook_endpoints", sa.Column("events", sa.JSON(), nullable=True))
    op.execute("UPDATE webhook_endpoints SET description = '' WHERE description IS NULL")
    op.execute("UPDATE webhook_endpoints SET events = '[]' WHERE events IS NULL")
    with op.batch_alter_table("webhook_endpoints") as batch:
        batch.alter_column("description", existing_type=sa.String(length=160), nullable=False)
        batch.alter_column("events", existing_type=sa.JSON(), nullable=False)

    op.create_table(
        "email_tokens",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=True),
        sa.Column("workspace_id", sa.String(length=32), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_email_tokens_user_id"), "email_tokens", ["user_id"], unique=False)
    op.create_index(op.f("ix_email_tokens_workspace_id"), "email_tokens", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_email_tokens_email"), "email_tokens", ["email"], unique=False)
    op.create_index(op.f("ix_email_tokens_token_hash"), "email_tokens", ["token_hash"], unique=True)
    op.create_index("ix_email_tokens_email_kind", "email_tokens", ["email", "kind"], unique=False)

    op.create_table(
        "clip_comments",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("workspace_id", sa.String(length=32), nullable=False),
        sa.Column("clip_id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["clip_id"], ["candidate_clips.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_clip_comments_workspace_id"), "clip_comments", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_clip_comments_clip_id"), "clip_comments", ["clip_id"], unique=False)
    op.create_index("ix_clip_comments_clip_created", "clip_comments", ["clip_id", "created_at"], unique=False)

    op.create_table(
        "share_links",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("workspace_id", sa.String(length=32), nullable=False),
        sa.Column("exported_video_id", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.String(length=32), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("view_count", sa.Integer(), nullable=False),
        sa.Column("last_viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["exported_video_id"], ["exported_videos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_share_links_workspace_id"), "share_links", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_share_links_exported_video_id"), "share_links", ["exported_video_id"], unique=False)
    op.create_index(op.f("ix_share_links_token"), "share_links", ["token"], unique=True)

    op.create_table(
        "billing_invoices",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("workspace_id", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=24), nullable=False),
        sa.Column("external_id", sa.String(length=120), nullable=False),
        sa.Column("number", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("hosted_url", sa.Text(), nullable=False),
        sa.Column("pdf_url", sa.Text(), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_billing_invoices_workspace_id"), "billing_invoices", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_billing_invoices_external_id"), "billing_invoices", ["external_id"], unique=True)

    op.create_table(
        "billing_events",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=24), nullable=False),
        sa.Column("external_id", sa.String(length=120), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_billing_events_external_id"), "billing_events", ["external_id"], unique=True)

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("endpoint_id", sa.String(length=32), nullable=False),
        sa.Column("workspace_id", sa.String(length=32), nullable=False),
        sa.Column("event", sa.String(length=80), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["endpoint_id"], ["webhook_endpoints.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_webhook_deliveries_endpoint_id"), "webhook_deliveries", ["endpoint_id"], unique=False)
    op.create_index("ix_webhook_deliveries_endpoint_created", "webhook_deliveries", ["endpoint_id", "created_at"], unique=False)
    op.create_index(op.f("ix_webhook_deliveries_event"), "webhook_deliveries", ["event"], unique=False)
    op.create_index(op.f("ix_webhook_deliveries_workspace_id"), "webhook_deliveries", ["workspace_id"], unique=False)


def downgrade() -> None:
    op.drop_table("webhook_deliveries")
    op.drop_table("billing_events")
    op.drop_table("billing_invoices")
    op.drop_table("share_links")
    op.drop_table("clip_comments")
    op.drop_table("email_tokens")
    op.drop_column("webhook_endpoints", "events")
    op.drop_column("webhook_endpoints", "description")
    with op.batch_alter_table("workspaces") as batch:
        batch.drop_column("stripe_subscription_id")
        batch.drop_column("stripe_customer_id")
        batch.drop_column("plan_renews_at")
        batch.drop_column("plan_interval")
        batch.drop_column("plan_status")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("email_verified_at")
