"""
API Module

Endpoints HTTP para health checks, métricas y administración.
"""

from src.api.health import health_router

__all__ = ["health_router"]