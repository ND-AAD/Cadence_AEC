"""Initial schema: three core tables + infrastructure.

Revision ID: 001
Revises: None
Create Date: 2026-02-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Extensions ──────────────────────────────────────────
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm"')

    # ── Users (must come first — referenced by created_by) ──
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
    )

    # ── Items ───────────────────────────────────────────────
    op.create_table(
        "items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("item_type", sa.String(100), nullable=False),
        sa.Column("identifier", sa.String(500), nullable=True),
        sa.Column("properties", JSONB, nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_items_type", "items", ["item_type"])
    op.create_index("idx_items_identifier", "items", ["identifier"])
    op.execute(
        "CREATE INDEX idx_items_identifier_trgm ON items "
        "USING gin (identifier gin_trgm_ops)"
    )

    # ── Connections ─────────────────────────────────────────
    op.create_table(
        "connections",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("source_item_id", UUID(as_uuid=True),
                  sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_item_id", UUID(as_uuid=True),
                  sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("properties", JSONB, nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_connections_source", "connections", ["source_item_id"])
    op.create_index("idx_connections_target", "connections", ["target_item_id"])
    op.create_index("idx_connections_pair", "connections",
                    ["source_item_id", "target_item_id"])

    # ── Snapshots ───────────────────────────────────────────
    op.create_table(
        "snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("item_id", UUID(as_uuid=True),
                  sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("context_id", UUID(as_uuid=True),
                  sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_id", UUID(as_uuid=True),
                  sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("properties", JSONB, nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
    )
    # The triple
    op.create_index("idx_snapshots_triple", "snapshots",
                    ["item_id", "context_id", "source_id"])
    # Conflict detection: same (what, when)
    op.create_index("idx_snapshots_what_when", "snapshots",
                    ["item_id", "context_id"])
    # Change detection: same (what, who says)
    op.create_index("idx_snapshots_what_who", "snapshots",
                    ["item_id", "source_id"])
    op.create_index("idx_snapshots_source", "snapshots", ["source_id"])
    op.create_index("idx_snapshots_context", "snapshots", ["context_id"])

    # ── Permissions ─────────────────────────────────────────
    op.create_table(
        "permissions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope_item_id", UUID(as_uuid=True),
                  sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="viewer"),
        sa.Column("can_resolve_conflicts", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
        sa.Column("can_import", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
        sa.Column("can_edit", sa.Boolean, nullable=False,
                  server_default=sa.text("true")),
    )
    op.create_index("idx_permissions_user", "permissions", ["user_id"])
    op.create_index("idx_permissions_scope", "permissions", ["scope_item_id"])
    op.create_index("idx_permissions_user_scope", "permissions",
                    ["user_id", "scope_item_id"], unique=True)

    # ── Notifications ───────────────────────────────────────
    op.create_table(
        "notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("related_item_id", UUID(as_uuid=True),
                  sa.ForeignKey("items.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("is_read", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_notifications_user", "notifications", ["user_id"])
    op.create_index("idx_notifications_user_unread", "notifications",
                    ["user_id", "is_read"])


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("permissions")
    op.drop_table("snapshots")
    op.drop_table("connections")
    op.drop_table("items")
    op.drop_table("users")
