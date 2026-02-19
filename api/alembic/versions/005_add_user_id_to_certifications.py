"""Add user_id column to certification_submissions for IDOR prevention

Revision ID: 005
Revises: 004
Create Date: 2026-02-18

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add user_id column (nullable first for existing rows)
    op.add_column("certification_submissions", sa.Column("user_id", sa.String(255), nullable=True))

    # Backfill existing rows with a placeholder
    op.execute("UPDATE certification_submissions SET user_id = 'unknown' WHERE user_id IS NULL")

    # Make non-nullable
    op.alter_column("certification_submissions", "user_id", nullable=False)

    # Index for user-scoped queries
    op.create_index("ix_certification_submissions_user_id", "certification_submissions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_certification_submissions_user_id", table_name="certification_submissions")
    op.drop_column("certification_submissions", "user_id")
