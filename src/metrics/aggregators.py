"""
Metrics Aggregators

Agrega métricas por períodos de tiempo para análisis histórico.
Soporta diferentes granularidades: hora, día, semana, mes.
"""

from enum import Enum
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from collections import defaultdict

from src.utils.logger import get_logger
from src.metrics.collectors import EventType, MetricEventData

logger = get_logger(__name__)


# ============================================================================
# ENUMS
# ============================================================================

class AggregationPeriod(str, Enum):
    """Períodos de agregación disponibles."""

    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class AggregatedMetric:
    """Métrica agregada para un período."""

    period: AggregationPeriod
    period_start: datetime
    period_end: datetime
    event_type: str
    organization_id: Optional[str] = None

    # Contadores
    count: int = 0
    total_value: float = 0.0
    success_count: int = 0
    error_count: int = 0
    total_duration_ms: float = 0.0

    # Valores min/max
    min_value: Optional[float] = None
    max_value: Optional[float] = None

    def add_event(self, value: float, success: bool, duration_ms: Optional[float] = None):
        """Agrega un evento a la agregación."""
        self.count += 1
        self.total_value += value

        if success:
            self.success_count += 1
        else:
            self.error_count += 1

        if duration_ms:
            self.total_duration_ms += duration_ms

        # Actualizar min/max
        if self.min_value is None or value < self.min_value:
            self.min_value = value
        if self.max_value is None or value > self.max_value:
            self.max_value = value

    @property
    def avg_value(self) -> float:
        """Valor promedio."""
        if self.count == 0:
            return 0.0
        return self.total_value / self.count

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
            "period": self.period.value,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "event_type": self.event_type,
            "organization_id": self.organization_id,
            "count": self.count,
            "total_value": round(self.total_value, 2),
            "avg_value": round(self.avg_value, 2),
            "min_value": round(self.min_value, 2) if self.min_value else None,
            "max_value": round(self.max_value, 2) if self.max_value else None,
            "success_rate": round(self.success_rate, 4),
            "avg_duration_ms": round(self.avg_duration_ms, 2),
        }


@dataclass
class TimeSeriesPoint:
    """Punto en una serie temporal."""

    timestamp: datetime
    value: float
    count: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "value": round(self.value, 2),
            "count": self.count,
        }


# ============================================================================
# AGGREGATOR
# ============================================================================

class MetricsAggregator:
    """
    Agregador de métricas por período.

    Proporciona funciones para agregar eventos en ventanas
    de tiempo y generar series temporales.
    """

    def __init__(self):
        # Cache de agregaciones
        self._aggregations: Dict[str, AggregatedMetric] = {}
        logger.info("MetricsAggregator inicializado")

    def _get_period_bounds(
        self,
        timestamp: datetime,
        period: AggregationPeriod
    ) -> tuple[datetime, datetime]:
        """Calcula inicio y fin del período."""
        if period == AggregationPeriod.HOUR:
            start = timestamp.replace(minute=0, second=0, microsecond=0)
            end = start + timedelta(hours=1)

        elif period == AggregationPeriod.DAY:
            start = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)

        elif period == AggregationPeriod.WEEK:
            # Inicio de semana (lunes)
            start = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
            start = start - timedelta(days=start.weekday())
            end = start + timedelta(weeks=1)

        elif period == AggregationPeriod.MONTH:
            start = timestamp.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # Siguiente mes
            if start.month == 12:
                end = start.replace(year=start.year + 1, month=1)
            else:
                end = start.replace(month=start.month + 1)

        else:
            raise ValueError(f"Período no soportado: {period}")

        return start, end

    def _get_aggregation_key(
        self,
        event_type: str,
        period: AggregationPeriod,
        period_start: datetime,
        organization_id: Optional[str] = None
    ) -> str:
        """Genera clave única para la agregación."""
        org_part = organization_id or "global"
        return f"{event_type}:{period.value}:{period_start.isoformat()}:{org_part}"

    def aggregate_event(
        self,
        event: MetricEventData,
        period: AggregationPeriod = AggregationPeriod.HOUR
    ) -> AggregatedMetric:
        """
        Agrega un evento al período correspondiente.

        Args:
            event: Evento a agregar
            period: Período de agregación

        Returns:
            Métrica agregada actualizada
        """
        period_start, period_end = self._get_period_bounds(event.timestamp, period)
        key = self._get_aggregation_key(
            event.event_type.value,
            period,
            period_start,
            event.organization_id
        )

        if key not in self._aggregations:
            self._aggregations[key] = AggregatedMetric(
                period=period,
                period_start=period_start,
                period_end=period_end,
                event_type=event.event_type.value,
                organization_id=event.organization_id,
            )

        # Extraer valor del metadata si existe
        value = event.metadata.get("value", 1.0)
        if isinstance(value, (int, float)):
            value = float(value)
        else:
            value = 1.0

        self._aggregations[key].add_event(
            value=value,
            success=event.success,
            duration_ms=event.duration_ms
        )

        return self._aggregations[key]

    def aggregate_events(
        self,
        events: List[MetricEventData],
        period: AggregationPeriod = AggregationPeriod.HOUR
    ) -> List[AggregatedMetric]:
        """
        Agrega múltiples eventos.

        Args:
            events: Lista de eventos
            period: Período de agregación

        Returns:
            Lista de métricas agregadas
        """
        for event in events:
            self.aggregate_event(event, period)

        return list(self._aggregations.values())

    def get_aggregations(
        self,
        event_type: Optional[str] = None,
        organization_id: Optional[str] = None,
        period: Optional[AggregationPeriod] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> List[AggregatedMetric]:
        """
        Obtiene agregaciones filtradas.

        Args:
            event_type: Filtrar por tipo de evento
            organization_id: Filtrar por organización
            period: Filtrar por período
            since: Desde esta fecha
            until: Hasta esta fecha

        Returns:
            Lista de métricas agregadas
        """
        results = list(self._aggregations.values())

        if event_type:
            results = [a for a in results if a.event_type == event_type]

        if organization_id:
            results = [a for a in results if a.organization_id == organization_id]

        if period:
            results = [a for a in results if a.period == period]

        if since:
            results = [a for a in results if a.period_start >= since]

        if until:
            results = [a for a in results if a.period_end <= until]

        # Ordenar por fecha
        results.sort(key=lambda a: a.period_start)

        return results

    def get_time_series(
        self,
        event_type: str,
        period: AggregationPeriod,
        organization_id: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        metric: str = "count",
    ) -> List[TimeSeriesPoint]:
        """
        Genera serie temporal para un tipo de evento.

        Args:
            event_type: Tipo de evento
            period: Granularidad
            organization_id: Filtrar por org
            since: Desde
            until: Hasta
            metric: Métrica a extraer (count, total_value, success_rate)

        Returns:
            Lista de puntos temporales
        """
        aggregations = self.get_aggregations(
            event_type=event_type,
            organization_id=organization_id,
            period=period,
            since=since,
            until=until,
        )

        points = []
        for agg in aggregations:
            if metric == "count":
                value = float(agg.count)
            elif metric == "total_value":
                value = agg.total_value
            elif metric == "avg_value":
                value = agg.avg_value
            elif metric == "success_rate":
                value = agg.success_rate * 100  # Porcentaje
            elif metric == "avg_duration_ms":
                value = agg.avg_duration_ms
            else:
                value = float(agg.count)

            points.append(TimeSeriesPoint(
                timestamp=agg.period_start,
                value=value,
                count=agg.count,
            ))

        return points

    def clear(self):
        """Limpia todas las agregaciones."""
        self._aggregations.clear()


# ============================================================================
# SINGLETON
# ============================================================================

_metrics_aggregator: Optional[MetricsAggregator] = None


def get_metrics_aggregator() -> MetricsAggregator:
    """Obtiene la instancia singleton del agregador."""
    global _metrics_aggregator
    if _metrics_aggregator is None:
        _metrics_aggregator = MetricsAggregator()
    return _metrics_aggregator
