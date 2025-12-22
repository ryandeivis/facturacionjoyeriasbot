"""
Modelos de Base de Datos

Define las tablas de la base de datos usando SQLAlchemy.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Float
from sqlalchemy.types import TypeDecorator, VARCHAR
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import json

from src.database.connection import Base
from config.constants import InvoiceStatus


class JSONType(TypeDecorator):
    """Tipo JSON compatible con SQLite y PostgreSQL"""
    impl = VARCHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import JSON as PGJSON
            return dialect.type_descriptor(PGJSON())
        else:
            return dialect.type_descriptor(VARCHAR(10000))

    def process_bind_param(self, value, dialect):
        if value is not None:
            return json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            if isinstance(value, str):
                return json.loads(value)
            return value
        return value


class User(Base):
    """Modelo de Usuario"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    cedula = Column(String(15), unique=True, index=True, nullable=False)
    nombre_completo = Column(String(200), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=True)
    telefono = Column(String(20), nullable=True)
    password_hash = Column(String(255), nullable=False)
    rol = Column(String(50), nullable=False)  # ADMIN, VENDEDOR
    telegram_id = Column(Integer, unique=True, index=True, nullable=True)
    activo = Column(Boolean, default=True, nullable=False)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    ultimo_login = Column(DateTime, nullable=True)

    # Relaciones
    facturas = relationship("Invoice", back_populates="vendedor")


class Invoice(Base):
    """Modelo de Factura"""
    __tablename__ = "invoices"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    numero_factura = Column(String(20), unique=True, index=True, nullable=False)

    # Datos del cliente
    cliente_nombre = Column(String(200), nullable=False)
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

    # Fechas
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    fecha_pago = Column(DateTime, nullable=True)

    # Input original
    input_type = Column(String(10), nullable=True)  # TEXTO, VOZ, FOTO
    input_raw = Column(Text, nullable=True)  # Texto o path al archivo

    # Procesamiento n8n
    n8n_processed = Column(Boolean, default=False)
    n8n_response = Column(JSONType(), nullable=True)

    # Relaciones
    vendedor = relationship("User", back_populates="facturas")
    audit_logs = relationship("AuditLog", back_populates="invoice")


class AuditLog(Base):
    """Audit Trail"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    usuario_cedula = Column(String(15), nullable=False, index=True)
    accion = Column(String(100), nullable=False, index=True)
    entidad_tipo = Column(String(50), nullable=True)
    entidad_id = Column(String(100), nullable=True)
    detalles = Column(JSONType(), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    invoice_id = Column(String(36), ForeignKey("invoices.id"), nullable=True)
    invoice = relationship("Invoice", back_populates="audit_logs")