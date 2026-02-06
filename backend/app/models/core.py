"""
Core data models: Items, Connections, Snapshots.

The entire Cadence data model rests on three tables and a triple.

Snapshot triple: (item_id, context_id, source_id) answers:
  - WHAT item is being described
  - WHEN (at which milestone / context)
  - WHO SAYS (which source is making this assertion)

Conflicts: same (what, when), different (who says)
Changes: same (what, who says), different (when)
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Item(Base):
    """
    Everything is an item.

    Physical things (doors, rooms, buildings), documents (schedules, specs),
    temporal anchors (milestones, phases), workflow artifacts (changes,
    conflicts, decisions, notes) — all items in a flat graph.

    item_type is application configuration, not schema. Adding a new type
    requires zero migrations.
    """

    __tablename__ = "items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.uuid_generate_v4(),
    )
    item_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Application-level type: door, room, milestone, conflict, etc.",
    )
    identifier: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Human-readable identifier: door number, room name, etc.",
    )
    properties: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Type-specific properties as JSON.",
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        comment="The operator who created this item.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    outgoing_connections: Mapped[list["Connection"]] = relationship(
        "Connection",
        foreign_keys="Connection.source_item_id",
        back_populates="source_item",
        lazy="selectin",
    )
    incoming_connections: Mapped[list["Connection"]] = relationship(
        "Connection",
        foreign_keys="Connection.target_item_id",
        back_populates="target_item",
        lazy="selectin",
    )
    snapshots: Mapped[list["Snapshot"]] = relationship(
        "Snapshot",
        foreign_keys="Snapshot.item_id",
        back_populates="item",
        lazy="selectin",
    )

    __table_args__ = (
        Index("idx_items_type", "item_type"),
        Index("idx_items_identifier", "identifier"),
        Index(
            "idx_items_identifier_trgm",
            "identifier",
            postgresql_using="gin",
            postgresql_ops={"identifier": "gin_trgm_ops"},
        ),
    )

    def __repr__(self) -> str:
        return f"<Item {self.item_type}:{self.identifier or self.id}>"


class Connection(Base):
    """
    Semantically minimal, directional relationships between items.

    Convention:
      - Container/authority → contained/described
        (project → building, schedule → door)
      - Workflow items reverse: point TO what they reference
        (conflict → door, decision → conflict)

    No enforced hierarchy. The graph is flat; navigation imposes
    hierarchy through breadcrumb traversal.
    """

    __tablename__ = "connections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.uuid_generate_v4(),
    )
    source_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("items.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("items.id", ondelete="CASCADE"),
        nullable=False,
    )
    properties: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Connection metadata: relationship_type, etc.",
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    source_item: Mapped["Item"] = relationship(
        "Item",
        foreign_keys=[source_item_id],
        back_populates="outgoing_connections",
    )
    target_item: Mapped["Item"] = relationship(
        "Item",
        foreign_keys=[target_item_id],
        back_populates="incoming_connections",
    )

    __table_args__ = (
        Index("idx_connections_source", "source_item_id"),
        Index("idx_connections_target", "target_item_id"),
        Index("idx_connections_pair", "source_item_id", "target_item_id"),
    )

    def __repr__(self) -> str:
        return f"<Connection {self.source_item_id} → {self.target_item_id}>"


class Snapshot(Base):
    """
    Source-attributed assertions: the snapshot triple.

    (item_id, context_id, source_id) answers:
      WHAT: which item is being described
      WHEN: at which milestone (context)
      WHO SAYS: which source makes this assertion

    context_id is always a milestone item.
    source_id is always a source item (schedule, specification, etc.)
      — or the item itself for self-sourced items (source_id = item_id).

    A value is current until superseded: the most recent snapshot from a
    source (by milestone ordinal) is the effective value.
    """

    __tablename__ = "snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.uuid_generate_v4(),
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("items.id", ondelete="CASCADE"),
        nullable=False,
        comment="WHAT: the item being described.",
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("items.id", ondelete="CASCADE"),
        nullable=False,
        comment="WHEN: the milestone at which this assertion is made.",
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("items.id", ondelete="CASCADE"),
        nullable=False,
        comment="WHO SAYS: the source making this assertion.",
    )
    properties: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="The asserted property values.",
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        comment="The operator who created this snapshot.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    item: Mapped["Item"] = relationship(
        "Item",
        foreign_keys=[item_id],
        back_populates="snapshots",
    )
    context: Mapped["Item"] = relationship(
        "Item",
        foreign_keys=[context_id],
    )
    source: Mapped["Item"] = relationship(
        "Item",
        foreign_keys=[source_id],
    )

    __table_args__ = (
        # The triple: core lookup pattern
        Index("idx_snapshots_triple", "item_id", "context_id", "source_id"),
        # Conflict detection: same (what, when), different (who says)
        Index("idx_snapshots_what_when", "item_id", "context_id"),
        # Change detection: same (what, who says), different (when)
        Index("idx_snapshots_what_who", "item_id", "source_id"),
        # Source lookup
        Index("idx_snapshots_source", "source_id"),
        # Context lookup
        Index("idx_snapshots_context", "context_id"),
    )

    def __repr__(self) -> str:
        return f"<Snapshot item={self.item_id} ctx={self.context_id} src={self.source_id}>"
