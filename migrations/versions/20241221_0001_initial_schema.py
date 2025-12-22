"""Initial schema with multi-tenancy support

Revision ID: 0001
Revises:
Create Date: 2024-12-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial database schema with multi-tenancy support."""

    # Organizations table (tenants)
    op.create_table(
        'organizations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('slug', sa.String(50), unique=True, nullable=False),
        sa.Column('plan', sa.String(20), nullable=False, server_default='basic'),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('settings', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('telefono', sa.String(20), nullable=True),
        sa.Column('direccion', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='0'),
    )
    op.create_index('ix_organizations_id', 'organizations', ['id'])
    op.create_index('ix_organizations_slug', 'organizations', ['slug'], unique=True)
    op.create_index('ix_organizations_deleted_at', 'organizations', ['deleted_at'])
    op.create_index('ix_organizations_is_deleted', 'organizations', ['is_deleted'])

    # Tenant configs table
    op.create_table(
        'tenant_configs',
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('invoice_prefix', sa.String(10), nullable=False, server_default='FAC'),
        sa.Column('tax_rate', sa.Float(), nullable=False, server_default='0.19'),
        sa.Column('currency', sa.String(3), nullable=False, server_default='COP'),
        sa.Column('settings', sa.Text(), nullable=False, server_default='{}'),
    )

    # Users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('cedula', sa.String(15), nullable=False),
        sa.Column('nombre_completo', sa.String(200), nullable=False),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('telefono', sa.String(20), nullable=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('rol', sa.String(50), nullable=False),
        sa.Column('telegram_id', sa.Integer(), nullable=True),
        sa.Column('activo', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('ultimo_login', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='0'),
    )
    op.create_index('ix_users_id', 'users', ['id'])
    op.create_index('ix_users_organization_id', 'users', ['organization_id'])
    op.create_index('ix_users_cedula', 'users', ['cedula'])
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_users_telegram_id', 'users', ['telegram_id'])
    op.create_index('ix_users_org_cedula', 'users', ['organization_id', 'cedula'], unique=True)
    op.create_index('ix_users_org_telegram', 'users', ['organization_id', 'telegram_id'])

    # Invoices table
    op.create_table(
        'invoices',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('numero_factura', sa.String(20), nullable=False),
        sa.Column('cliente_nombre', sa.String(200), nullable=False),
        sa.Column('cliente_telefono', sa.String(20), nullable=True),
        sa.Column('cliente_cedula', sa.String(15), nullable=True),
        sa.Column('items', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('subtotal', sa.Float(), server_default='0.0'),
        sa.Column('descuento', sa.Float(), server_default='0.0'),
        sa.Column('impuesto', sa.Float(), server_default='0.0'),
        sa.Column('total', sa.Float(), server_default='0.0'),
        sa.Column('estado', sa.String(20), server_default='BORRADOR'),
        sa.Column('vendedor_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('fecha_pago', sa.DateTime(), nullable=True),
        sa.Column('input_type', sa.String(10), nullable=True),
        sa.Column('input_raw', sa.Text(), nullable=True),
        sa.Column('n8n_processed', sa.Boolean(), server_default='0'),
        sa.Column('n8n_response', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='0'),
    )
    op.create_index('ix_invoices_id', 'invoices', ['id'])
    op.create_index('ix_invoices_organization_id', 'invoices', ['organization_id'])
    op.create_index('ix_invoices_numero_factura', 'invoices', ['numero_factura'])
    op.create_index('ix_invoices_org_numero', 'invoices', ['organization_id', 'numero_factura'], unique=True)
    op.create_index('ix_invoices_org_estado', 'invoices', ['organization_id', 'estado'])
    op.create_index('ix_invoices_org_vendedor', 'invoices', ['organization_id', 'vendedor_id'])

    # Audit logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('usuario_cedula', sa.String(15), nullable=False),
        sa.Column('accion', sa.String(100), nullable=False),
        sa.Column('entidad_tipo', sa.String(50), nullable=True),
        sa.Column('entidad_id', sa.String(100), nullable=True),
        sa.Column('detalles', sa.Text(), nullable=True),
        sa.Column('old_values', sa.Text(), nullable=True),
        sa.Column('new_values', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('invoice_id', sa.String(36), sa.ForeignKey('invoices.id', ondelete='SET NULL'), nullable=True),
    )
    op.create_index('ix_audit_logs_id', 'audit_logs', ['id'])
    op.create_index('ix_audit_logs_organization_id', 'audit_logs', ['organization_id'])
    op.create_index('ix_audit_logs_usuario_cedula', 'audit_logs', ['usuario_cedula'])
    op.create_index('ix_audit_logs_accion', 'audit_logs', ['accion'])
    op.create_index('ix_audit_logs_timestamp', 'audit_logs', ['timestamp'])
    op.create_index('ix_audit_org_timestamp', 'audit_logs', ['organization_id', 'timestamp'])
    op.create_index('ix_audit_org_accion', 'audit_logs', ['organization_id', 'accion'])


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table('audit_logs')
    op.drop_table('invoices')
    op.drop_table('users')
    op.drop_table('tenant_configs')
    op.drop_table('organizations')