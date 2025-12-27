"""
Business Metrics API Endpoints

Endpoints REST para consultar métricas de negocio.
Acceso controlado por organización y rol.
"""

from datetime import datetime, timedelta
from typing import Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Intentar importar FastAPI
try:
    from fastapi import APIRouter, Query, Path, HTTPException
    from pydantic import BaseModel, Field

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    logger.warning("FastAPI no instalado. Endpoints de métricas no disponibles.")


if FASTAPI_AVAILABLE:
    from src.metrics import (
        BusinessMetricsService,
        get_business_metrics_service,
        get_metrics_collector,
        AggregationPeriod,
    )

    # =========================================================================
    # SCHEMAS
    # =========================================================================

    class MetricsPeriodParams(BaseModel):
        """Parámetros de período para consultas."""
        since: Optional[datetime] = Field(
            None,
            description="Inicio del período (default: 30 días atrás)"
        )
        until: Optional[datetime] = Field(
            None,
            description="Fin del período (default: ahora)"
        )

    class TimeSeriesParams(BaseModel):
        """Parámetros para series temporales."""
        period: AggregationPeriod = Field(
            AggregationPeriod.DAY,
            description="Granularidad de la serie"
        )
        metric: str = Field(
            "count",
            description="Métrica a extraer: count, total_value, success_rate"
        )

    # =========================================================================
    # ROUTER
    # =========================================================================

    business_metrics_router = APIRouter(
        prefix="/metrics/business",
        tags=["business-metrics"],
    )

    @business_metrics_router.get(
        "",
        summary="Resumen de métricas de negocio",
        description="Obtiene un resumen general de todas las métricas de negocio",
    )
    async def get_business_summary():
        """
        Resumen general de métricas.

        Incluye:
        - Métricas de producto (organizaciones, facturas)
        - Métricas de uso (API, bot)
        - Estado del collector
        """
        service = get_business_metrics_service()
        return await service.get_summary()

    @business_metrics_router.get(
        "/product",
        summary="Métricas del producto",
        description="Métricas globales del producto SaaS",
    )
    async def get_product_metrics(
        since: Optional[datetime] = Query(None, description="Inicio del período"),
        until: Optional[datetime] = Query(None, description="Fin del período"),
    ):
        """
        Métricas globales del producto.

        Incluye:
        - Organizaciones (total, activas, nuevas, churned)
        - Distribución por plan
        - Facturas procesadas
        - Uso de features
        """
        service = get_business_metrics_service()
        metrics = await service.get_product_metrics(since=since, until=until)
        return metrics.to_dict()

    @business_metrics_router.get(
        "/usage",
        summary="Métricas de uso",
        description="Patrones de uso del sistema",
    )
    async def get_usage_metrics(
        since: Optional[datetime] = Query(None, description="Inicio del período"),
        until: Optional[datetime] = Query(None, description="Fin del período"),
    ):
        """
        Métricas de uso del sistema.

        Incluye:
        - Requests API (total, errores, latencia)
        - Interacciones del bot
        - Patrones por hora y día
        """
        service = get_business_metrics_service()
        metrics = await service.get_usage_metrics(since=since, until=until)
        return metrics.to_dict()

    @business_metrics_router.get(
        "/organizations/{organization_id}",
        summary="Métricas de organización",
        description="Métricas detalladas de una organización específica",
    )
    async def get_organization_metrics(
        organization_id: str = Path(..., description="ID de la organización"),
        since: Optional[datetime] = Query(None, description="Inicio del período"),
        until: Optional[datetime] = Query(None, description="Fin del período"),
    ):
        """
        Métricas completas de una organización.

        Incluye:
        - Usuarios activos
        - Métricas de facturación
        - Uso del bot
        - Engagement
        """
        service = get_business_metrics_service()
        metrics = await service.get_organization_metrics(
            organization_id=organization_id,
            since=since,
            until=until,
        )
        return metrics.to_dict()

    @business_metrics_router.get(
        "/organizations/{organization_id}/health",
        summary="Health score de organización",
        description="Calcula el score de salud de una organización",
    )
    async def get_organization_health(
        organization_id: str = Path(..., description="ID de la organización"),
    ):
        """
        Score de salud de la organización.

        El score (0-100) considera:
        - Actividad reciente
        - Tasa de conversión de facturas
        - Éxito de extracciones IA
        - Uso de features
        """
        service = get_business_metrics_service()
        score = await service.get_organization_health_score(organization_id)

        # Determinar nivel
        if score >= 80:
            level = "healthy"
        elif score >= 50:
            level = "moderate"
        else:
            level = "at_risk"

        return {
            "organization_id": organization_id,
            "health_score": round(score, 2),
            "level": level,
            "calculated_at": datetime.utcnow().isoformat(),
        }

    @business_metrics_router.get(
        "/at-risk",
        summary="Organizaciones en riesgo",
        description="Lista organizaciones en riesgo de churn",
    )
    async def get_at_risk_organizations(
        threshold_days: int = Query(7, description="Días sin actividad"),
        min_health_score: float = Query(50.0, description="Score mínimo de salud"),
    ):
        """
        Organizaciones en riesgo de abandonar el servicio.

        Criterios:
        - Sin actividad en los últimos N días
        - Health score por debajo del umbral
        """
        service = get_business_metrics_service()
        orgs = await service.get_at_risk_organizations(
            threshold_days=threshold_days,
            min_health_score=min_health_score,
        )
        return {
            "organizations": orgs,
            "count": len(orgs),
            "criteria": {
                "threshold_days": threshold_days,
                "min_health_score": min_health_score,
            },
        }

    @business_metrics_router.get(
        "/events",
        summary="Eventos recientes",
        description="Lista eventos métricos recientes",
    )
    async def get_recent_events(
        event_type: Optional[str] = Query(None, description="Filtrar por tipo"),
        organization_id: Optional[str] = Query(None, description="Filtrar por org"),
        limit: int = Query(100, ge=1, le=1000, description="Máximo de eventos"),
    ):
        """
        Eventos métricos recientes.

        Útil para debugging y análisis en tiempo real.
        """
        from src.metrics.collectors import EventType

        collector = get_metrics_collector()

        # Convertir string a EventType si se proporciona
        event_type_enum = None
        if event_type:
            try:
                event_type_enum = EventType(event_type)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Tipo de evento inválido: {event_type}"
                )

        events = await collector.get_events(
            event_type=event_type_enum,
            organization_id=organization_id,
            limit=limit,
        )

        return {
            "events": [e.to_dict() for e in events],
            "count": len(events),
        }

    @business_metrics_router.get(
        "/counters",
        summary="Contadores globales",
        description="Contadores agregados por tipo de evento",
    )
    async def get_global_counters():
        """
        Contadores globales de todos los tipos de evento.

        Muestra totales acumulados desde el inicio.
        """
        collector = get_metrics_collector()
        counters = await collector.get_global_counters()

        return {
            "counters": {
                event_type: counter.to_dict()
                for event_type, counter in counters.items()
            },
            "total_event_types": len(counters),
        }

    @business_metrics_router.get(
        "/collector/status",
        summary="Estado del collector",
        description="Estado interno del recolector de métricas",
    )
    async def get_collector_status():
        """
        Estado del collector de métricas.

        Información sobre:
        - Eventos en memoria
        - Organizaciones trackeadas
        - Uptime
        """
        collector = get_metrics_collector()
        return await collector.get_summary()

else:
    # FastAPI no disponible
    business_metrics_router = None
