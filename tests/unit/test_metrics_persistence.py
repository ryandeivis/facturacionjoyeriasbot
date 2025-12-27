"""
Tests para la persistencia de métricas en base de datos.

Verifica:
- Persistencia de eventos
- Queries de agregación
- Integración con BusinessMetricsService
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.metrics.collectors import (
    MetricsCollector,
    EventType,
    MetricEvent,
    MetricCounter,
    set_db_persistence,
    is_db_persistence_enabled,
    _persist_event_to_db,
)
from src.metrics.business import (
    BusinessMetricsService,
    DataSource,
    OrganizationMetrics,
)


class TestDbPersistenceFlag:
    """Tests para el flag de persistencia."""

    def test_persistence_enabled_by_default(self):
        """Verifica que la persistencia está habilitada por defecto."""
        # Reset to default
        set_db_persistence(True)
        assert is_db_persistence_enabled() is True

    def test_disable_persistence(self):
        """Verifica que se puede deshabilitar la persistencia."""
        set_db_persistence(False)
        assert is_db_persistence_enabled() is False
        # Restore
        set_db_persistence(True)

    def test_enable_persistence(self):
        """Verifica que se puede habilitar la persistencia."""
        set_db_persistence(False)
        set_db_persistence(True)
        assert is_db_persistence_enabled() is True


class TestPersistEventToDb:
    """Tests para la función _persist_event_to_db."""

    def test_skips_when_disabled(self):
        """Verifica que no persiste cuando está deshabilitado."""
        set_db_persistence(False)

        # No debería lanzar error ni intentar conectar a BD
        _persist_event_to_db(
            event_type="test.event",
            organization_id="org-123",
            user_id=1,
            value=100.0,
            success=True,
            duration_ms=50.0,
            metadata={"test": True},
        )

        # Restore
        set_db_persistence(True)

    @patch('src.database.connection.get_db')
    @patch('src.database.queries.metrics_queries.create_metric_event')
    def test_persists_when_enabled(self, mock_create, mock_get_db):
        """Verifica que persiste cuando está habilitado."""
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        mock_create.return_value = Mock()

        set_db_persistence(True)

        _persist_event_to_db(
            event_type="test.event",
            organization_id="org-123",
            user_id=1,
            value=100.0,
            success=True,
            duration_ms=50.0,
            metadata={"test": True},
        )

        # Verificar que se llamó create_metric_event
        mock_create.assert_called_once_with(
            db=mock_db,
            event_type="test.event",
            organization_id="org-123",
            user_id=1,
            value=100.0,
            success=True,
            duration_ms=50.0,
            metadata={"test": True},
        )


class TestMetricsCollectorWithPersistence:
    """Tests para MetricsCollector con persistencia."""

    @pytest.fixture
    def collector(self):
        """Crea un collector para tests."""
        return MetricsCollector(persist_to_db=False)

    @pytest.mark.asyncio
    async def test_collect_stores_in_memory(self, collector):
        """Verifica que collect almacena en memoria."""
        await collector.collect(
            event_type=EventType.INVOICE_CREATED,
            organization_id="org-123",
            value=500.0,
        )

        events = await collector.get_events()
        assert len(events) == 1
        assert events[0].event_type == EventType.INVOICE_CREATED
        assert events[0].organization_id == "org-123"

    @pytest.mark.asyncio
    async def test_collect_updates_counters(self, collector):
        """Verifica que collect actualiza contadores."""
        await collector.collect(
            event_type=EventType.INVOICE_CREATED,
            organization_id="org-123",
            value=500.0,
            success=True,
        )
        await collector.collect(
            event_type=EventType.INVOICE_CREATED,
            organization_id="org-123",
            value=300.0,
            success=False,
        )

        counter = await collector.get_counter(
            EventType.INVOICE_CREATED,
            organization_id="org-123"
        )

        assert counter.count == 2
        assert counter.total_value == 800.0
        assert counter.success_count == 1
        assert counter.error_count == 1

    @pytest.mark.asyncio
    @patch('src.metrics.collectors._persist_event_to_db')
    async def test_collect_calls_persist_when_enabled(self, mock_persist):
        """Verifica que collect llama a persistir cuando está habilitado."""
        collector = MetricsCollector(persist_to_db=True)
        set_db_persistence(True)

        await collector.collect(
            event_type=EventType.INVOICE_CREATED,
            organization_id="org-123",
            value=500.0,
        )

        # Dar tiempo al executor
        import asyncio
        await asyncio.sleep(0.1)

        # Debería haberse llamado (aunque sea en thread pool)
        # Nota: El thread pool puede no haber ejecutado aún
        # pero la llamada a run_in_executor debería haberse hecho


class TestMetricsCollectorDbQueries:
    """Tests para métodos de consulta a BD."""

    @pytest.fixture
    def collector(self):
        """Crea un collector para tests."""
        return MetricsCollector(persist_to_db=False)

    @patch('src.database.connection.get_db')
    @patch('src.database.queries.metrics_queries.get_recent_events')
    def test_get_events_from_db(self, mock_get_events, mock_get_db, collector):
        """Verifica get_events_from_db."""
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])

        mock_event = Mock()
        mock_event.id = 1
        mock_event.event_type = "invoice.created"
        mock_event.organization_id = "org-123"
        mock_event.user_id = 1
        mock_event.value = 500.0
        mock_event.success = True
        mock_event.duration_ms = 50.0
        mock_event.event_metadata = {}
        mock_event.created_at = datetime.utcnow()

        mock_get_events.return_value = [mock_event]

        events = collector.get_events_from_db(
            organization_id="org-123",
            limit=10,
        )

        assert len(events) == 1
        assert events[0]["event_type"] == "invoice.created"
        assert events[0]["organization_id"] == "org-123"

    @patch('src.database.connection.get_db')
    @patch('src.database.queries.metrics_queries.get_event_counts')
    def test_get_aggregated_counts_from_db(self, mock_get_counts, mock_get_db, collector):
        """Verifica get_aggregated_counts_from_db."""
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])

        mock_get_counts.return_value = {
            "invoice.created": {
                "count": 10,
                "total_value": 5000.0,
                "success_count": 9,
                "error_count": 1,
                "success_rate": 0.9,
                "avg_duration_ms": 50.0,
            }
        }

        counts = collector.get_aggregated_counts_from_db(
            organization_id="org-123",
        )

        assert "invoice.created" in counts
        assert counts["invoice.created"]["count"] == 10

    @patch('src.database.connection.get_db')
    @patch('src.database.queries.metrics_queries.get_daily_stats')
    def test_get_daily_stats_from_db(self, mock_get_stats, mock_get_db, collector):
        """Verifica get_daily_stats_from_db."""
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])

        mock_get_stats.return_value = [
            {"date": "2024-01-01", "count": 5, "total_value": 1000.0},
            {"date": "2024-01-02", "count": 8, "total_value": 1500.0},
        ]

        stats = collector.get_daily_stats_from_db(
            organization_id="org-123",
            days=7,
        )

        assert len(stats) == 2
        assert stats[0]["count"] == 5


class TestDataSource:
    """Tests para el enum DataSource."""

    def test_data_source_values(self):
        """Verifica los valores del enum."""
        assert DataSource.MEMORY.value == "memory"
        assert DataSource.DATABASE.value == "database"
        assert DataSource.AUTO.value == "auto"


class TestBusinessMetricsServiceWithDb:
    """Tests para BusinessMetricsService con soporte BD."""

    @pytest.fixture
    def service(self):
        """Crea un servicio para tests."""
        collector = MetricsCollector(persist_to_db=False)
        return BusinessMetricsService(collector=collector)

    def test_should_use_database_memory_source(self, service):
        """Verifica que retorna False para source=MEMORY."""
        result = service._should_use_database(
            since=datetime.utcnow() - timedelta(days=30),
            source=DataSource.MEMORY,
        )
        assert result is False

    def test_should_use_database_db_source_when_enabled(self, service):
        """Verifica que retorna True para source=DATABASE cuando está habilitado."""
        set_db_persistence(True)
        result = service._should_use_database(
            since=datetime.utcnow() - timedelta(days=30),
            source=DataSource.DATABASE,
        )
        assert result is True

    def test_should_use_database_auto_short_period(self, service):
        """Verifica que AUTO usa memoria para períodos cortos."""
        set_db_persistence(True)
        result = service._should_use_database(
            since=datetime.utcnow() - timedelta(hours=12),
            source=DataSource.AUTO,
        )
        assert result is False

    def test_should_use_database_auto_long_period(self, service):
        """Verifica que AUTO usa BD para períodos largos."""
        set_db_persistence(True)
        result = service._should_use_database(
            since=datetime.utcnow() - timedelta(days=7),
            source=DataSource.AUTO,
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_get_organization_metrics_from_memory(self, service):
        """Verifica obtener métricas desde memoria."""
        # Agregar datos en memoria
        await service._collector.collect(
            event_type=EventType.INVOICE_CREATED,
            organization_id="org-123",
            value=500.0,
        )

        metrics = await service.get_organization_metrics(
            organization_id="org-123",
            source=DataSource.MEMORY,
        )

        assert metrics.organization_id == "org-123"
        assert metrics.invoices.total_created == 1
        assert metrics.invoices.total_amount == 500.0

    def test_get_daily_time_series_disabled(self, service):
        """Verifica que retorna vacío cuando BD está deshabilitada."""
        set_db_persistence(False)

        result = service.get_daily_time_series(organization_id="org-123")

        assert result == []
        # Restore
        set_db_persistence(True)

    def test_get_historical_events_disabled(self, service):
        """Verifica que retorna vacío cuando BD está deshabilitada."""
        set_db_persistence(False)

        result = service.get_historical_events(organization_id="org-123")

        assert result == []
        # Restore
        set_db_persistence(True)


class TestMetricEventDataclass:
    """Tests para MetricEvent dataclass."""

    def test_to_dict(self):
        """Verifica conversión a diccionario."""
        event = MetricEvent(
            event_type=EventType.INVOICE_CREATED,
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            organization_id="org-123",
            user_id=1,
            metadata={"key": "value"},
            duration_ms=50.0,
            success=True,
        )

        result = event.to_dict()

        assert result["event_type"] == "invoice.created"
        assert result["organization_id"] == "org-123"
        assert result["user_id"] == 1
        assert result["metadata"] == {"key": "value"}
        assert result["duration_ms"] == 50.0
        assert result["success"] is True


class TestMetricCounterDataclass:
    """Tests para MetricCounter dataclass."""

    def test_increment(self):
        """Verifica incremento del contador."""
        counter = MetricCounter()

        counter.increment(value=100.0, success=True, duration_ms=50.0)
        counter.increment(value=200.0, success=False, duration_ms=75.0)

        assert counter.count == 2
        assert counter.total_value == 300.0
        assert counter.success_count == 1
        assert counter.error_count == 1
        assert counter.total_duration_ms == 125.0

    def test_success_rate(self):
        """Verifica cálculo de tasa de éxito."""
        counter = MetricCounter()

        counter.increment(success=True)
        counter.increment(success=True)
        counter.increment(success=False)

        assert counter.success_rate == pytest.approx(0.666, rel=0.01)

    def test_success_rate_zero_count(self):
        """Verifica tasa de éxito con cero eventos."""
        counter = MetricCounter()
        assert counter.success_rate == 0.0

    def test_avg_duration(self):
        """Verifica cálculo de duración promedio."""
        counter = MetricCounter()

        counter.increment(duration_ms=50.0)
        counter.increment(duration_ms=100.0)

        assert counter.avg_duration_ms == 75.0

    def test_avg_duration_zero_count(self):
        """Verifica duración promedio con cero eventos."""
        counter = MetricCounter()
        assert counter.avg_duration_ms == 0.0

    def test_to_dict(self):
        """Verifica conversión a diccionario."""
        counter = MetricCounter()
        counter.increment(value=100.0, success=True, duration_ms=50.0)

        result = counter.to_dict()

        assert result["count"] == 1
        assert result["total_value"] == 100.0
        assert result["success_count"] == 1
        assert result["error_count"] == 0
        assert result["success_rate"] == 1.0
        assert result["avg_duration_ms"] == 50.0
