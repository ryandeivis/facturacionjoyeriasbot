"""
Health Check Endpoints

Endpoints para verificar el estado de la aplicación y sus dependencias.
Compatible con Kubernetes, Docker y balanceadores de carga.
"""

import time
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass, field, asdict

from src.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# HEALTH CHECK MODELS
# ============================================================================

@dataclass
class ComponentHealth:
    """Estado de salud de un componente."""
    name: str
    status: str  # "up", "down", "degraded"
    latency_ms: Optional[float] = None
    message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "name": self.name,
            "status": self.status,
        }
        if self.latency_ms is not None:
            result["latency_ms"] = round(self.latency_ms, 2)
        if self.message:
            result["message"] = self.message
        if self.details:
            result["details"] = self.details
        return result


@dataclass
class HealthResponse:
    """Respuesta de health check."""
    status: str  # "healthy", "unhealthy", "degraded"
    timestamp: str
    version: str
    environment: str
    components: Dict[str, ComponentHealth] = field(default_factory=dict)
    uptime_seconds: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "timestamp": self.timestamp,
            "version": self.version,
            "environment": self.environment,
            "components": {k: v.to_dict() for k, v in self.components.items()},
            "uptime_seconds": round(self.uptime_seconds, 2) if self.uptime_seconds else None,
        }


# ============================================================================
# HEALTH CHECKERS
# ============================================================================

class HealthChecker:
    """
    Verificador de salud del sistema.

    Verifica el estado de todos los componentes críticos.
    """

    def __init__(self):
        self._start_time = time.time()
        self._checks = {}

    @property
    def uptime(self) -> float:
        """Tiempo de actividad en segundos."""
        return time.time() - self._start_time

    async def check_database(self) -> ComponentHealth:
        """Verifica la conexión a la base de datos."""
        start = time.time()
        try:
            from src.core.context import get_app_context
            from sqlalchemy import text

            ctx = get_app_context()
            async with ctx.db.get_session() as session:
                await session.execute(text("SELECT 1"))

            latency = (time.time() - start) * 1000
            return ComponentHealth(
                name="database",
                status="up",
                latency_ms=latency,
            )

        except Exception as e:
            latency = (time.time() - start) * 1000
            logger.error(f"Database health check failed: {e}")
            return ComponentHealth(
                name="database",
                status="down",
                latency_ms=latency,
                message=str(e),
            )

    async def check_n8n(self) -> ComponentHealth:
        """Verifica la conexión a N8N webhook."""
        start = time.time()
        try:
            from config.settings import settings
            import aiohttp

            if not settings.N8N_WEBHOOK_URL:
                return ComponentHealth(
                    name="n8n",
                    status="up",
                    message="N8N no configurado (opcional)",
                )

            # Solo verificar que el endpoint responde
            async with aiohttp.ClientSession() as session:
                async with session.head(
                    settings.N8N_WEBHOOK_URL,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    latency = (time.time() - start) * 1000

                    if response.status < 500:
                        return ComponentHealth(
                            name="n8n",
                            status="up",
                            latency_ms=latency,
                        )
                    else:
                        return ComponentHealth(
                            name="n8n",
                            status="degraded",
                            latency_ms=latency,
                            message=f"Status: {response.status}",
                        )

        except asyncio.TimeoutError:
            latency = (time.time() - start) * 1000
            return ComponentHealth(
                name="n8n",
                status="degraded",
                latency_ms=latency,
                message="Timeout",
            )
        except Exception as e:
            latency = (time.time() - start) * 1000
            return ComponentHealth(
                name="n8n",
                status="down",
                latency_ms=latency,
                message=str(e),
            )

    async def check_telegram(self) -> ComponentHealth:
        """Verifica la conexión a Telegram API."""
        start = time.time()
        try:
            from config.settings import settings
            import aiohttp

            if not settings.TELEGRAM_BOT_TOKEN:
                return ComponentHealth(
                    name="telegram",
                    status="down",
                    message="Token no configurado",
                )

            url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getMe"

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    latency = (time.time() - start) * 1000

                    if response.status == 200:
                        data = await response.json()
                        return ComponentHealth(
                            name="telegram",
                            status="up",
                            latency_ms=latency,
                            details={"bot_username": data.get("result", {}).get("username")},
                        )
                    else:
                        return ComponentHealth(
                            name="telegram",
                            status="down",
                            latency_ms=latency,
                            message=f"Status: {response.status}",
                        )

        except Exception as e:
            latency = (time.time() - start) * 1000
            return ComponentHealth(
                name="telegram",
                status="down",
                latency_ms=latency,
                message=str(e),
            )

    async def check_all(self) -> HealthResponse:
        """
        Ejecuta todos los health checks.

        Returns:
            HealthResponse con el estado de todos los componentes
        """
        from config.settings import settings

        # Ejecutar checks en paralelo
        db_check, n8n_check, telegram_check = await asyncio.gather(
            self.check_database(),
            self.check_n8n(),
            self.check_telegram(),
            return_exceptions=True,
        )

        components = {}

        # Procesar resultados
        for check in [db_check, n8n_check, telegram_check]:
            if isinstance(check, Exception):
                components["error"] = ComponentHealth(
                    name="error",
                    status="down",
                    message=str(check),
                )
            elif isinstance(check, ComponentHealth):
                components[check.name] = check

        # Determinar estado general
        statuses = [c.status for c in components.values()]

        if all(s == "up" for s in statuses):
            overall_status = "healthy"
        elif any(s == "down" for s in statuses):
            # Si la DB está down, es crítico
            if components.get("database", ComponentHealth("db", "up")).status == "down":
                overall_status = "unhealthy"
            else:
                overall_status = "degraded"
        else:
            overall_status = "degraded"

        env_value = settings.ENVIRONMENT.value if hasattr(settings.ENVIRONMENT, 'value') else str(settings.ENVIRONMENT)

        return HealthResponse(
            status=overall_status,
            timestamp=datetime.utcnow().isoformat() + "Z",
            version=settings.VERSION,
            environment=env_value,
            components=components,
            uptime_seconds=self.uptime,
        )

    async def liveness(self) -> Dict[str, Any]:
        """
        Liveness probe para Kubernetes.

        Solo verifica que la aplicación esté corriendo.
        """
        return {
            "status": "alive",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    async def readiness(self) -> Dict[str, Any]:
        """
        Readiness probe para Kubernetes.

        Verifica que la aplicación pueda recibir tráfico.
        """
        db_check = await self.check_database()

        if db_check.status == "up":
            return {
                "status": "ready",
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
        else:
            return {
                "status": "not_ready",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "reason": db_check.message,
            }


# ============================================================================
# SINGLETON
# ============================================================================

_health_checker: Optional[HealthChecker] = None


def get_health_checker() -> HealthChecker:
    """Obtiene la instancia del health checker."""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker


# ============================================================================
# ROUTER (para FastAPI si se usa)
# ============================================================================

try:
    from fastapi import APIRouter, Response

    health_router = APIRouter(prefix="/health", tags=["health"])

    @health_router.get(
        "",
        summary="Health check completo",
        description="Verifica el estado de todos los componentes del sistema",
        responses={
            200: {"description": "Sistema saludable"},
            503: {"description": "Sistema no saludable"}
        }
    )
    async def health_check():
        """
        Health check completo del sistema.

        Verifica:
        - Base de datos
        - Conexión a N8N
        - API de Telegram

        Returns:
            Estado de salud de cada componente y estado general
        """
        checker = get_health_checker()
        result = await checker.check_all()
        return result.to_dict()

    @health_router.get(
        "/live",
        summary="Liveness probe",
        description="Verifica que la aplicación está viva (Kubernetes)"
    )
    async def liveness_check():
        """
        Liveness probe para Kubernetes.

        Solo verifica que la aplicación está corriendo.
        No verifica dependencias externas.
        """
        checker = get_health_checker()
        return await checker.liveness()

    @health_router.get(
        "/ready",
        summary="Readiness probe",
        description="Verifica que la aplicación puede recibir tráfico",
        responses={
            200: {"description": "Aplicación lista"},
            503: {"description": "Aplicación no lista"}
        }
    )
    async def readiness_check(response: Response):
        """
        Readiness probe para Kubernetes.

        Verifica que la aplicación puede recibir tráfico.
        Requiere conexión a base de datos.
        """
        checker = get_health_checker()
        result = await checker.readiness()

        if result["status"] != "ready":
            response.status_code = 503

        return result

except ImportError:
    # FastAPI no instalado, crear un router dummy
    health_router = None