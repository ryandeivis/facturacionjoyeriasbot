"""
API Schemas

Schemas Pydantic documentados para la API REST.
Proporciona validación y documentación automática para OpenAPI/Swagger.

Uso:
    from src.api.schemas import InvoiceResponse, OrganizationCreate
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# ENUMS
# ============================================================================

class InvoiceStatus(str, Enum):
    """Estados posibles de una factura."""
    BORRADOR = "BORRADOR"
    PENDIENTE = "PENDIENTE"
    PAGADA = "PAGADA"
    ANULADA = "ANULADA"


class PlanType(str, Enum):
    """Tipos de plan disponibles."""
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class UserRole(str, Enum):
    """Roles de usuario en el sistema."""
    ADMIN = "ADMIN"
    VENDEDOR = "VENDEDOR"
    CONTADOR = "CONTADOR"


# ============================================================================
# BASE SCHEMAS
# ============================================================================

class BaseSchema(BaseModel):
    """Schema base con configuración común."""
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"example": {}}
    )


class TimestampMixin(BaseModel):
    """Mixin para campos de timestamp."""
    created_at: Optional[datetime] = Field(
        None,
        description="Fecha de creación (UTC)"
    )
    updated_at: Optional[datetime] = Field(
        None,
        description="Fecha de última actualización (UTC)"
    )


class PaginationParams(BaseModel):
    """Parámetros de paginación."""
    limit: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Número máximo de resultados"
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Número de resultados a saltar"
    )


# ============================================================================
# ERROR SCHEMAS
# ============================================================================

class ErrorResponse(BaseSchema):
    """Respuesta de error estándar."""
    error: str = Field(..., description="Tipo de error")
    message: str = Field(..., description="Mensaje descriptivo del error")
    status_code: int = Field(..., description="Código HTTP del error")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Momento del error"
    )
    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Detalles adicionales del error"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "ValidationError",
                "message": "El campo 'nombre' es requerido",
                "status_code": 400,
                "timestamp": "2024-01-15T10:30:00Z",
                "details": {"field": "nombre", "type": "missing"}
            }
        }
    )


class ValidationErrorDetail(BaseSchema):
    """Detalle de error de validación."""
    loc: List[str] = Field(..., description="Ubicación del error")
    msg: str = Field(..., description="Mensaje de error")
    type: str = Field(..., description="Tipo de error")


class ValidationErrorResponse(BaseSchema):
    """Respuesta de error de validación."""
    detail: List[ValidationErrorDetail] = Field(
        ...,
        description="Lista de errores de validación"
    )


# ============================================================================
# INVOICE ITEM SCHEMAS
# ============================================================================

class InvoiceItemBase(BaseSchema):
    """Datos base de un item de factura."""
    descripcion: str = Field(
        ...,
        min_length=2,
        max_length=200,
        description="Descripción del producto/servicio"
    )
    cantidad: int = Field(
        ...,
        ge=1,
        le=9999,
        description="Cantidad del item"
    )
    precio_unitario: float = Field(
        ...,
        ge=0,
        description="Precio unitario en COP"
    )


class InvoiceItemCreate(InvoiceItemBase):
    """Datos para crear un item de factura."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "descripcion": "Anillo Oro 18K",
                "cantidad": 1,
                "precio_unitario": 500000.0
            }
        }
    )


class InvoiceItemResponse(InvoiceItemBase):
    """Respuesta con datos de item de factura."""
    subtotal: float = Field(..., description="Subtotal del item (cantidad * precio)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "descripcion": "Anillo Oro 18K",
                "cantidad": 1,
                "precio_unitario": 500000.0,
                "subtotal": 500000.0
            }
        }
    )


# ============================================================================
# INVOICE SCHEMAS
# ============================================================================

class InvoiceBase(BaseSchema):
    """Datos base de una factura."""
    cliente_nombre: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Nombre completo del cliente"
    )
    cliente_cedula: Optional[str] = Field(
        None,
        min_length=6,
        max_length=12,
        description="Número de cédula del cliente"
    )
    cliente_telefono: Optional[str] = Field(
        None,
        max_length=20,
        description="Teléfono del cliente"
    )
    cliente_direccion: Optional[str] = Field(
        None,
        max_length=200,
        description="Dirección del cliente"
    )
    cliente_email: Optional[str] = Field(
        None,
        max_length=254,
        description="Email del cliente"
    )
    notas: Optional[str] = Field(
        None,
        max_length=500,
        description="Notas adicionales de la factura"
    )


class InvoiceCreate(InvoiceBase):
    """Datos para crear una factura."""
    items: List[InvoiceItemCreate] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Lista de items de la factura"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cliente_nombre": "Juan Pérez",
                "cliente_cedula": "12345678",
                "cliente_telefono": "3001234567",
                "items": [
                    {
                        "descripcion": "Anillo Oro 18K",
                        "cantidad": 1,
                        "precio_unitario": 500000.0
                    },
                    {
                        "descripcion": "Cadena Plata",
                        "cantidad": 2,
                        "precio_unitario": 150000.0
                    }
                ],
                "notas": "Cliente frecuente"
            }
        }
    )


class InvoiceUpdate(BaseSchema):
    """Datos para actualizar una factura."""
    cliente_nombre: Optional[str] = Field(
        None,
        min_length=3,
        max_length=100
    )
    cliente_telefono: Optional[str] = Field(None, max_length=20)
    cliente_direccion: Optional[str] = Field(None, max_length=200)
    notas: Optional[str] = Field(None, max_length=500)


class InvoiceStatusUpdate(BaseSchema):
    """Datos para actualizar estado de factura."""
    status: InvoiceStatus = Field(
        ...,
        description="Nuevo estado de la factura"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"status": "PAGADA"}
        }
    )


class InvoiceListItem(BaseSchema):
    """Factura en lista (resumen)."""
    id: str = Field(..., description="ID único de la factura")
    numero_factura: str = Field(..., description="Número de factura")
    cliente_nombre: str = Field(..., description="Nombre del cliente")
    cliente_cedula: Optional[str] = Field(None, description="Cédula del cliente")
    subtotal: float = Field(..., description="Subtotal antes de impuestos")
    impuestos: float = Field(..., description="Total de impuestos")
    total: float = Field(..., description="Total de la factura")
    estado: InvoiceStatus = Field(..., description="Estado de la factura")
    created_at: Optional[datetime] = Field(None, description="Fecha de creación")


class InvoiceResponse(InvoiceBase, TimestampMixin):
    """Respuesta completa de factura."""
    id: str = Field(..., description="ID único de la factura")
    numero_factura: str = Field(..., description="Número de factura")
    organization_id: str = Field(..., description="ID de la organización")
    items: List[InvoiceItemResponse] = Field(
        ...,
        description="Items de la factura"
    )
    subtotal: float = Field(..., description="Subtotal antes de impuestos")
    descuento: float = Field(default=0, description="Descuento aplicado")
    impuestos: float = Field(..., description="Total de impuestos (IVA)")
    total: float = Field(..., description="Total de la factura")
    estado: InvoiceStatus = Field(..., description="Estado de la factura")
    vendedor_id: Optional[int] = Field(None, description="ID del vendedor")
    vendedor_nombre: Optional[str] = Field(None, description="Nombre del vendedor")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "inv-123-abc",
                "numero_factura": "FAC-202401-0001",
                "organization_id": "org-xyz",
                "cliente_nombre": "Juan Pérez",
                "cliente_cedula": "12345678",
                "cliente_telefono": "3001234567",
                "items": [
                    {
                        "descripcion": "Anillo Oro 18K",
                        "cantidad": 1,
                        "precio_unitario": 500000.0,
                        "subtotal": 500000.0
                    }
                ],
                "subtotal": 500000.0,
                "descuento": 0,
                "impuestos": 95000.0,
                "total": 595000.0,
                "estado": "PENDIENTE",
                "created_at": "2024-01-15T10:30:00Z"
            }
        }
    )


class InvoiceListResponse(BaseSchema):
    """Respuesta de lista de facturas."""
    items: List[InvoiceListItem] = Field(..., description="Lista de facturas")
    total: int = Field(..., description="Total de facturas")
    limit: int = Field(..., description="Límite de la consulta")
    offset: int = Field(..., description="Offset de la consulta")


# ============================================================================
# ORGANIZATION SCHEMAS
# ============================================================================

class OrganizationBase(BaseSchema):
    """Datos base de una organización."""
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Nombre de la organización"
    )
    invoice_prefix: str = Field(
        default="FAC",
        max_length=10,
        description="Prefijo para números de factura"
    )


class OrganizationCreate(OrganizationBase):
    """Datos para crear una organización."""
    plan: PlanType = Field(
        default=PlanType.BASIC,
        description="Plan de suscripción"
    )
    owner_email: Optional[str] = Field(
        None,
        description="Email del propietario"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Joyería El Diamante",
                "plan": "basic",
                "invoice_prefix": "JOY",
                "owner_email": "admin@joyeria.com"
            }
        }
    )


class OrganizationUpdate(BaseSchema):
    """Datos para actualizar una organización."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    plan: Optional[PlanType] = None
    invoice_prefix: Optional[str] = Field(None, max_length=10)
    is_active: Optional[bool] = Field(None, description="Estado activo/inactivo")


class PlanFeatures(BaseSchema):
    """Características del plan."""
    ai_extraction: bool = Field(..., description="Extracción con IA")
    voice_input: bool = Field(..., description="Entrada por voz")
    photo_input: bool = Field(..., description="Entrada por foto")
    custom_templates: bool = Field(..., description="Plantillas personalizadas")
    api_access: bool = Field(..., description="Acceso a API")
    priority_support: bool = Field(default=False, description="Soporte prioritario")


class PlanLimits(BaseSchema):
    """Límites del plan."""
    invoices_per_month: int = Field(..., description="Facturas por mes")
    users_per_org: int = Field(..., description="Usuarios por organización")
    max_items_per_invoice: int = Field(..., description="Items por factura")
    features: PlanFeatures = Field(..., description="Características incluidas")


class OrganizationResponse(OrganizationBase, TimestampMixin):
    """Respuesta completa de organización."""
    id: str = Field(..., description="ID único de la organización")
    plan: PlanType = Field(..., description="Plan actual")
    is_active: bool = Field(..., description="Estado activo")
    users_count: int = Field(..., description="Número de usuarios")
    invoices_count: int = Field(..., description="Número de facturas")
    plan_limits: Optional[PlanLimits] = Field(
        None,
        description="Límites del plan actual"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "org-xyz-123",
                "name": "Joyería El Diamante",
                "plan": "pro",
                "invoice_prefix": "JOY",
                "is_active": True,
                "users_count": 5,
                "invoices_count": 150,
                "created_at": "2024-01-01T00:00:00Z",
                "plan_limits": {
                    "invoices_per_month": 500,
                    "users_per_org": 10,
                    "max_items_per_invoice": 100,
                    "features": {
                        "ai_extraction": True,
                        "voice_input": True,
                        "photo_input": True,
                        "custom_templates": True,
                        "api_access": True
                    }
                }
            }
        }
    )


class OrganizationListResponse(BaseSchema):
    """Respuesta de lista de organizaciones."""
    items: List[OrganizationResponse] = Field(
        ...,
        description="Lista de organizaciones"
    )
    total: int = Field(..., description="Total de organizaciones")


class OrganizationStats(BaseSchema):
    """Estadísticas de una organización."""
    organization_id: str = Field(..., description="ID de la organización")
    total_invoices: int = Field(..., description="Total de facturas")
    invoices_this_month: int = Field(..., description="Facturas este mes")
    total_revenue: float = Field(..., description="Ingresos totales")
    revenue_this_month: float = Field(..., description="Ingresos este mes")
    pending_invoices: int = Field(..., description="Facturas pendientes")
    pending_amount: float = Field(..., description="Monto pendiente")
    top_products: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Productos más vendidos"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Momento de la consulta"
    )


# ============================================================================
# USER SCHEMAS
# ============================================================================

class UserBase(BaseSchema):
    """Datos base de usuario."""
    cedula: str = Field(
        ...,
        min_length=6,
        max_length=12,
        description="Número de cédula"
    )
    nombre_completo: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Nombre completo"
    )
    email: Optional[str] = Field(None, description="Email")
    telefono: Optional[str] = Field(None, description="Teléfono")
    rol: UserRole = Field(default=UserRole.VENDEDOR, description="Rol del usuario")


class UserCreate(UserBase):
    """Datos para crear usuario."""
    password: str = Field(
        ...,
        min_length=8,
        description="Contraseña (mínimo 8 caracteres)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cedula": "12345678",
                "nombre_completo": "María García",
                "email": "maria@joyeria.com",
                "rol": "VENDEDOR",
                "password": "SecurePass123!"
            }
        }
    )


class UserResponse(UserBase, TimestampMixin):
    """Respuesta de usuario."""
    id: int = Field(..., description="ID del usuario")
    organization_id: str = Field(..., description="ID de la organización")
    activo: bool = Field(..., description="Usuario activo")
    telegram_id: Optional[int] = Field(None, description="ID de Telegram")
    last_login: Optional[datetime] = Field(None, description="Último login")


# ============================================================================
# HEALTH SCHEMAS
# ============================================================================

class ComponentHealthResponse(BaseSchema):
    """Estado de salud de un componente."""
    name: str = Field(..., description="Nombre del componente")
    status: str = Field(..., description="Estado (healthy, degraded, unhealthy)")
    message: str = Field(default="", description="Mensaje adicional")
    latency_ms: float = Field(default=0, description="Latencia en ms")
    checked_at: datetime = Field(..., description="Momento del check")


class HealthResponse(BaseSchema):
    """Respuesta de health check del sistema."""
    status: str = Field(..., description="Estado general del sistema")
    version: str = Field(..., description="Versión de la aplicación")
    uptime_seconds: float = Field(..., description="Tiempo de actividad")
    components: List[ComponentHealthResponse] = Field(
        ...,
        description="Estado de cada componente"
    )
    checked_at: datetime = Field(..., description="Momento del check")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "uptime_seconds": 86400.5,
                "components": [
                    {
                        "name": "database",
                        "status": "healthy",
                        "latency_ms": 5.2,
                        "checked_at": "2024-01-15T10:30:00Z"
                    },
                    {
                        "name": "n8n",
                        "status": "healthy",
                        "latency_ms": 120.5,
                        "checked_at": "2024-01-15T10:30:00Z"
                    }
                ],
                "checked_at": "2024-01-15T10:30:00Z"
            }
        }
    )


# ============================================================================
# METRICS SCHEMAS
# ============================================================================

class MetricValue(BaseSchema):
    """Valor de una métrica."""
    name: str = Field(..., description="Nombre de la métrica")
    value: float = Field(..., description="Valor actual")
    labels: Dict[str, str] = Field(
        default_factory=dict,
        description="Labels de la métrica"
    )


class MetricsResponse(BaseSchema):
    """Respuesta de métricas."""
    metrics: List[MetricValue] = Field(..., description="Lista de métricas")
    timestamp: datetime = Field(..., description="Momento de la consulta")


# ============================================================================
# API INFO SCHEMAS
# ============================================================================

class APIInfo(BaseSchema):
    """Información de la API."""
    name: str = Field(..., description="Nombre de la API")
    version: str = Field(..., description="Versión de la API")
    status: str = Field(..., description="Estado de la API")
    docs_url: Optional[str] = Field(None, description="URL de documentación")
    endpoints: Dict[str, str] = Field(..., description="Endpoints disponibles")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Jewelry Invoice Bot API",
                "version": "1.0.0",
                "status": "running",
                "docs_url": "/docs",
                "endpoints": {
                    "health": "/health",
                    "metrics": "/metrics",
                    "organizations": "/api/v1/organizations",
                    "invoices": "/api/v1/invoices"
                }
            }
        }
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Enums
    "InvoiceStatus",
    "PlanType",
    "UserRole",
    # Base
    "BaseSchema",
    "TimestampMixin",
    "PaginationParams",
    # Errors
    "ErrorResponse",
    "ValidationErrorResponse",
    # Invoice
    "InvoiceItemCreate",
    "InvoiceItemResponse",
    "InvoiceCreate",
    "InvoiceUpdate",
    "InvoiceStatusUpdate",
    "InvoiceListItem",
    "InvoiceResponse",
    "InvoiceListResponse",
    # Organization
    "OrganizationCreate",
    "OrganizationUpdate",
    "OrganizationResponse",
    "OrganizationListResponse",
    "OrganizationStats",
    "PlanFeatures",
    "PlanLimits",
    # User
    "UserCreate",
    "UserResponse",
    # Health
    "HealthResponse",
    "ComponentHealthResponse",
    # Metrics
    "MetricsResponse",
    # API
    "APIInfo",
]
