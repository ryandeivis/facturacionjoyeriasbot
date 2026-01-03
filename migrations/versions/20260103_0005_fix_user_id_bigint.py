"""Fix user_id column to BIGINT for Telegram user IDs

Revision ID: 0005
Revises: 0004
Create Date: 2026-01-03

Telegram user IDs can exceed INTEGER max value (~2.1 billion).
This migration changes user_id to BIGINT to support larger IDs.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0005'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Change user_id from INTEGER to BIGINT."""
    # metric_events.user_id
    op.alter_column(
        'metric_events',
        'user_id',
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True
    )


def downgrade() -> None:
    """Revert user_id back to INTEGER."""
    op.alter_column(
        'metric_events',
        'user_id',
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True
    )
