"""
Modelos de Base de Datos

Define las tablas de la base de datos usando SQLAlchemy.
Incluye soporte para multi-tenancy, soft deletes y timestamps.
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text,
    ForeignKey, Float, Index, CheckConstraint
)
from sqlalchemy.types import TypeDecorator, VARCHAR
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
from typing import Any, Optional, Dict, List
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
    settings: Any = Column(JSONType(), default=dict, nullable=False)

    # Contacto
    email = Column(String(255), nullable=True)
    telefono = Column(String(20), nullable=True)
    direccion = Column(String(500), nullable=True)

    # Auditoría
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)

    # Relaciones
    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="organization", cascade="all, delete-orphan")
    customers = relationship("Customer", back_populates="organization", cascade="all, delete-orphan")
    invoice_drafts = relationship("InvoiceDraft", back_populates="organization", cascade="all, delete-orphan")
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
    settings: Any = Column(JSONType(), default=dict, nullable=False)

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

    # Auditoría
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)

    # Relaciones
    organization = relationship("Organization", back_populates="users")
    facturas = relationship("Invoice", back_populates="vendedor", cascade="all, delete-orphan")
    invoice_drafts = relationship("InvoiceDraft", back_populates="user")

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

    # FK a Customer normalizado (nullable para compatibilidad)
    customer_id = Column(
        String(36),
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Datos del cliente (legacy - mantener para compatibilidad)
    cliente_nombre = Column(String(200), nullable=False)
    cliente_direccion = Column(String(300), nullable=True)
    cliente_ciudad = Column(String(100), nullable=True)
    cliente_email = Column(String(255), nullable=True)
    cliente_telefono = Column(String(20), nullable=True)
    cliente_cedula = Column(String(15), nullable=True)

    # Items (JSON array - legacy, usar items_rel para nuevas facturas)
    items: Any = Column(JSONType(), default=list, nullable=False)

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
    n8n_response: Any = Column(JSONType(), nullable=True)

    # Notas adicionales
    notas = Column(Text, nullable=True)

    # Versión para optimistic locking
    version = Column(Integer, default=1, nullable=False)

    # Auditoría
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)

    # Relaciones
    organization = relationship("Organization", back_populates="invoices")
    vendedor = relationship("User", back_populates="facturas")
    customer = relationship("Customer", back_populates="invoices")
    items_rel = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="invoice", cascade="all, delete-orphan")
    drafts = relationship("InvoiceDraft", back_populates="invoice")

    # Índice compuesto para número de factura único por organización
    __table_args__ = (
        Index('ix_invoices_org_numero', 'organization_id', 'numero_factura', unique=True),
        Index('ix_invoices_org_estado', 'organization_id', 'estado'),
        Index('ix_invoices_org_vendedor', 'organization_id', 'vendedor_id'),
        Index('ix_invoices_org_created', 'organization_id', 'created_at'),
        Index('ix_invoices_cliente_cedula', 'cliente_cedula'),
        CheckConstraint("subtotal >= 0", name="ck_invoices_subtotal_min"),
        CheckConstraint("descuento >= 0", name="ck_invoices_descuento_min"),
        CheckConstraint("impuesto >= 0", name="ck_invoices_impuesto_min"),
        CheckConstraint("total >= 0", name="ck_invoices_total_min"),
        CheckConstraint(
            "estado IN ('BORRADOR', 'PENDIENTE', 'PAGADA', 'ANULADA')",
            name="ck_invoices_estado_valid"
        ),
    )

    @property
    def items_list(self) -> List[dict]:
        """
        Retorna items de tabla normalizada o JSON legacy.

        Prioriza items_rel (normalizado) si ya fue cargado, fallback a items (JSON).
        Evita lazy loading para compatibilidad con contextos async.
        """
        # Verificar si items_rel ya fue cargado (eager loading)
        # Usamos __dict__ para evitar trigger de lazy loading en contexto async
        try:
            if 'items_rel' in self.__dict__ and self.__dict__['items_rel']:
                return [
                    {
                        'descripcion': item.descripcion,
                        'cantidad': item.cantidad,
                        'precio': item.precio_unitario,
                        'subtotal': item.subtotal,
                        'material': item.material,
                        'peso_gramos': item.peso_gramos,
                        'tipo_prenda': item.tipo_prenda,
                    }
                    for item in self.__dict__['items_rel']
                ]
        except Exception:
            pass

        # Fallback a JSON field
        return self.items or []

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
    detalles: Any = Column(JSONType(), nullable=True)
    old_values: Any = Column(JSONType(), nullable=True)
    new_values: Any = Column(JSONType(), nullable=True)

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


class MetricEvent(Base):
    """
    Evento de Métrica de Negocio.

    Almacena eventos para análisis de métricas SaaS.
    Diseñado para consultas de agregación eficientes.

    Tipos de eventos:
    - invoice.*: Eventos de facturación
    - bot.*: Interacciones con el bot
    - ai.*: Extracciones de IA
    - user.*: Eventos de usuario
    - org.*: Eventos de organización
    - api.*: Eventos de API
    """
    __tablename__ = "metric_events"

    id = Column(Integer, primary_key=True, index=True)

    # Tipo de evento (invoice.created, bot.photo, ai.extraction, etc.)
    event_type = Column(String(50), nullable=False, index=True)

    # Multi-tenancy (opcional para métricas globales)
    organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )

    # Usuario que generó el evento
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Valor numérico (ej: monto de factura, items extraídos)
    value = Column(Float, default=0.0, nullable=False)

    # Resultado de la operación
    success = Column(Boolean, default=True, nullable=False)

    # Duración en milisegundos
    duration_ms = Column(Float, nullable=True)

    # Metadata adicional (JSON) - Nota: 'metadata' es reservado en SQLAlchemy
    event_metadata: Any = Column(JSONType(), default=dict, nullable=False)

    # Timestamp con índice para queries temporales
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Índices compuestos para consultas frecuentes
    __table_args__ = (
        # Por org y tipo de evento (métricas por tenant)
        Index('ix_metrics_org_type', 'organization_id', 'event_type'),
        # Por org y fecha (series temporales)
        Index('ix_metrics_org_date', 'organization_id', 'created_at'),
        # Por tipo y fecha (agregaciones globales)
        Index('ix_metrics_type_date', 'event_type', 'created_at'),
        # Por org, tipo y fecha (consultas completas)
        Index('ix_metrics_org_type_date', 'organization_id', 'event_type', 'created_at'),
    )

    def __repr__(self):
        return f"<MetricEvent {self.event_type} org={self.organization_id}>"

    def to_dict(self) -> dict:
        """Serializa el evento a diccionario."""
        return {
            "id": self.id,
            "event_type": self.event_type,
            "organization_id": self.organization_id,
            "user_id": self.user_id,
            "value": self.value,
            "success": self.success,
            "duration_ms": self.duration_ms,
            "metadata": self.event_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ============================================================================
# MODELOS DE NORMALIZACIÓN Y TRAZABILIDAD
# ============================================================================


class Customer(Base, TimestampMixin, SoftDeleteMixin):
    """
    Modelo de Cliente normalizado.

    Centraliza los datos de clientes que antes estaban desnormalizados
    en cada factura. Permite tracking de clientes recurrentes y análisis.
    """
    __tablename__ = "customers"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)

    # Multi-tenancy
    organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Datos del cliente
    nombre = Column(String(200), nullable=False)
    cedula = Column(String(15), nullable=True, index=True)
    telefono = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    direccion = Column(String(300), nullable=True)
    ciudad = Column(String(100), nullable=True)
    notas = Column(Text, nullable=True)

    # Auditoría
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)

    # Relaciones
    organization = relationship("Organization", back_populates="customers")
    invoices = relationship("Invoice", back_populates="customer")

    # Índices compuestos
    __table_args__ = (
        Index('ix_customers_org_cedula', 'organization_id', 'cedula'),
        Index('ix_customers_org_nombre', 'organization_id', 'nombre'),
        Index('ix_customers_org_email', 'organization_id', 'email'),
    )

    def __repr__(self):
        return f"<Customer {self.nombre} ({self.cedula})>"

    def to_dict(self) -> dict:
        """Serializa el cliente a diccionario."""
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "nombre": self.nombre,
            "cedula": self.cedula,
            "telefono": self.telefono,
            "email": self.email,
            "direccion": self.direccion,
            "ciudad": self.ciudad,
            "notas": self.notas,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class InvoiceItem(Base, TimestampMixin):
    """
    Modelo de Item de Factura normalizado.

    Separa los items del campo JSON en Invoice para permitir:
    - Queries SQL sobre items individuales
    - Reportes de productos más vendidos
    - Análisis de ventas por categoría/material
    """
    __tablename__ = "invoice_items"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # FK a factura
    invoice_id = Column(
        String(36),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Datos del item
    numero = Column(Integer, nullable=False, default=1)  # Orden en la factura
    descripcion = Column(String(200), nullable=False)
    cantidad = Column(Integer, nullable=False, default=1)
    precio_unitario = Column(Float, nullable=False)
    subtotal = Column(Float, nullable=False)

    # Metadata joyería (opcional)
    material = Column(String(50), nullable=True)  # oro_18k, plata_925, etc.
    peso_gramos = Column(Float, nullable=True)
    tipo_prenda = Column(String(50), nullable=True)  # anillo, cadena, arete, etc.

    # Relación
    invoice = relationship("Invoice", back_populates="items_rel")

    # Constraints e índices
    __table_args__ = (
        Index('ix_invoice_items_invoice', 'invoice_id'),
        Index('ix_invoice_items_descripcion', 'descripcion'),
        Index('ix_invoice_items_material', 'material'),
        Index('ix_invoice_items_tipo_prenda', 'tipo_prenda'),
        CheckConstraint("cantidad >= 1", name="ck_invoice_items_cantidad_min"),
        CheckConstraint("precio_unitario >= 0", name="ck_invoice_items_precio_min"),
        CheckConstraint("subtotal >= 0", name="ck_invoice_items_subtotal_min"),
    )

    def __repr__(self):
        return f"<InvoiceItem {self.descripcion} x{self.cantidad}>"

    def to_dict(self) -> dict:
        """Serializa el item a diccionario."""
        return {
            "id": self.id,
            "invoice_id": self.invoice_id,
            "numero": self.numero,
            "descripcion": self.descripcion,
            "cantidad": self.cantidad,
            "precio_unitario": self.precio_unitario,
            "subtotal": self.subtotal,
            "material": self.material,
            "peso_gramos": self.peso_gramos,
            "tipo_prenda": self.tipo_prenda,
        }


class InvoiceDraft(Base, TimestampMixin):
    """
    Modelo de Borrador de Factura con trazabilidad.

    Almacena el estado de una factura en proceso de creación,
    permitiendo trazabilidad completa de:
    - Input original del usuario
    - Datos extraídos por IA
    - Modificaciones del usuario
    - Historial de cambios
    """
    __tablename__ = "invoice_drafts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)

    # Multi-tenancy
    organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Usuario que crea el borrador
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Chat de Telegram (para recuperar borradores)
    telegram_chat_id = Column(Integer, nullable=False, index=True)

    # Estado del flujo de conversación
    current_step = Column(String(50), nullable=False, default="SELECCIONAR_INPUT")

    # Input original (para trazabilidad)
    input_type = Column(String(10), nullable=True)  # TEXTO, VOZ, FOTO
    input_raw = Column(Text, nullable=True)
    input_file_path = Column(String(500), nullable=True)

    # Datos extraídos por IA (snapshot original)
    ai_response_raw: Any = Column(JSONType(), nullable=True)
    ai_extraction_timestamp = Column(DateTime, nullable=True)

    # Datos actuales (pueden ser modificados por usuario)
    items_data: Any = Column(JSONType(), default=list, nullable=False)
    customer_data: Any = Column(JSONType(), default=dict, nullable=False)
    totals_data: Any = Column(JSONType(), default=dict, nullable=False)

    # Historial de cambios [{timestamp, field, old_value, new_value, source}]
    change_history: Any = Column(JSONType(), default=list, nullable=False)

    # Estado del borrador
    status = Column(String(20), default="active", nullable=False)  # active, completed, cancelled, expired

    # Expiración (borradores abandonados)
    expires_at = Column(DateTime, nullable=True)

    # FK a factura final (si se completó)
    invoice_id = Column(
        String(36),
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True
    )

    # Relaciones
    organization = relationship("Organization", back_populates="invoice_drafts")
    user = relationship("User", back_populates="invoice_drafts")
    invoice = relationship("Invoice", back_populates="drafts")

    # Índices
    __table_args__ = (
        Index('ix_drafts_org_user', 'organization_id', 'user_id'),
        Index('ix_drafts_chat', 'telegram_chat_id'),
        Index('ix_drafts_status', 'status'),
        Index('ix_drafts_org_status', 'organization_id', 'status'),
    )

    def __repr__(self):
        return f"<InvoiceDraft {self.id[:8]} step={self.current_step} status={self.status}>"

    def add_change(self, field: str, old_value: Any, new_value: Any, source: str = "user") -> None:
        """
        Agrega un cambio al historial con mutation tracking.

        SQLAlchemy no detecta cambios in-place en columnas JSON, por lo que
        creamos una nueva lista y usamos flag_modified() para notificar.

        Args:
            field: Nombre del campo modificado (ej: "items[0].precio")
            old_value: Valor anterior
            new_value: Valor nuevo
            source: Origen del cambio ("user", "ai", "system")
        """
        from sqlalchemy.orm.attributes import flag_modified

        change = {
            "timestamp": datetime.utcnow().isoformat(),
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
            "source": source,
        }

        # Crear nueva lista para forzar detección de cambio por SQLAlchemy
        if self.change_history is None:
            self.change_history = []

        new_history = list(self.change_history)
        new_history.append(change)
        self.change_history = new_history

        # Marcar explícitamente como modificado para SQLAlchemy
        flag_modified(self, "change_history")

    def to_dict(self) -> dict:
        """Serializa el borrador a diccionario."""
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "user_id": self.user_id,
            "telegram_chat_id": self.telegram_chat_id,
            "current_step": self.current_step,
            "input_type": self.input_type,
            "input_raw": self.input_raw,
            "ai_response_raw": self.ai_response_raw,
            "items_data": self.items_data,
            "customer_data": self.customer_data,
            "totals_data": self.totals_data,
            "change_history": self.change_history,
            "status": self.status,
            "invoice_id": self.invoice_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }