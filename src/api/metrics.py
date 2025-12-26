"""
Metrics Endpoints

Endpoints para exponer métricas de la aplicación.
Compatible con Prometheus y formato JSON.
"""

from typing import Dict, Any
from datetime import datetime

from src.utils.logger import get_logger
from src.utils.metrics import get_metrics, get_prometheus_metrics, registry

logger = get_logger(__name__)


async def get_metrics_json() -> Dict[str, Any]:
    """
    Obtiene métricas en formato JSON.

    Returns:
        Diccionario con todas las métricas
    """
    metrics = get_metrics()
    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "metrics": metrics
    }


async def get_metrics_prometheus() -> str:
    """
    Obtiene métricas en formato Prometheus.

    Returns:
        String en formato Prometheus exposition
    """
    return get_prometheus_metrics()


# ============================================================================
# FASTAPI ROUTER
# ============================================================================

try:
    from fastapi import APIRouter, Response

    metrics_router = APIRouter(prefix="/metrics", tags=["metrics"])

    @metrics_router.get("")
    async def metrics_json():
        """Métricas en formato JSON."""
        return await get_metrics_json()

    @metrics_router.get("/prometheus")
    async def metrics_prometheus(response: Response):
        """Métricas en formato Prometheus."""
        content = await get_metrics_prometheus()
        response.headers["Content-Type"] = "text/plain; charset=utf-8"
        return Response(content=content, media_type="text/plain")

except ImportError:
    metrics_router = None