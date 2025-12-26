"""
Tests de integración para la API REST.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

# Intentar importar FastAPI
try:
    from fastapi.testclient import TestClient
    from src.api.app import create_app
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not installed")
class TestHealthEndpoints:
    """Tests para endpoints de health."""

    @pytest.fixture
    def client(self):
        """Crea cliente de test."""
        app = create_app()
        return TestClient(app)

    def test_root_endpoint(self, client):
        """Verifica endpoint raíz."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "status" in data

    def test_health_endpoint(self, client):
        """Verifica endpoint de health."""
        with patch('src.api.health.get_health_checker') as mock_checker:
            mock_instance = MagicMock()
            mock_instance.check_all = AsyncMock(return_value=MagicMock(
                to_dict=lambda: {
                    "status": "healthy",
                    "components": {},
                    "timestamp": "2024-01-01T00:00:00Z"
                }
            ))
            mock_checker.return_value = mock_instance

            response = client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"

    def test_liveness_endpoint(self, client):
        """Verifica endpoint de liveness."""
        with patch('src.api.health.get_health_checker') as mock_checker:
            mock_instance = MagicMock()
            mock_instance.liveness = AsyncMock(return_value={
                "status": "alive",
                "timestamp": "2024-01-01T00:00:00Z"
            })
            mock_checker.return_value = mock_instance

            response = client.get("/health/live")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "alive"


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not installed")
class TestMetricsEndpoints:
    """Tests para endpoints de métricas."""

    @pytest.fixture
    def client(self):
        """Crea cliente de test."""
        app = create_app()
        return TestClient(app)

    def test_metrics_json_endpoint(self, client):
        """Verifica endpoint de métricas JSON."""
        response = client.get("/metrics")

        assert response.status_code == 200
        data = response.json()
        assert "timestamp" in data
        assert "metrics" in data

    def test_metrics_prometheus_endpoint(self, client):
        """Verifica endpoint de métricas Prometheus."""
        response = client.get("/metrics/prometheus")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not installed")
class TestAPIInfo:
    """Tests para información de la API."""

    @pytest.fixture
    def client(self):
        """Crea cliente de test."""
        app = create_app()
        return TestClient(app)

    def test_api_info_endpoint(self, client):
        """Verifica endpoint de información de API."""
        response = client.get("/api/v1")

        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "endpoints" in data


# Tests para servicios sin FastAPI (siempre ejecutan)
class TestOrganizationService:
    """Tests para OrganizationService."""

    @pytest.fixture
    def service(self):
        """Crea servicio de organizaciones."""
        from src.api.organizations import OrganizationService
        return OrganizationService()

    @pytest.mark.asyncio
    async def test_list_organizations_empty(self, service):
        """Verifica listado vacío de organizaciones."""
        with patch('src.api.organizations.get_async_db') as mock_db:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=None)

            orgs = await service.list_organizations()

            assert orgs == []


class TestInvoiceAPIService:
    """Tests para InvoiceAPIService."""

    @pytest.fixture
    def service(self):
        """Crea servicio de facturas API."""
        from src.api.invoices import InvoiceAPIService
        return InvoiceAPIService()

    @pytest.mark.asyncio
    async def test_list_invoices_empty(self, service):
        """Verifica listado vacío de facturas."""
        with patch('src.api.invoices.get_async_db') as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch('src.api.invoices.get_invoices_by_org_async') as mock_query:
                mock_query.return_value = []

                invoices = await service.list_invoices("org-123")

                assert invoices == []

    @pytest.mark.asyncio
    async def test_update_invoice_status_invalid(self, service):
        """Verifica error con estado inválido."""
        with pytest.raises(ValueError) as exc_info:
            await service.update_invoice_status("org-123", "inv-123", "INVALID")

        assert "Estado inválido" in str(exc_info.value)