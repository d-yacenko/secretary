"""object occurred_at and retrieval indexes

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-29

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.add_column(
        "objects",
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_objects_user_occurred_at", "objects", ["user_id", "occurred_at"])

    op.execute(
        """
        CREATE INDEX ix_objects_fts_document ON objects USING gin (
            (
                setweight(to_tsvector('simple', coalesce(title, '')), 'A')
                || setweight(to_tsvector('simple', coalesce(body, '')), 'C')
            )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_objects_title_trgm ON objects USING gin (title gin_trgm_ops)
        """
    )

    op.execute(
        """
        UPDATE objects
        SET occurred_at = (metadata->>'timestamp')::timestamptz
        WHERE occurred_at IS NULL
          AND kind = 'email'
          AND metadata ? 'timestamp'
          AND metadata->>'timestamp' ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}'
        """
    )
    op.execute(
        """
        UPDATE objects
        SET occurred_at = start_at
        WHERE occurred_at IS NULL
          AND kind = 'event'
          AND start_at IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_objects_title_trgm")
    op.execute("DROP INDEX IF EXISTS ix_objects_fts_document")
    op.drop_index("ix_objects_user_occurred_at", table_name="objects")
    op.drop_column("objects", "occurred_at")
