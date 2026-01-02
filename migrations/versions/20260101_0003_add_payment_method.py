"""Add payment method fields to invoices

Revision ID: 0003
Revises: 0002
Create Date: 2026-01-01

Adds payment tracking fields to invoices:
- metodo_pago: Payment method (efectivo, tarjeta, transferencia)
- banco_origen: Source bank for transfers
- banco_destino: Destination bank for transfers
- referencia_pago: Payment reference/transaction number
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add payment method columns to invoices table."""
    op.add_column('invoices', sa.Column('metodo_pago', sa.String(20), nullable=True))
    op.add_column('invoices', sa.Column('banco_origen', sa.String(50), nullable=True))
    op.add_column('invoices', sa.Column('banco_destino', sa.String(50), nullable=True))
    op.add_column('invoices', sa.Column('referencia_pago', sa.String(50), nullable=True))


def downgrade() -> None:
    """Remove payment method columns from invoices table."""
    op.drop_column('invoices', 'referencia_pago')
    op.drop_column('invoices', 'banco_destino')
    op.drop_column('invoices', 'banco_origen')
    op.drop_column('invoices', 'metodo_pago')
