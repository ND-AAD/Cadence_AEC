"""
Infrastructure models: Users, Permissions, Notifications.

These support the core three tables but are not part of the
fundamental data model.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    """
    Operators of the system.

    Distinct from sources: a user is the person performing an action
    (created_by), while a source is the document authority (source_id
    on snapshots).
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.uuid_generate_v4(),
    )
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"


class Permission(Base):
    """
    Scoped permissions for users.

    scope_item_id references the item (typically a project) that
    this permission applies to.
    """

    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.uuid_generate_v4(),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    scope_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("items.id", ondelete="CASCADE"),
        nullable=False,
        comment="The item (project) this permission is scoped to.",
    )
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="viewer",
        comment="Role: admin, editor, viewer.",
    )
    can_resolve_conflicts: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    can_import: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    can_edit: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    __table_args__ = (
        Index("idx_permissions_user", "user_id"),
        Index("idx_permissions_scope", "scope_item_id"),
        Index("idx_permissions_user_scope", "user_id", "scope_item_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<Permission user={self.user_id} scope={self.scope_item_id} role={self.role}>"


class Notification(Base):
    """User notifications for conflicts, changes, decisions, etc."""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.uuid_generate_v4(),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    related_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("items.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index("idx_notifications_user", "user_id"),
        Index("idx_notifications_user_unread", "user_id", "is_read"),
    )

    def __repr__(self) -> str:
        return f"<Notification {self.title[:30]}>"
