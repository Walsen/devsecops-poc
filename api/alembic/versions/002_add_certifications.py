"""Add certification tables

Revision ID: 002
Revises: 001
Create Date: 2026-02-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'certification_submissions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('member_name', sa.String(100), nullable=False),
        sa.Column('certification_type', sa.String(50), nullable=False),
        sa.Column('certification_date', sa.DateTime(), nullable=False),
        sa.Column('photo_url', sa.String(2048), nullable=True),
        sa.Column('linkedin_url', sa.String(2048), nullable=True),
        sa.Column('personal_message', sa.String(280), nullable=True),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        'ix_certification_submissions_status',
        'certification_submissions',
        ['status']
    )
    op.create_index(
        'ix_certification_submissions_certification_type',
        'certification_submissions',
        ['certification_type']
    )

    op.create_table(
        'certification_deliveries',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('submission_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('channel', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('external_post_id', sa.String(255), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('delivered_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['submission_id'], ['certification_submissions.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        'ix_certification_deliveries_submission_id',
        'certification_deliveries',
        ['submission_id']
    )


def downgrade() -> None:
    op.drop_index('ix_certification_deliveries_submission_id')
    op.drop_table('certification_deliveries')
    op.drop_index('ix_certification_submissions_certification_type')
    op.drop_index('ix_certification_submissions_status')
    op.drop_table('certification_submissions')
