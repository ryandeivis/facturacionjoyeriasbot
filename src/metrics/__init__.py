"""
Metrics Module

Sistema de métricas de negocio para análisis y monitoreo SaaS.

Componentes:
- Collectors: Recolectan eventos del sistema
- Aggregators: Agregan datos por período
- BusinessMetrics: Cálculos de métricas de negocio
- Exporters: Exponen métricas (Prometheus, JSON)

Almacenamiento:
- Memoria: Para consultas rápidas (últimas 24h)
- Base de datos: Para persistencia y análisis histórico

Uso:
    from src.metrics import metrics_tracker, BusinessMetricsService

    # Trackear evento (se guarda en memoria + BD automáticamente)
    await metrics_tracker.track_invoice_created(org_id, amount)

    # Obtener métricas (usa BD automáticamente si período > 24h)
    service = BusinessMetricsService()
    stats = await service.get_organization_metrics(org_id)

    # Forzar uso de BD para análisis histórico
    from src.metrics import DataSource
    stats = await service.get_organization_metrics(org_id, source=DataSource.DATABASE)
"""

from src.metrics.collectors import (
    MetricsCollector,
    get_metrics_collector,
    EventType,
    set_db_persistence,
    is_db_persistence_enabled,
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
    DataSource,
    # Métricas de joyería
    CustomerStats,
    SellerPerformance,
    TopProduct,
    JewelryMetrics,
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
    "set_db_persistence",
    "is_db_persistence_enabled",
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
    "DataSource",
    # Métricas de joyería
    "CustomerStats",
    "SellerPerformance",
    "TopProduct",
    "JewelryMetrics",
    # Tracker
    "MetricsTracker",
    "get_metrics_tracker",
    "metrics_tracker",
]
