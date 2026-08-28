import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Index, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Object(Base):
    __tablename__ = "objects"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(nullable=False)
    body: Mapped[str | None] = mapped_column(nullable=True)
    provider: Mapped[str | None] = mapped_column(nullable=True)
    external_id: Mapped[str | None] = mapped_column(nullable=True)
    canonical_uri: Mapped[str | None] = mapped_column(nullable=True)
    status: Mapped[str | None] = mapped_column(nullable=True)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    origin: Mapped[str] = mapped_column(nullable=False)
    state: Mapped[str] = mapped_column(nullable=False, server_default="confirmed")
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(), nullable=True)
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

    __table_args__ = (
        Index("ix_objects_kind", "kind"),
        Index("ix_objects_status", "status"),
        Index("ix_objects_state", "state"),
        Index("ix_objects_due_at", "due_at"),
        Index(
            "uq_objects_provider_kind_external_id",
            "provider",
            "kind",
            "external_id",
            unique=True,
            postgresql_where=text("provider IS NOT NULL AND external_id IS NOT NULL"),
        ),
    )


class Edge(Base):
    __tablename__ = "edges"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("objects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("objects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(nullable=False)
    origin: Mapped[str] = mapped_column(nullable=False)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    state: Mapped[str] = mapped_column(nullable=False)
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
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

    __table_args__ = (
        Index("ix_edges_source_id", "source_id"),
        Index("ix_edges_target_id", "target_id"),
        Index("ix_edges_type", "type"),
    )


class View(Base):
    __tablename__ = "views"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(nullable=False)
    view_type: Mapped[str] = mapped_column(nullable=False)
    root_object_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("objects.id", ondelete="SET NULL"),
        nullable=True,
    )
    settings_: Mapped[dict] = mapped_column(
        "settings",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
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


class ViewItem(Base):
    __tablename__ = "view_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    view_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("views.id", ondelete="CASCADE"),
        nullable=False,
    )
    object_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("objects.id", ondelete="CASCADE"),
        nullable=True,
    )
    visual_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    x: Mapped[float | None] = mapped_column(nullable=True)
    y: Mapped[float | None] = mapped_column(nullable=True)
    width: Mapped[float | None] = mapped_column(nullable=True)
    height: Mapped[float | None] = mapped_column(nullable=True)
    collapsed: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    settings_: Mapped[dict] = mapped_column(
        "settings",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
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

    __table_args__ = (
        sa.CheckConstraint(
            "(object_id IS NOT NULL AND visual_id IS NULL) "
            "OR (object_id IS NULL AND visual_id IS NOT NULL)",
            name="ck_view_items_object_xor_visual",
        ),
    )


class Representation(Base):
    __tablename__ = "representations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    object_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("objects.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(nullable=False)
    part_index: Mapped[int | None] = mapped_column(nullable=True)
    text: Mapped[str | None] = mapped_column(nullable=True)
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(), nullable=True)
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

    __table_args__ = (
        Index("ix_representations_object_id", "object_id"),
        Index("ix_representations_kind", "kind"),
    )


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    type: Mapped[str] = mapped_column(nullable=False)
    payload: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    status: Mapped[str] = mapped_column(nullable=False)
    attempts: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    run_after: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(nullable=True)
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

    __table_args__ = (
        Index("ix_jobs_status_run_after", "status", "run_after"),
    )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(nullable=False)
    body: Mapped[str | None] = mapped_column(nullable=True)
    priority: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False)
    source_object_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("objects.id", ondelete="SET NULL"),
        nullable=True,
    )
    related_object_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("objects.id", ondelete="SET NULL"),
        nullable=True,
    )
    proposal_: Mapped[dict] = mapped_column(
        "proposal",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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

    __table_args__ = (
        Index("ix_notifications_status", "status"),
        Index("ix_notifications_priority", "priority"),
        Index("ix_notifications_created_at", "created_at"),
    )


class GoogleAccount(Base):
    __tablename__ = "google_accounts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(nullable=False, unique=True)
    scopes: Mapped[list] = mapped_column(JSONB, nullable=False)
    access_token_encrypted: Mapped[str | None] = mapped_column(nullable=True)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(nullable=True)
    token_expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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


class OAuthState(Base):
    __tablename__ = "oauth_states"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    state_hash: Mapped[str] = mapped_column(nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (Index("ix_oauth_states_state_hash", "state_hash"),)
