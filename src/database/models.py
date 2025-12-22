"""
Modelos de Base de Datos

Define las tablas de la base de datos usando SQLAlchemy.
Incluye soporte para multi-tenancy, soft deletes y timestamps.
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text,
    ForeignKey, Float, Index
)
from sqlalchemy.types import TypeDecorator, VARCHAR
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import json

from src.database.connection import Base
from src.database.mixins import SoftDeleteMixin, TimestampMixin
from config.constants import InvoiceStatus


class JSONType(TypeDecorator):
    """Tipo JSON compatible con SQLite y PostgreSQL"""
    impl = VARCHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import JSONB
            return dialect.type_descriptor(JSONB())
        else:
            return dialect.type_descriptor(VARCHAR(10000))

    def process_bind_param(self, value, dialect):
        if value is not None:
            if dialect.name != 'postgresql':
                return json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            if isinstance(value, str):
                return json.loads(value)
        return value


class Organization(Base, TimestampMixin, SoftDeleteMixin):
    """
    Modelo de Organización (Tenant).

    Representa una empresa/joyería que usa el sistema.
    Todos los datos están aislados por organization_id.
    """
    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(50), unique=True, index=True, nullable=False)

    # Plan y estado
    plan = Column(String(20), default="basic", nullable=False)  # basic, pro, enterprise
    status = Column(String(20), default="active", nullable=False)  # active, suspended, cancelled

    # Configuración
    settings = Column(JSONType(), default=dict, nullable=False)

    # Contacto
    email = Column(String(255), nullable=True)
    telefono = Column(String(20), nullable=True)
    direccion = Column(String(500), nullable=True)

    # Relaciones
    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="organization", cascade="all, delete-orphan")
    configs = relationship("TenantConfig", back_populates="organization", uselist=False)

    def __repr__(self):
        return f"<Organization {self.name}>"


class TenantConfig(Base):
    """
    Configuración específica del tenant.

    Permite personalizar el comportamiento por organización.
    """
    __tablename__ = "tenant_configs"

    organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        primary_key=True
    )

    # Configuración de facturas
    invoice_prefix = Column(String(10), default="FAC", nullable=False)
    tax_rate = Column(Float, default=0.19, nullable=False)
    currency = Column(String(3), default="COP", nullable=False)

    # Configuración adicional
    settings = Column(JSONType(), default=dict, nullable=False)

    # Relación
    organization = relationship("Organization", back_populates="configs")

    def __repr__(self):
        return f"<TenantConfig {self.organization_id}>"


class User(Base, TimestampMixin, SoftDeleteMixin):
    """Modelo de Usuario con soporte multi-tenant"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    # Multi-tenancy
    organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Datos de usuario
    cedula = Column(String(15), nullable=False, index=True)
    nombre_completo = Column(String(200), nullable=False)
    email = Column(String(255), index=True, nullable=True)
    telefono = Column(String(20), nullable=True)
    password_hash = Column(String(255), nullable=False)
    rol = Column(String(50), nullable=False)  # ADMIN, VENDEDOR
    telegram_id = Column(Integer, index=True, nullable=True)
    activo = Column(Boolean, default=True, nullable=False)
    ultimo_login = Column(DateTime, nullable=True)

    # Relaciones
    organization = relationship("Organization", back_populates="users")
    facturas = relationship("Invoice", back_populates="vendedor", cascade="all, delete-orphan")

    # Índice compuesto para búsqueda por cédula dentro de una organización
    __table_args__ = (
        Index('ix_users_org_cedula', 'organization_id', 'cedula', unique=True),
        Index('ix_users_org_telegram', 'organization_id', 'telegram_id'),
    )

    def __repr__(self):
        return f"<User {self.cedula}>"


class Invoice(Base, TimestampMixin, SoftDeleteMixin):
    """Modelo de Factura con soporte multi-tenant"""
    __tablename__ = "invoices"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)

    # Multi-tenancy
    organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    numero_factura = Column(String(20), nullable=False, index=True)

    # Datos del cliente
    cliente_nombre = Column(String(200), nullable=False)
    cliente_direccion = Column(String(300), nullable=True)
    cliente_ciudad = Column(String(100), nullable=True)
    cliente_email = Column(String(255), nullable=True)
    cliente_telefono = Column(String(20), nullable=True)
    cliente_cedula = Column(String(15), nullable=True)

    # Items (JSON array)
    items = Column(JSONType(), default=list, nullable=False)

    # Totales
    subtotal = Column(Float, default=0.0)
    descuento = Column(Float, default=0.0)
    impuesto = Column(Float, default=0.0)
    total = Column(Float, default=0.0)

    # Estado
    estado = Column(String(20), default=InvoiceStatus.BORRADOR.value)

    # Vendedor
    vendedor_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Fecha de pago
    fecha_pago = Column(DateTime, nullable=True)

    # Input original
    input_type = Column(String(10), nullable=True)  # TEXTO, VOZ, FOTO
    input_raw = Column(Text, nullable=True)  # Texto o path al archivo

    # Procesamiento n8n
    n8n_processed = Column(Boolean, default=False)
    n8n_response = Column(JSONType(), nullable=True)

    # Relaciones
    organization = relationship("Organization", back_populates="invoices")
    vendedor = relationship("User", back_populates="facturas")
    audit_logs = relationship("AuditLog", back_populates="invoice", cascade="all, delete-orphan")

    # Índice compuesto para número de factura único por organización
    __table_args__ = (
        Index('ix_invoices_org_numero', 'organization_id', 'numero_factura', unique=True),
        Index('ix_invoices_org_estado', 'organization_id', 'estado'),
        Index('ix_invoices_org_vendedor', 'organization_id', 'vendedor_id'),
    )

    def __repr__(self):
        return f"<Invoice {self.numero_factura}>"


class AuditLog(Base):
    """
    Audit Trail con soporte multi-tenant.

    Registra todas las acciones importantes del sistema.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)

    # Multi-tenancy
    organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Usuario que realizó la acción
    usuario_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    usuario_cedula = Column(String(15), nullable=False, index=True)

    # Acción
    accion = Column(String(100), nullable=False, index=True)

    # Entidad afectada
    entidad_tipo = Column(String(50), nullable=True)
    entidad_id = Column(String(100), nullable=True)

    # Detalles del cambio
    detalles = Column(JSONType(), nullable=True)
    old_values = Column(JSONType(), nullable=True)
    new_values = Column(JSONType(), nullable=True)

    # Metadata
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # Referencia opcional a factura
    invoice_id = Column(String(36), ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True)

    # Relaciones
    invoice = relationship("Invoice", back_populates="audit_logs")

    # Índices
    __table_args__ = (
        Index('ix_audit_org_timestamp', 'organization_id', 'timestamp'),
        Index('ix_audit_org_accion', 'organization_id', 'accion'),
    )

    def __repr__(self):
        return f"<AuditLog {self.accion} by {self.usuario_cedula}>"