"""
Metrics Tracker

Interface simplificada para trackear eventos desde cualquier parte del código.
Proporciona métodos convenientes para los eventos más comunes.
"""

import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from functools import wraps
from contextlib import asynccontextmanager

from src.utils.logger import get_logger
from src.metrics.collectors import (
    MetricsCollector,
    get_metrics_collector,
    EventType,
)

logger = get_logger(__name__)


class MetricsTracker:
    """
    Tracker de métricas con API simplificada.

    Uso:
        tracker = get_metrics_tracker()

        # Trackear factura creada
        await tracker.track_invoice_created(org_id, amount=500000)

        # Trackear con contexto
        async with tracker.track_operation("ai_extraction", org_id):
            result = await extract_data(image)
    """

    def __init__(self, collector: Optional[MetricsCollector] = None):
        self._collector = collector or get_metrics_collector()
        logger.info("MetricsTracker inicializado")

    # =========================================================================
    # FACTURAS
    # =========================================================================

    async def track_invoice_created(
        self,
        organization_id: str,
        amount: float,
        user_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Trackea la creación de una factura."""
        await self._collector.collect(
            event_type=EventType.INVOICE_CREATED,
            organization_id=organization_id,
            user_id=user_id,
            value=amount,
            metadata={**(metadata or {}), "amount": amount},
        )

    async def track_invoice_paid(
        self,
        organization_id: str,
        amount: float,
        invoice_id: Optional[str] = None,
        time_to_payment_hours: Optional[float] = None,
    ):
        """Trackea el pago de una factura."""
        await self._collector.collect(
            event_type=EventType.INVOICE_PAID,
            organization_id=organization_id,
            value=amount,
            metadata={
                "invoice_id": invoice_id,
                "amount": amount,
                "time_to_payment_hours": time_to_payment_hours,
            },
        )

    async def track_invoice_status_changed(
        self,
        organization_id: str,
        invoice_id: str,
        old_status: str,
        new_status: str,
    ):
        """Trackea cambio de estado de factura."""
        await self._collector.collect(
            event_type=EventType.INVOICE_STATUS_CHANGED,
            organization_id=organization_id,
            metadata={
                "invoice_id": invoice_id,
                "old_status": old_status,
                "new_status": new_status,
            },
        )

    # =========================================================================
    # BOT
    # =========================================================================

    async def track_bot_command(
        self,
        organization_id: Optional[str],
        user_id: int,
        command: str,
        duration_ms: Optional[float] = None,
    ):
        """Trackea un comando del bot."""
        await self._collector.collect(
            event_type=EventType.BOT_COMMAND,
            organization_id=organization_id,
            user_id=user_id,
            duration_ms=duration_ms,
            metadata={"command": command},
        )

    async def track_bot_message(
        self,
        organization_id: Optional[str],
        user_id: int,
        message_type: str = "text",
    ):
        """Trackea un mensaje del bot."""
        await self._collector.collect(
            event_type=EventType.BOT_MESSAGE,
            organization_id=organization_id,
            user_id=user_id,
            metadata={"type": message_type},
        )

    async def track_bot_photo(
        self,
        organization_id: Optional[str],
        user_id: int,
        success: bool = True,
        duration_ms: Optional[float] = None,
    ):
        """Trackea procesamiento de foto."""
        await self._collector.collect(
            event_type=EventType.BOT_PHOTO,
            organization_id=organization_id,
            user_id=user_id,
            success=success,
            duration_ms=duration_ms,
        )

    async def track_bot_voice(
        self,
        organization_id: Optional[str],
        user_id: int,
        success: bool = True,
        duration_ms: Optional[float] = None,
    ):
        """Trackea procesamiento de voz."""
        await self._collector.collect(
            event_type=EventType.BOT_VOICE,
            organization_id=organization_id,
            user_id=user_id,
            success=success,
            duration_ms=duration_ms,
        )

    async def track_bot_error(
        self,
        organization_id: Optional[str],
        user_id: Optional[int],
        error_type: str,
        error_message: str,
    ):
        """Trackea un error del bot."""
        await self._collector.collect(
            event_type=EventType.BOT_ERROR,
            organization_id=organization_id,
            user_id=user_id,
            success=False,
            metadata={
                "error_type": error_type,
                "error_message": error_message[:500],  # Limitar longitud
            },
        )

    # =========================================================================
    # IA
    # =========================================================================

    async def track_ai_extraction(
        self,
        organization_id: str,
        user_id: int,
        extraction_type: str,  # "photo", "voice", "text"
        success: bool,
        duration_ms: float,
        items_extracted: int = 0,
        confidence: Optional[float] = None,
    ):
        """Trackea una extracción de IA."""
        event_type = (
            EventType.AI_EXTRACTION_SUCCESS if success
            else EventType.AI_EXTRACTION_FAILED
        )

        await self._collector.collect(
            event_type=event_type,
            organization_id=organization_id,
            user_id=user_id,
            success=success,
            duration_ms=duration_ms,
            metadata={
                "extraction_type": extraction_type,
                "items_extracted": items_extracted,
                "confidence": confidence,
            },
        )

        # También trackear el evento general
        await self._collector.collect(
            event_type=EventType.AI_EXTRACTION,
            organization_id=organization_id,
            user_id=user_id,
            success=success,
            duration_ms=duration_ms,
            value=float(items_extracted),
        )

    # =========================================================================
    # USUARIOS
    # =========================================================================

    async def track_user_login(
        self,
        organization_id: str,
        user_id: int,
    ):
        """Trackea login de usuario."""
        await self._collector.collect(
            event_type=EventType.USER_LOGIN,
            organization_id=organization_id,
            user_id=user_id,
        )

    async def track_user_registered(
        self,
        organization_id: str,
        user_id: int,
    ):
        """Trackea registro de usuario."""
        await self._collector.collect(
            event_type=EventType.USER_REGISTERED,
            organization_id=organization_id,
            user_id=user_id,
        )

    # =========================================================================
    # ORGANIZACIONES
    # =========================================================================

    async def track_org_created(
        self,
        organization_id: str,
        plan: str,
    ):
        """Trackea creación de organización."""
        await self._collector.collect(
            event_type=EventType.ORG_CREATED,
            organization_id=organization_id,
            metadata={"plan": plan},
        )

    async def track_org_plan_changed(
        self,
        organization_id: str,
        old_plan: str,
        new_plan: str,
    ):
        """Trackea cambio de plan."""
        await self._collector.collect(
            event_type=EventType.ORG_PLAN_CHANGED,
            organization_id=organization_id,
            metadata={
                "old_plan": old_plan,
                "new_plan": new_plan,
            },
        )

    # =========================================================================
    # API
    # =========================================================================

    async def track_api_request(
        self,
        organization_id: Optional[str],
        endpoint: str,
        method: str,
        status_code: int,
        duration_ms: float,
    ):
        """Trackea request a la API."""
        success = 200 <= status_code < 400

        await self._collector.collect(
            event_type=EventType.API_REQUEST,
            organization_id=organization_id,
            success=success,
            duration_ms=duration_ms,
            metadata={
                "endpoint": endpoint,
                "method": method,
                "status_code": status_code,
            },
        )

        if not success:
            await self._collector.collect(
                event_type=EventType.API_ERROR,
                organization_id=organization_id,
                success=False,
                metadata={
                    "endpoint": endpoint,
                    "status_code": status_code,
                },
            )

    async def track_api_rate_limited(
        self,
        organization_id: str,
        endpoint: str,
    ):
        """Trackea rate limiting."""
        await self._collector.collect(
            event_type=EventType.API_RATE_LIMITED,
            organization_id=organization_id,
            success=False,
            metadata={"endpoint": endpoint},
        )

    # =========================================================================
    # NEGOCIO - CLIENTES (JOYERÍA)
    # =========================================================================

    async def track_customer_new(
        self,
        organization_id: str,
        customer_cedula: str,
        customer_name: str,
        user_id: Optional[int] = None,
    ):
        """Trackea registro de cliente nuevo."""
        await self._collector.collect(
            event_type=EventType.CUSTOMER_NEW,
            organization_id=organization_id,
            user_id=user_id,
            metadata={
                "customer_cedula": customer_cedula,
                "customer_name": customer_name,
            },
        )

    async def track_customer_returning(
        self,
        organization_id: str,
        customer_cedula: str,
        customer_name: str,
        previous_purchases: int = 0,
        user_id: Optional[int] = None,
    ):
        """Trackea cliente recurrente (ya existente)."""
        await self._collector.collect(
            event_type=EventType.CUSTOMER_RETURNING,
            organization_id=organization_id,
            user_id=user_id,
            value=float(previous_purchases),
            metadata={
                "customer_cedula": customer_cedula,
                "customer_name": customer_name,
                "previous_purchases": previous_purchases,
            },
        )

    async def track_customer_activity(
        self,
        organization_id: str,
        customer_cedula: str,
        customer_name: str,
        is_new: bool,
        previous_purchases: int = 0,
        user_id: Optional[int] = None,
    ):
        """
        Trackea actividad de cliente (nuevo o recurrente).

        Args:
            organization_id: ID de la organización
            customer_cedula: Cédula del cliente
            customer_name: Nombre del cliente
            is_new: True si es cliente nuevo
            previous_purchases: Compras anteriores (si recurrente)
            user_id: ID del vendedor
        """
        if is_new:
            await self.track_customer_new(
                organization_id, customer_cedula, customer_name, user_id
            )
        else:
            await self.track_customer_returning(
                organization_id, customer_cedula, customer_name,
                previous_purchases, user_id
            )

    # =========================================================================
    # NEGOCIO - PRODUCTOS/VENTAS (JOYERÍA)
    # =========================================================================

    async def track_product_sale(
        self,
        organization_id: str,
        item: Dict[str, Any],
        invoice_id: Optional[str] = None,
        user_id: Optional[int] = None,
    ):
        """
        Trackea venta de producto individual.

        Args:
            organization_id: ID de la organización
            item: Diccionario con datos del item:
                - descripcion: str
                - cantidad: int
                - precio_unitario: float
                - subtotal: float
                - material: Optional[str] (oro, plata, etc.)
                - tipo_prenda: Optional[str] (anillo, collar, etc.)
                - peso_gramos: Optional[float]
            invoice_id: ID de la factura
            user_id: ID del vendedor
        """
        subtotal = item.get('subtotal', 0) or (
            item.get('cantidad', 1) * item.get('precio_unitario', 0)
        )

        # Evento principal de producto vendido
        await self._collector.collect(
            event_type=EventType.PRODUCT_SOLD,
            organization_id=organization_id,
            user_id=user_id,
            value=subtotal,
            metadata={
                "descripcion": item.get('descripcion', ''),
                "cantidad": item.get('cantidad', 1),
                "precio_unitario": item.get('precio_unitario', 0),
                "material": item.get('material'),
                "tipo_prenda": item.get('tipo_prenda'),
                "peso_gramos": item.get('peso_gramos'),
                "invoice_id": invoice_id,
            },
        )

        # Evento por material (si está definido)
        material = item.get('material')
        if material:
            await self._collector.collect(
                event_type=EventType.SALE_BY_MATERIAL,
                organization_id=organization_id,
                user_id=user_id,
                value=subtotal,
                metadata={
                    "material": material,
                    "cantidad": item.get('cantidad', 1),
                    "peso_gramos": item.get('peso_gramos'),
                },
            )

        # Evento por categoría/tipo de prenda (si está definido)
        tipo_prenda = item.get('tipo_prenda')
        if tipo_prenda:
            await self._collector.collect(
                event_type=EventType.SALE_BY_CATEGORY,
                organization_id=organization_id,
                user_id=user_id,
                value=subtotal,
                metadata={
                    "tipo_prenda": tipo_prenda,
                    "cantidad": item.get('cantidad', 1),
                },
            )

    async def track_sale_completed(
        self,
        organization_id: str,
        invoice_id: str,
        total_amount: float,
        items_count: int,
        customer_cedula: Optional[str] = None,
        user_id: Optional[int] = None,
    ):
        """
        Trackea venta completada (factura finalizada).

        Args:
            organization_id: ID de la organización
            invoice_id: ID de la factura
            total_amount: Monto total de la venta
            items_count: Número de items vendidos
            customer_cedula: Cédula del cliente
            user_id: ID del vendedor
        """
        await self._collector.collect(
            event_type=EventType.SALE_COMPLETED,
            organization_id=organization_id,
            user_id=user_id,
            value=total_amount,
            metadata={
                "invoice_id": invoice_id,
                "items_count": items_count,
                "customer_cedula": customer_cedula,
            },
        )

        # Trackear venta del vendedor
        if user_id:
            await self._collector.collect(
                event_type=EventType.SELLER_SALE,
                organization_id=organization_id,
                user_id=user_id,
                value=total_amount,
                metadata={
                    "invoice_id": invoice_id,
                    "items_count": items_count,
                },
            )

    async def track_full_sale(
        self,
        organization_id: str,
        invoice_id: str,
        items: List[Dict[str, Any]],
        total_amount: float,
        customer_data: Optional[Dict[str, Any]] = None,
        is_new_customer: bool = False,
        user_id: Optional[int] = None,
    ):
        """
        Trackea venta completa con todos sus componentes.

        Trackea: cliente, cada producto, y la venta final.

        Args:
            organization_id: ID de la organización
            invoice_id: ID de la factura
            items: Lista de items vendidos
            total_amount: Monto total
            customer_data: Datos del cliente (nombre, cedula)
            is_new_customer: Si es cliente nuevo
            user_id: ID del vendedor
        """
        # 1. Trackear actividad del cliente
        if customer_data:
            await self.track_customer_activity(
                organization_id=organization_id,
                customer_cedula=customer_data.get('cedula', ''),
                customer_name=customer_data.get('nombre', ''),
                is_new=is_new_customer,
                user_id=user_id,
            )

        # 2. Trackear cada producto
        for item in items:
            await self.track_product_sale(
                organization_id=organization_id,
                item=item,
                invoice_id=invoice_id,
                user_id=user_id,
            )

        # 3. Trackear venta completada
        await self.track_sale_completed(
            organization_id=organization_id,
            invoice_id=invoice_id,
            total_amount=total_amount,
            items_count=len(items),
            customer_cedula=customer_data.get('cedula') if customer_data else None,
            user_id=user_id,
        )

    # =========================================================================
    # CONTEXT MANAGERS
    # =========================================================================

    @asynccontextmanager
    async def track_operation(
        self,
        operation_name: str,
        organization_id: Optional[str] = None,
        user_id: Optional[int] = None,
    ):
        """
        Context manager para trackear duración de operaciones.

        Uso:
            async with tracker.track_operation("process_invoice", org_id):
                await process_invoice(data)
        """
        start_time = time.time()
        success = True
        error_message = None

        try:
            yield
        except Exception as e:
            success = False
            error_message = str(e)
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000

            # Determinar tipo de evento según operación
            event_type_map = {
                "ai_extraction": EventType.AI_EXTRACTION,
                "process_photo": EventType.BOT_PHOTO,
                "process_voice": EventType.BOT_VOICE,
                "api_request": EventType.API_REQUEST,
            }

            event_type = event_type_map.get(operation_name, EventType.BOT_MESSAGE)

            await self._collector.collect(
                event_type=event_type,
                organization_id=organization_id,
                user_id=user_id,
                success=success,
                duration_ms=duration_ms,
                metadata={
                    "operation": operation_name,
                    "error": error_message,
                },
            )


# ============================================================================
# SINGLETON
# ============================================================================

_metrics_tracker: Optional[MetricsTracker] = None


def get_metrics_tracker() -> MetricsTracker:
    """Obtiene la instancia singleton del tracker."""
    global _metrics_tracker
    if _metrics_tracker is None:
        _metrics_tracker = MetricsTracker()
    return _metrics_tracker


# Instancia global para import directo
metrics_tracker = get_metrics_tracker()
