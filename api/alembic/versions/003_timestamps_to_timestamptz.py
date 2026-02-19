"""Convert all timestamp columns to timezone-aware (TIMESTAMPTZ)

Revision ID: 003
Revises: 002
Create Date: 2026-02-19

"""

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# All (table, column) pairs that need migration
TIMESTAMP_COLUMNS = [
    ("messages", "scheduled_at"),
    ("messages", "created_at"),
    ("messages", "updated_at"),
    ("channel_deliveries", "delivered_at"),
    ("certification_submissions", "certification_date"),
    ("certification_submissions", "created_at"),
    ("certification_submissions", "updated_at"),
    ("certification_deliveries", "delivered_at"),
]


def upgrade() -> None:
    for table, column in TIMESTAMP_COLUMNS:
        op.execute(
            text(
                f"ALTER TABLE {table} "
                f"ALTER COLUMN {column} TYPE TIMESTAMPTZ "
                f"USING {column} AT TIME ZONE 'UTC'"
            )
        )


def downgrade() -> None:
    for table, column in TIMESTAMP_COLUMNS:
        op.execute(
            text(
                f"ALTER TABLE {table} "
                f"ALTER COLUMN {column} TYPE TIMESTAMP WITHOUT TIME ZONE "
                f"USING {column} AT TIME ZONE 'UTC'"
            )
        )
