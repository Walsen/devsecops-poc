"""Initial schema - messages and channel deliveries

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Messages table
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("content_media_url", sa.String(2048), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("recipient_id", sa.String(255), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # Channel deliveries table
    op.create_table(
        "channel_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )

    # Index for finding pending deliveries
    op.create_index(
        "ix_channel_deliveries_message_status",
        "channel_deliveries",
        ["message_id", "status"],
    )

    # Index for scheduled messages query
    op.create_index(
        "ix_messages_scheduled_status",
        "messages",
        ["scheduled_at", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_messages_scheduled_status", table_name="messages")
    op.drop_index("ix_channel_deliveries_message_status", table_name="channel_deliveries")
    op.drop_table("channel_deliveries")
    op.drop_table("messages")
