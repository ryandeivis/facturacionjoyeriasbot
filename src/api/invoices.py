"""
Invoices API

Endpoints para gestión de facturas via API REST.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from src.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# SERVICE
# ============================================================================

class InvoiceAPIService:
    """Servicio para API de facturas."""

    async def list_invoices(
        self,
        org_id: str,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Lista facturas de una organización."""
        try:
            from src.database.connection import get_async_db
            from src.database.queries import get_invoices_by_org_async

            async with get_async_db() as db:
                invoices = await get_invoices_by_org_async(
                    db, org_id, estado=status, limit=limit, offset=offset
                )

                return [
                    {
                        "id": str(inv.id),
                        "numero_factura": inv.numero_factura,
                        "cliente_nombre": inv.cliente_nombre,
                        "cliente_cedula": inv.cliente_cedula,
                        "subtotal": float(inv.subtotal) if inv.subtotal else 0.0,
                        "impuesto": float(inv.impuesto) if inv.impuesto else 0.0,
                        "total": float(inv.total) if inv.total else 0.0,
                        "estado": inv.estado,
                        "created_at": inv.created_at.isoformat() + "Z" if inv.created_at else None,
                    }
                    for inv in invoices
                ]

        except Exception as e:
            logger.error(f"Error listando facturas: {e}")
            raise

    async def get_invoice(
        self,
        org_id: str,
        invoice_id: str
    ) -> Optional[Dict[str, Any]]:
        """Obtiene una factura por ID."""
        try:
            from src.database.connection import get_async_db
            from src.database.queries import get_invoice_by_id_async

            async with get_async_db() as db:
                invoice = await get_invoice_by_id_async(db, invoice_id, org_id)

                if not invoice:
                    return None

                return {
                    "id": str(invoice.id),
                    "numero_factura": invoice.numero_factura,
                    "cliente_nombre": invoice.cliente_nombre,
                    "cliente_cedula": invoice.cliente_cedula,
                    "cliente_telefono": invoice.cliente_telefono,
                    "cliente_direccion": invoice.cliente_direccion,
                    "items": invoice.items or [],
                    "subtotal": float(invoice.subtotal) if invoice.subtotal else 0.0,
                    "impuesto": float(invoice.impuesto) if invoice.impuesto else 0.0,
                    "total": float(invoice.total) if invoice.total else 0.0,
                    "estado": invoice.estado,
                    "vendedor_id": invoice.vendedor_id,
                    "descuento": float(invoice.descuento) if invoice.descuento else 0.0,
                    "created_at": invoice.created_at.isoformat() + "Z" if invoice.created_at else None,
                    "updated_at": invoice.updated_at.isoformat() + "Z" if invoice.updated_at else None,
                }

        except Exception as e:
            logger.error(f"Error obteniendo factura {invoice_id}: {e}")
            raise

    async def get_invoice_by_number(
        self,
        org_id: str,
        numero_factura: str
    ) -> Optional[Dict[str, Any]]:
        """Obtiene una factura por número."""
        try:
            from src.database.connection import get_async_db
            from src.database.queries import get_invoice_by_number_async

            async with get_async_db() as db:
                invoice = await get_invoice_by_number_async(db, numero_factura, org_id)

                if not invoice:
                    return None

                return await self.get_invoice(org_id, str(invoice.id))

        except Exception as e:
            logger.error(f"Error obteniendo factura {numero_factura}: {e}")
            raise

    async def update_invoice_status(
        self,
        org_id: str,
        invoice_id: str,
        new_status: str
    ) -> bool:
        """Actualiza el estado de una factura."""
        try:
            from src.database.connection import get_async_db
            from src.database.queries import update_invoice_status_async

            valid_statuses = ["BORRADOR", "PENDIENTE", "PAGADA", "ANULADA"]
            if new_status not in valid_statuses:
                raise ValueError(f"Estado inválido. Debe ser uno de: {valid_statuses}")

            async with get_async_db() as db:
                success = await update_invoice_status_async(
                    db, invoice_id, new_status, org_id
                )
                return success

        except Exception as e:
            logger.error(f"Error actualizando estado de factura: {e}")
            raise

    async def delete_invoice(
        self,
        org_id: str,
        invoice_id: str
    ) -> bool:
        """Elimina (soft delete) una factura."""
        try:
            from src.database.connection import get_async_db
            from src.database.queries import soft_delete_invoice_async

            async with get_async_db() as db:
                success = await soft_delete_invoice_async(db, invoice_id, org_id)
                return success

        except Exception as e:
            logger.error(f"Error eliminando factura {invoice_id}: {e}")
            raise


# Instancia global
invoice_api_service = InvoiceAPIService()


# ============================================================================
# FASTAPI ROUTER
# ============================================================================

try:
    from fastapi import APIRouter, HTTPException, Query, Header
    from pydantic import BaseModel, Field

    class InvoiceStatusUpdate(BaseModel):
        status: str = Field(..., pattern="^(BORRADOR|PENDIENTE|PAGADA|ANULADA)$")

    invoices_router = APIRouter(prefix="/invoices", tags=["invoices"])

    def get_org_id_from_header(x_org_id: str = Header(..., alias="X-Organization-ID")):
        """Extrae org_id del header."""
        return x_org_id

    @invoices_router.get("")
    async def list_invoices(
        x_org_id: str = Header(..., alias="X-Organization-ID"),
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        status: Optional[str] = Query(default=None)
    ):
        """Lista facturas de la organización."""
        return await invoice_api_service.list_invoices(
            x_org_id, limit, offset, status
        )

    @invoices_router.get("/{invoice_id}")
    async def get_invoice(
        invoice_id: str,
        x_org_id: str = Header(..., alias="X-Organization-ID")
    ):
        """Obtiene una factura por ID."""
        invoice = await invoice_api_service.get_invoice(x_org_id, invoice_id)
        if not invoice:
            raise HTTPException(status_code=404, detail="Factura no encontrada")
        return invoice

    @invoices_router.get("/by-number/{numero_factura}")
    async def get_invoice_by_number(
        numero_factura: str,
        x_org_id: str = Header(..., alias="X-Organization-ID")
    ):
        """Obtiene una factura por número."""
        invoice = await invoice_api_service.get_invoice_by_number(
            x_org_id, numero_factura
        )
        if not invoice:
            raise HTTPException(status_code=404, detail="Factura no encontrada")
        return invoice

    @invoices_router.patch("/{invoice_id}/status")
    async def update_status(
        invoice_id: str,
        request: InvoiceStatusUpdate,
        x_org_id: str = Header(..., alias="X-Organization-ID")
    ):
        """Actualiza el estado de una factura."""
        success = await invoice_api_service.update_invoice_status(
            x_org_id, invoice_id, request.status
        )
        if not success:
            raise HTTPException(status_code=404, detail="Factura no encontrada")
        return {"status": "updated", "new_status": request.status}

    @invoices_router.delete("/{invoice_id}")
    async def delete_invoice(
        invoice_id: str,
        x_org_id: str = Header(..., alias="X-Organization-ID")
    ):
        """Elimina una factura (soft delete)."""
        success = await invoice_api_service.delete_invoice(x_org_id, invoice_id)
        if not success:
            raise HTTPException(status_code=404, detail="Factura no encontrada")
        return {"status": "deleted"}

except ImportError:
    invoices_router = None