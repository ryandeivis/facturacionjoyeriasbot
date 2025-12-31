"""Database improvements: normalization, traceability, and metrics

Revision ID: 0002
Revises: 0001
Create Date: 2024-12-30

Includes:
- New table: customers (normalized customer data)
- New table: invoice_items (normalized invoice items)
- New table: invoice_drafts (traceability for invoice creation flow)
- New table: metric_events (business and system metrics)
- New columns on organizations: created_by, updated_by
- New columns on users: created_by, updated_by
- New columns on invoices: customer_id, notas, version, created_by, updated_by,
                          cliente_direccion, cliente_ciudad, cliente_email
- New indexes for performance
- CHECK constraints for data integrity
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply database improvements."""

    # =========================================================================
    # 1. ADD COLUMNS TO EXISTING TABLES
    # =========================================================================

    # Organizations: audit columns
    op.add_column('organizations', sa.Column('created_by', sa.String(36), nullable=True))
    op.add_column('organizations', sa.Column('updated_by', sa.String(36), nullable=True))

    # Users: audit columns
    op.add_column('users', sa.Column('created_by', sa.String(36), nullable=True))
    op.add_column('users', sa.Column('updated_by', sa.String(36), nullable=True))

    # Invoices: new columns
    op.add_column('invoices', sa.Column('cliente_direccion', sa.String(300), nullable=True))
    op.add_column('invoices', sa.Column('cliente_ciudad', sa.String(100), nullable=True))
    op.add_column('invoices', sa.Column('cliente_email', sa.String(255), nullable=True))
    op.add_column('invoices', sa.Column('notas', sa.Text(), nullable=True))
    op.add_column('invoices', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('invoices', sa.Column('created_by', sa.String(36), nullable=True))
    op.add_column('invoices', sa.Column('updated_by', sa.String(36), nullable=True))

    # =========================================================================
    # 2. CREATE CUSTOMERS TABLE
    # =========================================================================

    op.create_table(
        'customers',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('nombre', sa.String(200), nullable=False),
        sa.Column('cedula', sa.String(15), nullable=True),
        sa.Column('telefono', sa.String(20), nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('direccion', sa.String(300), nullable=True),
        sa.Column('ciudad', sa.String(100), nullable=True),
        sa.Column('notas', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(36), nullable=True),
        sa.Column('updated_by', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='0'),
    )

    # Customers indexes
    op.create_index('ix_customers_id', 'customers', ['id'])
    op.create_index('ix_customers_organization_id', 'customers', ['organization_id'])
    op.create_index('ix_customers_cedula', 'customers', ['cedula'])
    op.create_index('ix_customers_org_cedula', 'customers', ['organization_id', 'cedula'])
    op.create_index('ix_customers_org_nombre', 'customers', ['organization_id', 'nombre'])
    op.create_index('ix_customers_org_email', 'customers', ['organization_id', 'email'])

    # =========================================================================
    # 3. ADD CUSTOMER_ID TO INVOICES (after customers table exists)
    # Note: For SQLite, FK constraint is at model level, not DB level
    # =========================================================================

    op.add_column('invoices', sa.Column(
        'customer_id',
        sa.String(36),
        nullable=True
    ))
    op.create_index('ix_invoices_customer_id', 'invoices', ['customer_id'])

    # =========================================================================
    # 4. CREATE INVOICE_ITEMS TABLE
    # =========================================================================

    op.create_table(
        'invoice_items',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('invoice_id', sa.String(36), sa.ForeignKey('invoices.id', ondelete='CASCADE'), nullable=False),
        sa.Column('numero', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('descripcion', sa.String(200), nullable=False),
        sa.Column('cantidad', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('precio_unitario', sa.Float(), nullable=False),
        sa.Column('subtotal', sa.Float(), nullable=False),
        sa.Column('material', sa.String(50), nullable=True),
        sa.Column('peso_gramos', sa.Float(), nullable=True),
        sa.Column('tipo_prenda', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Invoice items indexes
    op.create_index('ix_invoice_items_id', 'invoice_items', ['id'])
    op.create_index('ix_invoice_items_invoice_id', 'invoice_items', ['invoice_id'])
    op.create_index('ix_invoice_items_invoice', 'invoice_items', ['invoice_id'])
    op.create_index('ix_invoice_items_descripcion', 'invoice_items', ['descripcion'])
    op.create_index('ix_invoice_items_material', 'invoice_items', ['material'])
    op.create_index('ix_invoice_items_tipo_prenda', 'invoice_items', ['tipo_prenda'])

    # =========================================================================
    # 5. CREATE INVOICE_DRAFTS TABLE (traceability)
    # =========================================================================

    op.create_table(
        'invoice_drafts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('telegram_chat_id', sa.Integer(), nullable=False),
        sa.Column('current_step', sa.String(50), nullable=False, server_default='SELECCIONAR_INPUT'),
        sa.Column('input_type', sa.String(10), nullable=True),
        sa.Column('input_raw', sa.Text(), nullable=True),
        sa.Column('input_file_path', sa.String(500), nullable=True),
        sa.Column('ai_response_raw', sa.Text(), nullable=True),
        sa.Column('ai_extraction_timestamp', sa.DateTime(), nullable=True),
        sa.Column('items_data', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('customer_data', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('totals_data', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('change_history', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('invoice_id', sa.String(36), sa.ForeignKey('invoices.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Invoice drafts indexes
    op.create_index('ix_invoice_drafts_id', 'invoice_drafts', ['id'])
    op.create_index('ix_invoice_drafts_organization_id', 'invoice_drafts', ['organization_id'])
    op.create_index('ix_drafts_org_user', 'invoice_drafts', ['organization_id', 'user_id'])
    op.create_index('ix_drafts_chat', 'invoice_drafts', ['telegram_chat_id'])
    op.create_index('ix_drafts_status', 'invoice_drafts', ['status'])
    op.create_index('ix_drafts_org_status', 'invoice_drafts', ['organization_id', 'status'])

    # =========================================================================
    # 6. CREATE METRIC_EVENTS TABLE
    # =========================================================================

    op.create_table(
        'metric_events',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('value', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('success', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('duration_ms', sa.Float(), nullable=True),
        sa.Column('event_metadata', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Metric events indexes
    op.create_index('ix_metric_events_id', 'metric_events', ['id'])
    op.create_index('ix_metric_events_event_type', 'metric_events', ['event_type'])
    op.create_index('ix_metric_events_organization_id', 'metric_events', ['organization_id'])
    op.create_index('ix_metric_events_created_at', 'metric_events', ['created_at'])
    op.create_index('ix_metrics_org_type', 'metric_events', ['organization_id', 'event_type'])
    op.create_index('ix_metrics_org_date', 'metric_events', ['organization_id', 'created_at'])
    op.create_index('ix_metrics_type_date', 'metric_events', ['event_type', 'created_at'])
    op.create_index('ix_metrics_org_type_date', 'metric_events', ['organization_id', 'event_type', 'created_at'])

    # =========================================================================
    # 7. ADD NEW INDEXES TO INVOICES
    # =========================================================================

    op.create_index('ix_invoices_org_created', 'invoices', ['organization_id', 'created_at'])
    op.create_index('ix_invoices_cliente_cedula', 'invoices', ['cliente_cedula'])

    # =========================================================================
    # 8. CHECK CONSTRAINTS (SQLite compatible - using naming convention)
    # Note: SQLite doesn't support ALTER TABLE ADD CONSTRAINT, so these are
    # documented here but will be enforced at application level for SQLite.
    # For PostgreSQL/MySQL, you can uncomment these.
    # =========================================================================

    # The following constraints are enforced in the SQLAlchemy models:
    # - ck_invoice_items_cantidad_min: cantidad >= 1
    # - ck_invoice_items_precio_min: precio_unitario >= 0
    # - ck_invoice_items_subtotal_min: subtotal >= 0
    # - ck_invoices_subtotal_min: subtotal >= 0
    # - ck_invoices_descuento_min: descuento >= 0
    # - ck_invoices_impuesto_min: impuesto >= 0
    # - ck_invoices_total_min: total >= 0
    # - ck_invoices_estado_valid: estado IN ('BORRADOR', 'PENDIENTE', 'PAGADA', 'ANULADA')

    # For PostgreSQL, uncomment:
    # op.create_check_constraint('ck_invoices_subtotal_min', 'invoices', 'subtotal >= 0')
    # op.create_check_constraint('ck_invoices_descuento_min', 'invoices', 'descuento >= 0')
    # op.create_check_constraint('ck_invoices_impuesto_min', 'invoices', 'impuesto >= 0')
    # op.create_check_constraint('ck_invoices_total_min', 'invoices', 'total >= 0')


def downgrade() -> None:
    """Revert database improvements."""

    # Drop new indexes from invoices
    op.drop_index('ix_invoices_cliente_cedula', table_name='invoices')
    op.drop_index('ix_invoices_org_created', table_name='invoices')

    # Drop metric_events table
    op.drop_index('ix_metrics_org_type_date', table_name='metric_events')
    op.drop_index('ix_metrics_type_date', table_name='metric_events')
    op.drop_index('ix_metrics_org_date', table_name='metric_events')
    op.drop_index('ix_metrics_org_type', table_name='metric_events')
    op.drop_index('ix_metric_events_created_at', table_name='metric_events')
    op.drop_index('ix_metric_events_organization_id', table_name='metric_events')
    op.drop_index('ix_metric_events_event_type', table_name='metric_events')
    op.drop_index('ix_metric_events_id', table_name='metric_events')
    op.drop_table('metric_events')

    # Drop invoice_drafts table
    op.drop_index('ix_drafts_org_status', table_name='invoice_drafts')
    op.drop_index('ix_drafts_status', table_name='invoice_drafts')
    op.drop_index('ix_drafts_chat', table_name='invoice_drafts')
    op.drop_index('ix_drafts_org_user', table_name='invoice_drafts')
    op.drop_index('ix_invoice_drafts_organization_id', table_name='invoice_drafts')
    op.drop_index('ix_invoice_drafts_id', table_name='invoice_drafts')
    op.drop_table('invoice_drafts')

    # Drop invoice_items table
    op.drop_index('ix_invoice_items_tipo_prenda', table_name='invoice_items')
    op.drop_index('ix_invoice_items_material', table_name='invoice_items')
    op.drop_index('ix_invoice_items_descripcion', table_name='invoice_items')
    op.drop_index('ix_invoice_items_invoice', table_name='invoice_items')
    op.drop_index('ix_invoice_items_invoice_id', table_name='invoice_items')
    op.drop_index('ix_invoice_items_id', table_name='invoice_items')
    op.drop_table('invoice_items')

    # Drop customer_id from invoices
    op.drop_index('ix_invoices_customer_id', table_name='invoices')
    op.drop_column('invoices', 'customer_id')

    # Drop customers table
    op.drop_index('ix_customers_org_email', table_name='customers')
    op.drop_index('ix_customers_org_nombre', table_name='customers')
    op.drop_index('ix_customers_org_cedula', table_name='customers')
    op.drop_index('ix_customers_cedula', table_name='customers')
    op.drop_index('ix_customers_organization_id', table_name='customers')
    op.drop_index('ix_customers_id', table_name='customers')
    op.drop_table('customers')

    # Drop new columns from invoices
    op.drop_column('invoices', 'updated_by')
    op.drop_column('invoices', 'created_by')
    op.drop_column('invoices', 'version')
    op.drop_column('invoices', 'notas')
    op.drop_column('invoices', 'cliente_email')
    op.drop_column('invoices', 'cliente_ciudad')
    op.drop_column('invoices', 'cliente_direccion')

    # Drop audit columns from users
    op.drop_column('users', 'updated_by')
    op.drop_column('users', 'created_by')

    # Drop audit columns from organizations
    op.drop_column('organizations', 'updated_by')
    op.drop_column('organizations', 'created_by')
