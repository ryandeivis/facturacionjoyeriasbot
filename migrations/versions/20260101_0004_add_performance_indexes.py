"""Add performance indexes for metrics and queries

Revision ID: 0004
Revises: 0003
Create Date: 2026-01-01

Adds composite indexes to improve query performance:
- idx_metrics_org_type_date: For metrics queries filtered by org, type, and date
- idx_invoices_org_numero: For invoice lookups by organization and number
- idx_customers_org_cedula: For customer lookups by organization and cedula
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add performance indexes."""
    # Index for metrics queries (HIGH-010, HIGH-011)
    # Improves: get_recent_events, get_event_counts, get_daily_stats
    op.create_index(
        'idx_metrics_org_type_date',
        'metric_events',
        ['organization_id', 'event_type', 'created_at'],
        unique=False
    )

    # Index for invoice lookups by organization and number
    # Improves: get_invoice_by_number, generate_invoice_number
    op.create_index(
        'idx_invoices_org_numero',
        'invoices',
        ['organization_id', 'numero_factura'],
        unique=False
    )

    # Index for customer lookups by organization and cedula
    # Improves: get_customer_by_cedula, find_or_create_customer
    op.create_index(
        'idx_customers_org_cedula',
        'customers',
        ['organization_id', 'cedula'],
        unique=False
    )

    # Index for invoice items by invoice_id
    # Improves: get_items_by_invoice, replace_items
    op.create_index(
        'idx_items_invoice_id',
        'invoice_items',
        ['invoice_id'],
        unique=False
    )


def downgrade() -> None:
    """Remove performance indexes."""
    op.drop_index('idx_items_invoice_id', table_name='invoice_items')
    op.drop_index('idx_customers_org_cedula', table_name='customers')
    op.drop_index('idx_invoices_org_numero', table_name='invoices')
    op.drop_index('idx_metrics_org_type_date', table_name='metric_events')
