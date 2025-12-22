"""
Modelos Pydantic de Factura

Schemas para validación de datos de factura.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import datetime

from config.constants import InvoiceStatus, InputType, MaterialType, JewelryType


class InvoiceItem(BaseModel):
    """Item de factura"""
    descripcion: str
    cantidad: int = 1
    precio: float = Field(..., ge=0)
    material: Optional[str] = None
    peso_gramos: Optional[float] = None
    tipo_prenda: Optional[str] = None

    @property
    def subtotal(self) -> float:
        return self.cantidad * self.precio


class ClienteInfo(BaseModel):
    """Información del cliente"""
    nombre: str
    telefono: Optional[str] = None
    cedula: Optional[str] = None


class InvoiceCreate(BaseModel):
    """Datos para crear factura"""
    cliente_nombre: str
    cliente_telefono: Optional[str] = None
    cliente_cedula: Optional[str] = None
    items: List[InvoiceItem]
    descuento: float = 0.0
    impuesto: float = 0.0
    input_type: Optional[str] = None
    input_raw: Optional[str] = None


class InvoiceResponse(BaseModel):
    """Factura completa"""
    id: str
    numero_factura: str
    cliente_nombre: str
    cliente_telefono: Optional[str]
    cliente_cedula: Optional[str]
    items: List[dict]
    subtotal: float
    descuento: float
    impuesto: float
    total: float
    estado: str
    fecha_creacion: datetime
    vendedor_nombre: Optional[str] = None

    class Config:
        from_attributes = True


class N8NResponse(BaseModel):
    """Respuesta esperada de n8n"""
    success: bool = False
    items: List[dict] = []
    transcripcion: Optional[str] = None
    confianza: float = 0.0
    error: Optional[str] = None