"""
Tests para el sistema de health checks.
"""

import pytest
from datetime import datetime

from src.utils.health_check import (
    HealthStatus,
    ComponentHealth,
    SystemHealth,
    HealthChecker,
    health_checker,
)


class TestHealthStatus:
    """Tests para HealthStatus enum."""

    def test_health_statuses(self):
        """Verifica que existen todos los estados."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"
        assert HealthStatus.UNKNOWN.value == "unknown"


class TestComponentHealth:
    """Tests para ComponentHealth dataclass."""

    def test_component_health_creation(self):
        """Verifica creación de ComponentHealth."""
        health = ComponentHealth(
            name="database",
            status=HealthStatus.HEALTHY,
            message="Connection OK",
            latency_ms=15.5
        )

        assert health.name == "database"
        assert health.status == HealthStatus.HEALTHY
        assert health.latency_ms == 15.5

    def test_component_health_to_dict(self):
        """Verifica conversión a diccionario."""
        health = ComponentHealth(
            name="test",
            status=HealthStatus.HEALTHY,
            message="OK",
            latency_ms=10.0,
            details={"version": "1.0"}
        )

        data = health.to_dict()

        assert data["name"] == "test"
        assert data["status"] == "healthy"
        assert data["message"] == "OK"
        assert data["latency_ms"] == 10.0
        assert data["details"]["version"] == "1.0"

    def test_component_health_defaults(self):
        """Verifica valores por defecto."""
        health = ComponentHealth(
            name="test",
            status=HealthStatus.UNKNOWN
        )

        assert health.message == ""
        assert health.latency_ms == 0.0
        assert health.details == {}


class TestSystemHealth:
    """Tests para SystemHealth dataclass."""

    def test_system_health_creation(self):
        """Verifica creación de SystemHealth."""
        components = [
            ComponentHealth(name="db", status=HealthStatus.HEALTHY),
            ComponentHealth(name="cache", status=HealthStatus.HEALTHY)
        ]

        health = SystemHealth(
            status=HealthStatus.HEALTHY,
            components=components,
            version="1.0.0",
            uptime_seconds=3600.0
        )

        assert health.status == HealthStatus.HEALTHY
        assert len(health.components) == 2
        assert health.version == "1.0.0"

    def test_system_health_to_dict(self):
        """Verifica conversión a diccionario."""
        components = [
            ComponentHealth(name="db", status=HealthStatus.HEALTHY)
        ]

        health = SystemHealth(
            status=HealthStatus.HEALTHY,
            components=components,
            uptime_seconds=100.5
        )

        data = health.to_dict()

        assert data["status"] == "healthy"
        assert len(data["components"]) == 1
        assert data["uptime_seconds"] == 100.5


class TestHealthChecker:
    """Tests para HealthChecker."""

    @pytest.fixture
    def checker(self):
        """Crea un HealthChecker para tests."""
        return HealthChecker()

    def test_register_check(self, checker):
        """Verifica registro de health check."""
        async def dummy_check():
            return ComponentHealth(name="dummy", status=HealthStatus.HEALTHY)

        checker.register("dummy", dummy_check)

        assert "dummy" in checker._checks

    def test_unregister_check(self, checker):
        """Verifica eliminación de health check."""
        async def dummy_check():
            return ComponentHealth(name="dummy", status=HealthStatus.HEALTHY)

        checker.register("dummy", dummy_check)
        result = checker.unregister("dummy")

        assert result is True
        assert "dummy" not in checker._checks

    def test_unregister_nonexistent(self, checker):
        """Verifica eliminación de check inexistente."""
        result = checker.unregister("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_check_component(self, checker):
        """Verifica ejecución de check de componente."""
        async def healthy_check():
            return ComponentHealth(
                name="test",
                status=HealthStatus.HEALTHY,
                message="All good"
            )

        checker.register("test", healthy_check)
        result = await checker.check_component("test")

        assert result.status == HealthStatus.HEALTHY
        assert result.name == "test"
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_check_component_nonexistent(self, checker):
        """Verifica check de componente inexistente."""
        result = await checker.check_component("nonexistent")

        assert result.status == HealthStatus.UNKNOWN
        assert "no registrado" in result.message

    @pytest.mark.asyncio
    async def test_check_component_with_error(self, checker):
        """Verifica manejo de errores en check."""
        async def failing_check():
            raise Exception("Test error")

        checker.register("failing", failing_check)
        result = await checker.check_component("failing")

        assert result.status == HealthStatus.UNHEALTHY
        assert "Error" in result.message

    @pytest.mark.asyncio
    async def test_check_all_healthy(self, checker):
        """Verifica check_all cuando todo está saludable."""
        async def healthy1():
            return ComponentHealth(name="comp1", status=HealthStatus.HEALTHY)

        async def healthy2():
            return ComponentHealth(name="comp2", status=HealthStatus.HEALTHY)

        checker.register("comp1", healthy1)
        checker.register("comp2", healthy2)

        result = await checker.check_all()

        assert result.status == HealthStatus.HEALTHY
        assert len(result.components) == 2

    @pytest.mark.asyncio
    async def test_check_all_degraded(self, checker):
        """Verifica check_all cuando hay componentes degradados."""
        async def healthy():
            return ComponentHealth(name="healthy", status=HealthStatus.HEALTHY)

        async def degraded():
            return ComponentHealth(name="degraded", status=HealthStatus.DEGRADED)

        checker.register("healthy", healthy)
        checker.register("degraded", degraded)

        result = await checker.check_all()

        assert result.status == HealthStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_check_all_unhealthy(self, checker):
        """Verifica check_all cuando hay componentes unhealthy."""
        async def healthy():
            return ComponentHealth(name="healthy", status=HealthStatus.HEALTHY)

        async def unhealthy():
            return ComponentHealth(name="unhealthy", status=HealthStatus.UNHEALTHY)

        checker.register("healthy", healthy)
        checker.register("unhealthy", unhealthy)

        result = await checker.check_all()

        assert result.status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_check_all_empty(self, checker):
        """Verifica check_all sin checks registrados."""
        result = await checker.check_all()

        assert result.status == HealthStatus.UNKNOWN

    def test_uptime_seconds(self, checker):
        """Verifica cálculo de uptime."""
        import time
        time.sleep(0.1)

        uptime = checker.uptime_seconds

        assert uptime >= 0.1

    def test_get_last_results(self, checker):
        """Verifica obtención de últimos resultados."""
        results = checker.get_last_results()
        assert isinstance(results, dict)


class TestGlobalHealthChecker:
    """Tests para la instancia global."""

    def test_global_instance_exists(self):
        """Verifica que existe la instancia global."""
        assert health_checker is not None
        assert isinstance(health_checker, HealthChecker)