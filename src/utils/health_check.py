"""
Health Check System

Sistema unificado de health checks para monitoreo de la aplicación.
Verifica estado de todos los componentes: DB, N8N, servicios externos.
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum

from src.utils.logger import get_logger
from src.utils.metrics import registry, Gauge

logger = get_logger(__name__)


class HealthStatus(str, Enum):
    """Estados posibles de salud."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Resultado de health check de un componente."""
    name: str
    status: HealthStatus
    message: str = ""
    latency_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario."""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "latency_ms": round(self.latency_ms, 2),
            "details": self.details,
            "checked_at": self.checked_at.isoformat() + "Z"
        }


@dataclass
class SystemHealth:
    """Estado de salud del sistema completo."""
    status: HealthStatus
    components: List[ComponentHealth]
    version: str = "1.0.0"
    uptime_seconds: float = 0.0
    checked_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario."""
        return {
            "status": self.status.value,
            "version": self.version,
            "uptime_seconds": round(self.uptime_seconds, 2),
            "checked_at": self.checked_at.isoformat() + "Z",
            "components": [c.to_dict() for c in self.components]
        }


# Métricas de health
health_status_gauge = registry.gauge(
    "health_check_status",
    "Estado de health check (1=healthy, 0.5=degraded, 0=unhealthy)"
)

health_latency = registry.histogram(
    "health_check_latency_seconds",
    "Latencia de health checks"
)


class HealthChecker:
    """
    Sistema centralizado de health checks.

    Registra y ejecuta checks de todos los componentes.
    """

    def __init__(self):
        self._checks: Dict[str, Callable[[], Awaitable[ComponentHealth]]] = {}
        self._start_time = datetime.utcnow()
        self._last_results: Dict[str, ComponentHealth] = {}

    def register(
        self,
        name: str,
        check: Callable[[], Awaitable[ComponentHealth]]
    ) -> None:
        """
        Registra un health check.

        Args:
            name: Nombre del componente
            check: Función async que retorna ComponentHealth
        """
        self._checks[name] = check
        logger.debug(f"Health check registrado: {name}")

    def unregister(self, name: str) -> bool:
        """Elimina un health check."""
        if name in self._checks:
            del self._checks[name]
            return True
        return False

    async def check_component(self, name: str) -> ComponentHealth:
        """
        Ejecuta el health check de un componente específico.

        Args:
            name: Nombre del componente

        Returns:
            Estado de salud del componente
        """
        if name not in self._checks:
            return ComponentHealth(
                name=name,
                status=HealthStatus.UNKNOWN,
                message=f"Componente '{name}' no registrado"
            )

        start = datetime.utcnow()
        try:
            result = await asyncio.wait_for(
                self._checks[name](),
                timeout=10.0  # 10 segundos máximo
            )
            result.latency_ms = (datetime.utcnow() - start).total_seconds() * 1000
            self._last_results[name] = result

            # Actualizar métricas
            status_value = {
                HealthStatus.HEALTHY: 1.0,
                HealthStatus.DEGRADED: 0.5,
                HealthStatus.UNHEALTHY: 0.0,
                HealthStatus.UNKNOWN: 0.0
            }.get(result.status, 0.0)

            health_status_gauge.set(status_value, {"component": name})
            health_latency.observe(
                result.latency_ms / 1000,
                {"component": name}
            )

            return result

        except asyncio.TimeoutError:
            result = ComponentHealth(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message="Health check timeout",
                latency_ms=10000.0
            )
            self._last_results[name] = result
            return result

        except Exception as e:
            logger.error(f"Error en health check {name}: {e}")
            result = ComponentHealth(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Error: {str(e)}"
            )
            self._last_results[name] = result
            return result

    async def check_all(self) -> SystemHealth:
        """
        Ejecuta todos los health checks registrados.

        Returns:
            Estado de salud del sistema completo
        """
        if not self._checks:
            return SystemHealth(
                status=HealthStatus.UNKNOWN,
                components=[],
                message="No hay health checks registrados"
            )

        # Ejecutar todos en paralelo
        tasks = [
            self.check_component(name)
            for name in self._checks
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Procesar resultados
        components = []
        for result in results:
            if isinstance(result, ComponentHealth):
                components.append(result)
            elif isinstance(result, Exception):
                components.append(ComponentHealth(
                    name="unknown",
                    status=HealthStatus.UNHEALTHY,
                    message=str(result)
                ))

        # Determinar estado general
        statuses = [c.status for c in components]

        if all(s == HealthStatus.HEALTHY for s in statuses):
            overall_status = HealthStatus.HEALTHY
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            overall_status = HealthStatus.UNHEALTHY
        elif any(s == HealthStatus.DEGRADED for s in statuses):
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.UNKNOWN

        uptime = (datetime.utcnow() - self._start_time).total_seconds()

        return SystemHealth(
            status=overall_status,
            components=components,
            uptime_seconds=uptime
        )

    def get_last_results(self) -> Dict[str, ComponentHealth]:
        """Obtiene los últimos resultados de health check."""
        return self._last_results.copy()

    @property
    def uptime_seconds(self) -> float:
        """Tiempo de ejecución en segundos."""
        return (datetime.utcnow() - self._start_time).total_seconds()


# Instancia global
health_checker = HealthChecker()


# ============================================================================
# HEALTH CHECK IMPLEMENTATIONS
# ============================================================================

async def check_database() -> ComponentHealth:
    """Health check de la base de datos."""
    try:
        from src.database.health import DatabaseHealth

        result = await DatabaseHealth.check_connection()

        if result.get("status") == "healthy":
            return ComponentHealth(
                name="database",
                status=HealthStatus.HEALTHY,
                message="Conexión OK",
                details=result
            )
        else:
            return ComponentHealth(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message=result.get("error", "Error desconocido"),
                details=result
            )

    except ImportError:
        return ComponentHealth(
            name="database",
            status=HealthStatus.UNKNOWN,
            message="DatabaseHealth no disponible"
        )
    except Exception as e:
        return ComponentHealth(
            name="database",
            status=HealthStatus.UNHEALTHY,
            message=str(e)
        )


async def check_n8n() -> ComponentHealth:
    """Health check del servicio N8N."""
    try:
        from src.services.n8n_service import n8n_service

        is_healthy = await n8n_service.health_check()

        if is_healthy:
            return ComponentHealth(
                name="n8n",
                status=HealthStatus.HEALTHY,
                message="N8N respondiendo"
            )
        else:
            return ComponentHealth(
                name="n8n",
                status=HealthStatus.DEGRADED,
                message="N8N no responde pero puede recuperarse"
            )

    except Exception as e:
        return ComponentHealth(
            name="n8n",
            status=HealthStatus.UNHEALTHY,
            message=str(e)
        )


async def check_memory() -> ComponentHealth:
    """Health check de uso de memoria."""
    try:
        import psutil
        memory = psutil.virtual_memory()

        details = {
            "total_mb": round(memory.total / (1024 * 1024), 2),
            "available_mb": round(memory.available / (1024 * 1024), 2),
            "percent_used": memory.percent
        }

        if memory.percent < 80:
            status = HealthStatus.HEALTHY
            message = f"Memoria OK ({memory.percent}% usado)"
        elif memory.percent < 90:
            status = HealthStatus.DEGRADED
            message = f"Memoria alta ({memory.percent}% usado)"
        else:
            status = HealthStatus.UNHEALTHY
            message = f"Memoria crítica ({memory.percent}% usado)"

        return ComponentHealth(
            name="memory",
            status=status,
            message=message,
            details=details
        )

    except ImportError:
        return ComponentHealth(
            name="memory",
            status=HealthStatus.UNKNOWN,
            message="psutil no instalado"
        )
    except Exception as e:
        return ComponentHealth(
            name="memory",
            status=HealthStatus.UNKNOWN,
            message=str(e)
        )


async def check_disk() -> ComponentHealth:
    """Health check de espacio en disco."""
    try:
        import psutil
        disk = psutil.disk_usage('/')

        details = {
            "total_gb": round(disk.total / (1024 ** 3), 2),
            "free_gb": round(disk.free / (1024 ** 3), 2),
            "percent_used": disk.percent
        }

        if disk.percent < 80:
            status = HealthStatus.HEALTHY
            message = f"Disco OK ({disk.percent}% usado)"
        elif disk.percent < 90:
            status = HealthStatus.DEGRADED
            message = f"Disco alto ({disk.percent}% usado)"
        else:
            status = HealthStatus.UNHEALTHY
            message = f"Disco crítico ({disk.percent}% usado)"

        return ComponentHealth(
            name="disk",
            status=status,
            message=message,
            details=details
        )

    except ImportError:
        return ComponentHealth(
            name="disk",
            status=HealthStatus.UNKNOWN,
            message="psutil no instalado"
        )
    except Exception as e:
        return ComponentHealth(
            name="disk",
            status=HealthStatus.UNKNOWN,
            message=str(e)
        )


# ============================================================================
# INITIALIZATION
# ============================================================================

def register_default_checks() -> None:
    """Registra los health checks por defecto."""
    health_checker.register("database", check_database)
    health_checker.register("n8n", check_n8n)
    health_checker.register("memory", check_memory)
    health_checker.register("disk", check_disk)
    logger.info("Health checks por defecto registrados")


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

async def get_health() -> Dict[str, Any]:
    """Obtiene el estado de salud completo en formato dict."""
    result = await health_checker.check_all()
    return result.to_dict()


async def is_healthy() -> bool:
    """Verifica si el sistema está saludable."""
    result = await health_checker.check_all()
    return result.status == HealthStatus.HEALTHY


async def get_readiness() -> tuple[bool, str]:
    """
    Verifica si el sistema está listo para recibir tráfico.

    Returns:
        Tuple (ready, message)
    """
    result = await health_checker.check_all()

    if result.status == HealthStatus.HEALTHY:
        return True, "System ready"
    elif result.status == HealthStatus.DEGRADED:
        return True, "System degraded but operational"
    else:
        unhealthy = [c.name for c in result.components
                     if c.status == HealthStatus.UNHEALTHY]
        return False, f"Unhealthy components: {', '.join(unhealthy)}"


async def get_liveness() -> tuple[bool, str]:
    """
    Verifica si el sistema está vivo (para Kubernetes liveness probe).

    Retorna True si el proceso está corriendo, sin verificar dependencias.
    """
    return True, "System alive"