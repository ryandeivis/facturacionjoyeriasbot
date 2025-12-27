"""
Metrics Tracker

Interface simplificada para trackear eventos desde cualquier parte del código.
Proporciona métodos convenientes para los eventos más comunes.
"""

import time
from datetime import datetime
from typing import Dict, Any, Optional
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
