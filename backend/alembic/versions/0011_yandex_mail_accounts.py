"""yandex_mail_accounts

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-28

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "yandex_mail_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("app_password_encrypted", sa.Text(), nullable=False),
        sa.Column("imap_host", sa.Text(), nullable=False, server_default="imap.yandex.ru"),
        sa.Column("imap_port", sa.Integer(), nullable=False, server_default="993"),
        sa.Column("sync_state", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "email", name="uq_yandex_mail_accounts_user_id_email"),
    )
    op.create_index(
        "ix_yandex_mail_accounts_user_id",
        "yandex_mail_accounts",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_yandex_mail_accounts_user_id", table_name="yandex_mail_accounts")
    op.drop_table("yandex_mail_accounts")
