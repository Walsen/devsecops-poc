"""Add user_id column to messages for IDOR prevention

Revision ID: 004
Revises: 003
Create Date: 2026-02-18

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add user_id column (nullable first for existing rows)
    op.add_column("messages", sa.Column("user_id", sa.String(255), nullable=True))

    # Backfill existing rows with a placeholder
    op.execute("UPDATE messages SET user_id = 'unknown' WHERE user_id IS NULL")

    # Make non-nullable
    op.alter_column("messages", "user_id", nullable=False)

    # Index for user-scoped queries
    op.create_index("ix_messages_user_id", "messages", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_messages_user_id", table_name="messages")
    op.drop_column("messages", "user_id")
