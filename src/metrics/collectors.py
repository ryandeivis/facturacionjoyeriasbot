"""
Metrics Collectors

Recolecta y almacena eventos del sistema para análisis posterior.
Diseñado para ser eficiente y no bloquear operaciones principales.

Almacenamiento dual:
- Memoria: Para consultas rápidas y tiempo real
- Base de datos: Para persistencia y análisis histórico
"""

import asyncio
from enum import Enum
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Thread pool para escrituras a BD sin bloquear
_db_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="metrics_db")

# Flag para habilitar/deshabilitar persistencia en BD
_db_persistence_enabled = True


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
class MetricEventData:
    """
    Representa un evento métrico en memoria.

    Nota: Esta clase es diferente del modelo SQLAlchemy MetricEvent
    en src.database.models. Esta se usa para almacenamiento en memoria,
    mientras que el modelo de BD se usa para persistencia.
    """

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
# DATABASE PERSISTENCE
# ============================================================================

def _persist_event_to_db(
    event_type: str,
    organization_id: Optional[str],
    user_id: Optional[int],
    value: float,
    success: bool,
    duration_ms: Optional[float],
    metadata: Dict[str, Any],
) -> None:
    """
    Persiste un evento en la base de datos (ejecutado en thread pool).

    Esta función se ejecuta en un thread separado para no bloquear
    el loop de asyncio principal.
    """
    if not _db_persistence_enabled:
        return

    try:
        from src.database.connection import get_db
        from src.database.queries.metrics_queries import create_metric_event

        db = next(get_db())
        try:
            create_metric_event(
                db=db,
                event_type=event_type,
                organization_id=organization_id,
                user_id=user_id,
                value=value,
                success=success,
                duration_ms=duration_ms,
                metadata=metadata,
            )
        finally:
            db.close()
    except Exception as e:
        # Log pero no falla - la persistencia es best-effort
        logger.warning(f"Error persistiendo métrica en BD: {e}")


def set_db_persistence(enabled: bool) -> None:
    """
    Habilita o deshabilita la persistencia en base de datos.

    Útil para tests o cuando la BD no está disponible.

    Args:
        enabled: True para habilitar, False para deshabilitar
    """
    global _db_persistence_enabled
    _db_persistence_enabled = enabled
    logger.info(f"Persistencia de métricas en BD: {'habilitada' if enabled else 'deshabilitada'}")


def is_db_persistence_enabled() -> bool:
    """Retorna si la persistencia en BD está habilitada."""
    return _db_persistence_enabled


# ============================================================================
# METRICS COLLECTOR
# ============================================================================

class MetricsCollector:
    """
    Recolector de métricas del sistema.

    Almacena eventos en memoria con ventanas de tiempo.
    Opcionalmente persiste a base de datos de forma asíncrona.
    Thread-safe y optimizado para alta frecuencia de escritura.
    """

    def __init__(
        self,
        max_events: int = 10000,
        retention_hours: int = 24,
        persist_to_db: bool = True,
    ):
        """
        Inicializa el collector.

        Args:
            max_events: Máximo de eventos a mantener en memoria
            retention_hours: Horas de retención en memoria
            persist_to_db: Si debe persistir eventos en base de datos
        """
        self._max_events = max_events
        self._retention_hours = retention_hours
        self._persist_to_db = persist_to_db

        # Eventos recientes (para análisis detallado)
        self._events: List[MetricEventData] = []
        self._events_lock = asyncio.Lock()

        # Contadores agregados por tipo y org
        self._counters: Dict[str, Dict[str, MetricCounter]] = defaultdict(
            lambda: defaultdict(MetricCounter)
        )
        self._counters_lock = asyncio.Lock()

        # Contadores globales
        self._global_counters: Dict[str, MetricCounter] = defaultdict(MetricCounter)

        self._started_at = datetime.utcnow()

        logger.info(
            f"MetricsCollector inicializado "
            f"(persist_to_db={persist_to_db}, max_events={max_events})"
        )

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

        Almacena en memoria para acceso rápido y opcionalmente
        persiste en base de datos para análisis histórico.

        Args:
            event_type: Tipo de evento
            organization_id: ID de la organización (tenant)
            user_id: ID del usuario
            value: Valor numérico (ej: monto de factura)
            success: Si la operación fue exitosa
            duration_ms: Duración en milisegundos
            metadata: Datos adicionales
        """
        event = MetricEventData(
            event_type=event_type,
            timestamp=datetime.utcnow(),
            organization_id=organization_id,
            user_id=user_id,
            metadata=metadata or {},
            duration_ms=duration_ms,
            success=success,
        )

        # 1. Agregar a eventos recientes (memoria)
        async with self._events_lock:
            self._events.append(event)

            # Limpiar eventos antiguos si excede límite
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events:]

        # 2. Actualizar contadores (memoria)
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

        # 3. Persistir en base de datos (asíncrono, no bloqueante)
        if self._persist_to_db and _db_persistence_enabled:
            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                _db_executor,
                _persist_event_to_db,
                event_type.value,
                organization_id,
                user_id,
                value,
                success,
                duration_ms,
                metadata or {},
            )

    async def get_events(
        self,
        event_type: Optional[EventType] = None,
        organization_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[MetricEventData]:
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

    # =========================================================================
    # DATABASE QUERY METHODS
    # =========================================================================

    def get_events_from_db(
        self,
        organization_id: Optional[str] = None,
        event_type: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Obtiene eventos históricos desde la base de datos.

        Args:
            organization_id: Filtrar por organización
            event_type: Filtrar por tipo de evento
            since: Eventos desde esta fecha
            limit: Máximo de eventos

        Returns:
            Lista de eventos como diccionarios
        """
        try:
            from src.database.connection import get_db
            from src.database.queries.metrics_queries import get_recent_events

            db = next(get_db())
            try:
                events = get_recent_events(
                    db=db,
                    organization_id=organization_id,
                    event_type=event_type,
                    since=since,
                    limit=limit,
                )
                return [
                    {
                        "id": e.id,
                        "event_type": e.event_type,
                        "organization_id": e.organization_id,
                        "user_id": e.user_id,
                        "value": e.value,
                        "success": e.success,
                        "duration_ms": e.duration_ms,
                        "metadata": e.event_metadata,
                        "created_at": e.created_at.isoformat(),
                    }
                    for e in events
                ]
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error obteniendo eventos de BD: {e}")
            return []

    def get_aggregated_counts_from_db(
        self,
        organization_id: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Obtiene conteos agregados desde la base de datos.

        Args:
            organization_id: Filtrar por organización
            since: Desde esta fecha
            until: Hasta esta fecha

        Returns:
            Diccionario con conteos por tipo de evento
        """
        try:
            from src.database.connection import get_db
            from src.database.queries.metrics_queries import get_event_counts

            db = next(get_db())
            try:
                return get_event_counts(
                    db=db,
                    organization_id=organization_id,
                    since=since,
                    until=until,
                )
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error obteniendo conteos de BD: {e}")
            return {}

    def get_daily_stats_from_db(
        self,
        organization_id: Optional[str] = None,
        event_type: Optional[str] = None,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Obtiene estadísticas diarias desde la base de datos.

        Args:
            organization_id: Filtrar por organización
            event_type: Filtrar por tipo de evento
            days: Número de días hacia atrás

        Returns:
            Lista de estadísticas por día
        """
        try:
            from src.database.connection import get_db
            from src.database.queries.metrics_queries import get_daily_stats

            db = next(get_db())
            try:
                return get_daily_stats(
                    db=db,
                    organization_id=organization_id,
                    event_type=event_type,
                    days=days,
                )
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error obteniendo stats diarias de BD: {e}")
            return []

    def get_organization_summary_from_db(
        self,
        organization_id: str,
        since: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Obtiene resumen de métricas de una organización desde BD.

        Args:
            organization_id: ID de la organización
            since: Desde esta fecha

        Returns:
            Resumen de métricas
        """
        try:
            from src.database.connection import get_db
            from src.database.queries.metrics_queries import get_organization_summary

            db = next(get_db())
            try:
                return get_organization_summary(
                    db=db,
                    organization_id=organization_id,
                    since=since,
                )
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error obteniendo resumen de BD: {e}")
            return {}


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
