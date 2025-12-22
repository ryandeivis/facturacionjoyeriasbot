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


class N8NClienteInfo(BaseModel):
    """Información del cliente extraída por n8n"""
    nombre: Optional[str] = None
    direccion: Optional[str] = None
    ciudad: Optional[str] = None
    pais: str = "Colombia"
    email: Optional[str] = None
    telefono: Optional[str] = None


class N8NItemInfo(BaseModel):
    """Item extraído por n8n"""
    numero: int = 1
    nombre: str
    descripcion: str = ""
    cantidad: int = 1
    precio: float = 0.0
    total: float = 0.0


class N8NTotales(BaseModel):
    """Totales calculados por n8n"""
    subtotal: float = 0.0
    descuento: float = 0.0
    impuesto: float = 0.0
    total: float = 0.0


class N8NFacturaInfo(BaseModel):
    """Información de factura generada por n8n"""
    numero: Optional[str] = None
    fecha_emision: Optional[str] = None
    fecha_vencimiento: Optional[str] = None


class N8NResponse(BaseModel):
    """Respuesta completa de n8n para extracción de datos"""
    success: bool = False
    items: List[dict] = []
    cliente: Optional[dict] = None
    totales: Optional[dict] = None
    factura: Optional[dict] = None
    transcripcion: Optional[str] = None
    input_type: Optional[str] = None
    notas: Optional[str] = None
    confianza: float = 0.0
    error: Optional[str] = None


class N8NPDFRequest(BaseModel):
    """Datos para solicitar generación de PDF a n8n"""
    organization_id: str
    invoice_id: str
    numero_factura: str
    cliente: dict
    items: List[dict]
    totales: dict
    vendedor: dict
    notas: Optional[str] = None


class N8NPDFResponse(BaseModel):
    """Respuesta de n8n al generar PDF"""
    success: bool = False
    pdf_url: Optional[str] = None
    pdf_base64: Optional[str] = None
    error: Optional[str] = None