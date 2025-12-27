"""
Metrics Module

Sistema de métricas de negocio para análisis y monitoreo SaaS.

Componentes:
- Collectors: Recolectan eventos del sistema
- Aggregators: Agregan datos por período
- BusinessMetrics: Cálculos de métricas de negocio
- Exporters: Exponen métricas (Prometheus, JSON)

Uso:
    from src.metrics import metrics_tracker, BusinessMetricsService

    # Trackear evento
    await metrics_tracker.track_invoice_created(org_id, amount)

    # Obtener métricas
    service = BusinessMetricsService()
    stats = await service.get_organization_metrics(org_id)
"""

from src.metrics.collectors import (
    MetricsCollector,
    get_metrics_collector,
    EventType,
)

from src.metrics.aggregators import (
    MetricsAggregator,
    AggregationPeriod,
    get_metrics_aggregator,
)

from src.metrics.business import (
    BusinessMetricsService,
    get_business_metrics_service,
    OrganizationMetrics,
    ProductMetrics,
    UsageMetrics,
)

from src.metrics.tracker import (
    MetricsTracker,
    get_metrics_tracker,
    metrics_tracker,
)

__all__ = [
    # Collectors
    "MetricsCollector",
    "get_metrics_collector",
    "EventType",
    # Aggregators
    "MetricsAggregator",
    "AggregationPeriod",
    "get_metrics_aggregator",
    # Business
    "BusinessMetricsService",
    "get_business_metrics_service",
    "OrganizationMetrics",
    "ProductMetrics",
    "UsageMetrics",
    # Tracker
    "MetricsTracker",
    "get_metrics_tracker",
    "metrics_tracker",
]
