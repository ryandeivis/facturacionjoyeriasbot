"""
Metrics Collectors

Recolecta y almacena eventos del sistema para análisis posterior.
Diseñado para ser eficiente y no bloquear operaciones principales.
"""

import time
import asyncio
from enum import Enum
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from collections import defaultdict

from src.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# ENUMS
# ============================================================================

class EventType(str, Enum):
    """Tipos de eventos que se pueden trackear."""

    # Facturas
    INVOICE_CREATED = "invoice.created"
    INVOICE_UPDATED = "invoice.updated"
    INVOICE_DELETED = "invoice.deleted"
    INVOICE_STATUS_CHANGED = "invoice.status_changed"
    INVOICE_PAID = "invoice.paid"

    # Bot
    BOT_COMMAND = "bot.command"
    BOT_MESSAGE = "bot.message"
    BOT_PHOTO = "bot.photo"
    BOT_VOICE = "bot.voice"
    BOT_ERROR = "bot.error"

    # IA
    AI_EXTRACTION = "ai.extraction"
    AI_EXTRACTION_SUCCESS = "ai.extraction.success"
    AI_EXTRACTION_FAILED = "ai.extraction.failed"

    # Usuarios
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    USER_REGISTERED = "user.registered"

    # Organizaciones
    ORG_CREATED = "org.created"
    ORG_PLAN_CHANGED = "org.plan_changed"
    ORG_DEACTIVATED = "org.deactivated"

    # API
    API_REQUEST = "api.request"
    API_ERROR = "api.error"
    API_RATE_LIMITED = "api.rate_limited"


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class MetricEvent:
    """Representa un evento métrico."""

    event_type: EventType
    timestamp: datetime
    organization_id: Optional[str] = None
    user_id: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[float] = None
    success: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "organization_id": self.organization_id,
            "user_id": self.user_id,
            "metadata": self.metadata,
            "duration_ms": self.duration_ms,
            "success": self.success,
        }


@dataclass
class MetricCounter:
    """Contador de métricas con ventana de tiempo."""

    count: int = 0
    total_value: float = 0.0
    success_count: int = 0
    error_count: int = 0
    total_duration_ms: float = 0.0
    last_updated: datetime = field(default_factory=datetime.utcnow)

    def increment(
        self,
        value: float = 1.0,
        success: bool = True,
        duration_ms: Optional[float] = None
    ):
        """Incrementa el contador."""
        self.count += 1
        self.total_value += value

        if success:
            self.success_count += 1
        else:
            self.error_count += 1

        if duration_ms:
            self.total_duration_ms += duration_ms

        self.last_updated = datetime.utcnow()

    @property
    def success_rate(self) -> float:
        """Tasa de éxito."""
        if self.count == 0:
            return 0.0
        return self.success_count / self.count

    @property
    def avg_duration_ms(self) -> float:
        """Duración promedio."""
        if self.count == 0:
            return 0.0
        return self.total_duration_ms / self.count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "count": self.count,
            "total_value": self.total_value,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "success_rate": round(self.success_rate, 4),
            "avg_duration_ms": round(self.avg_duration_ms, 2),
            "last_updated": self.last_updated.isoformat(),
        }


# ============================================================================
# METRICS COLLECTOR
# ============================================================================

class MetricsCollector:
    """
    Recolector de métricas del sistema.

    Almacena eventos en memoria con ventanas de tiempo.
    Thread-safe y optimizado para alta frecuencia de escritura.
    """

    def __init__(self, max_events: int = 10000, retention_hours: int = 24):
        self._max_events = max_events
        self._retention_hours = retention_hours

        # Eventos recientes (para análisis detallado)
        self._events: List[MetricEvent] = []
        self._events_lock = asyncio.Lock()

        # Contadores agregados por tipo y org
        self._counters: Dict[str, Dict[str, MetricCounter]] = defaultdict(
            lambda: defaultdict(MetricCounter)
        )
        self._counters_lock = asyncio.Lock()

        # Contadores globales
        self._global_counters: Dict[str, MetricCounter] = defaultdict(MetricCounter)

        self._started_at = datetime.utcnow()

        logger.info("MetricsCollector inicializado")

    async def collect(
        self,
        event_type: EventType,
        organization_id: Optional[str] = None,
        user_id: Optional[int] = None,
        value: float = 1.0,
        success: bool = True,
        duration_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Recolecta un evento métrico.

        Args:
            event_type: Tipo de evento
            organization_id: ID de la organización (tenant)
            user_id: ID del usuario
            value: Valor numérico (ej: monto de factura)
            success: Si la operación fue exitosa
            duration_ms: Duración en milisegundos
            metadata: Datos adicionales
        """
        event = MetricEvent(
            event_type=event_type,
            timestamp=datetime.utcnow(),
            organization_id=organization_id,
            user_id=user_id,
            metadata=metadata or {},
            duration_ms=duration_ms,
            success=success,
        )

        # Agregar a eventos recientes
        async with self._events_lock:
            self._events.append(event)

            # Limpiar eventos antiguos si excede límite
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events:]

        # Actualizar contadores
        async with self._counters_lock:
            # Contador global
            self._global_counters[event_type.value].increment(
                value=value,
                success=success,
                duration_ms=duration_ms
            )

            # Contador por organización
            if organization_id:
                self._counters[organization_id][event_type.value].increment(
                    value=value,
                    success=success,
                    duration_ms=duration_ms
                )

    async def get_events(
        self,
        event_type: Optional[EventType] = None,
        organization_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[MetricEvent]:
        """
        Obtiene eventos filtrados.

        Args:
            event_type: Filtrar por tipo
            organization_id: Filtrar por organización
            since: Eventos desde esta fecha
            limit: Máximo de eventos a retornar
        """
        async with self._events_lock:
            filtered = self._events.copy()

        if event_type:
            filtered = [e for e in filtered if e.event_type == event_type]

        if organization_id:
            filtered = [e for e in filtered if e.organization_id == organization_id]

        if since:
            filtered = [e for e in filtered if e.timestamp >= since]

        # Ordenar por timestamp descendente y limitar
        filtered.sort(key=lambda e: e.timestamp, reverse=True)
        return filtered[:limit]

    async def get_counter(
        self,
        event_type: EventType,
        organization_id: Optional[str] = None,
    ) -> MetricCounter:
        """
        Obtiene el contador para un tipo de evento.

        Args:
            event_type: Tipo de evento
            organization_id: ID de organización (None para global)
        """
        async with self._counters_lock:
            if organization_id:
                return self._counters[organization_id][event_type.value]
            return self._global_counters[event_type.value]

    async def get_organization_counters(
        self,
        organization_id: str
    ) -> Dict[str, MetricCounter]:
        """Obtiene todos los contadores de una organización."""
        async with self._counters_lock:
            return dict(self._counters[organization_id])

    async def get_global_counters(self) -> Dict[str, MetricCounter]:
        """Obtiene todos los contadores globales."""
        async with self._counters_lock:
            return dict(self._global_counters)

    async def get_summary(self) -> Dict[str, Any]:
        """Obtiene resumen de métricas recolectadas."""
        async with self._events_lock:
            events_count = len(self._events)

        async with self._counters_lock:
            orgs_count = len(self._counters)
            event_types_count = len(self._global_counters)

        return {
            "events_in_memory": events_count,
            "organizations_tracked": orgs_count,
            "event_types_tracked": event_types_count,
            "uptime_seconds": (datetime.utcnow() - self._started_at).total_seconds(),
            "max_events": self._max_events,
            "retention_hours": self._retention_hours,
        }

    async def cleanup_old_events(self):
        """Limpia eventos más antiguos que la retención."""
        cutoff = datetime.utcnow() - timedelta(hours=self._retention_hours)

        async with self._events_lock:
            before = len(self._events)
            self._events = [e for e in self._events if e.timestamp >= cutoff]
            after = len(self._events)

        if before != after:
            logger.info(f"Limpiados {before - after} eventos antiguos")


# ============================================================================
# SINGLETON
# ============================================================================

_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Obtiene la instancia singleton del collector."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector
