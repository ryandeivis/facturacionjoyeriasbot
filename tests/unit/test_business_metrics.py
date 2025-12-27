"""
Tests para el módulo de métricas de negocio.

Prueba collectors, aggregators y business metrics service.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from src.metrics.collectors import (
    MetricsCollector,
    EventType,
    MetricEvent,
    MetricCounter,
)
from src.metrics.aggregators import (
    MetricsAggregator,
    AggregationPeriod,
    AggregatedMetric,
)
from src.metrics.business import (
    BusinessMetricsService,
    OrganizationMetrics,
    InvoiceMetrics,
    BotMetrics,
)
from src.metrics.tracker import MetricsTracker


# ============================================================================
# TESTS: MetricCounter
# ============================================================================

class TestMetricCounter:
    """Tests para MetricCounter."""

    def test_init(self):
        """Test inicialización."""
        counter = MetricCounter()
        assert counter.count == 0
        assert counter.total_value == 0.0
        assert counter.success_count == 0
        assert counter.error_count == 0

    def test_increment_success(self):
        """Test incremento con éxito."""
        counter = MetricCounter()
        counter.increment(value=100.0, success=True, duration_ms=50.0)

        assert counter.count == 1
        assert counter.total_value == 100.0
        assert counter.success_count == 1
        assert counter.error_count == 0
        assert counter.total_duration_ms == 50.0

    def test_increment_error(self):
        """Test incremento con error."""
        counter = MetricCounter()
        counter.increment(value=50.0, success=False, duration_ms=100.0)

        assert counter.count == 1
        assert counter.success_count == 0
        assert counter.error_count == 1

    def test_success_rate(self):
        """Test cálculo de tasa de éxito."""
        counter = MetricCounter()
        counter.increment(success=True)
        counter.increment(success=True)
        counter.increment(success=False)

        assert counter.success_rate == pytest.approx(0.6667, rel=0.01)

    def test_avg_duration(self):
        """Test cálculo de duración promedio."""
        counter = MetricCounter()
        counter.increment(duration_ms=100.0)
        counter.increment(duration_ms=200.0)

        assert counter.avg_duration_ms == 150.0

    def test_to_dict(self):
        """Test serialización a diccionario."""
        counter = MetricCounter()
        counter.increment(value=100.0, success=True, duration_ms=50.0)

        result = counter.to_dict()

        assert result["count"] == 1
        assert result["total_value"] == 100.0
        assert result["success_rate"] == 1.0


# ============================================================================
# TESTS: MetricsCollector
# ============================================================================

class TestMetricsCollector:
    """Tests para MetricsCollector."""

    @pytest.fixture
    def collector(self):
        """Crea collector para tests."""
        return MetricsCollector(max_events=100, retention_hours=24)

    @pytest.mark.asyncio
    async def test_collect_event(self, collector):
        """Test recolección de evento."""
        await collector.collect(
            event_type=EventType.INVOICE_CREATED,
            organization_id="org-123",
            user_id=1,
            value=500000.0,
            success=True,
            duration_ms=100.0,
        )

        events = await collector.get_events(limit=10)
        assert len(events) == 1
        assert events[0].event_type == EventType.INVOICE_CREATED
        assert events[0].organization_id == "org-123"

    @pytest.mark.asyncio
    async def test_collect_updates_counters(self, collector):
        """Test que collect actualiza contadores."""
        await collector.collect(
            event_type=EventType.INVOICE_CREATED,
            organization_id="org-123",
            value=100.0,
        )
        await collector.collect(
            event_type=EventType.INVOICE_CREATED,
            organization_id="org-123",
            value=200.0,
        )

        counter = await collector.get_counter(
            EventType.INVOICE_CREATED,
            organization_id="org-123"
        )

        assert counter.count == 2
        assert counter.total_value == 300.0

    @pytest.mark.asyncio
    async def test_get_events_filtered(self, collector):
        """Test filtrado de eventos."""
        await collector.collect(
            event_type=EventType.INVOICE_CREATED,
            organization_id="org-1",
        )
        await collector.collect(
            event_type=EventType.BOT_COMMAND,
            organization_id="org-2",
        )

        events = await collector.get_events(
            event_type=EventType.INVOICE_CREATED
        )

        assert len(events) == 1
        assert events[0].event_type == EventType.INVOICE_CREATED

    @pytest.mark.asyncio
    async def test_global_counters(self, collector):
        """Test contadores globales."""
        await collector.collect(
            event_type=EventType.INVOICE_CREATED,
            organization_id="org-1",
            value=100.0,
        )
        await collector.collect(
            event_type=EventType.INVOICE_CREATED,
            organization_id="org-2",
            value=200.0,
        )

        counter = await collector.get_counter(EventType.INVOICE_CREATED)

        assert counter.count == 2
        assert counter.total_value == 300.0

    @pytest.mark.asyncio
    async def test_get_summary(self, collector):
        """Test resumen del collector."""
        await collector.collect(
            event_type=EventType.INVOICE_CREATED,
            organization_id="org-1",
        )

        summary = await collector.get_summary()

        assert summary["events_in_memory"] == 1
        assert summary["organizations_tracked"] == 1
        assert "uptime_seconds" in summary


# ============================================================================
# TESTS: MetricsAggregator
# ============================================================================

class TestMetricsAggregator:
    """Tests para MetricsAggregator."""

    @pytest.fixture
    def aggregator(self):
        """Crea aggregator para tests."""
        return MetricsAggregator()

    def test_aggregate_event(self, aggregator):
        """Test agregación de evento."""
        event = MetricEvent(
            event_type=EventType.INVOICE_CREATED,
            timestamp=datetime.utcnow(),
            organization_id="org-123",
            metadata={"value": 100.0},
        )

        result = aggregator.aggregate_event(event, AggregationPeriod.HOUR)

        assert result.count == 1
        assert result.event_type == EventType.INVOICE_CREATED.value
        assert result.period == AggregationPeriod.HOUR

    def test_aggregate_multiple_events(self, aggregator):
        """Test agregación de múltiples eventos."""
        now = datetime.utcnow()
        events = [
            MetricEvent(
                event_type=EventType.INVOICE_CREATED,
                timestamp=now,
                organization_id="org-123",
                metadata={"value": 100.0},
            ),
            MetricEvent(
                event_type=EventType.INVOICE_CREATED,
                timestamp=now,
                organization_id="org-123",
                metadata={"value": 200.0},
            ),
        ]

        results = aggregator.aggregate_events(events, AggregationPeriod.HOUR)

        # Debería haber una agregación
        assert len(results) >= 1

    def test_get_time_series(self, aggregator):
        """Test generación de serie temporal."""
        now = datetime.utcnow()
        for i in range(5):
            event = MetricEvent(
                event_type=EventType.INVOICE_CREATED,
                timestamp=now - timedelta(hours=i),
                organization_id="org-123",
                metadata={"value": float(100 * (i + 1))},
            )
            aggregator.aggregate_event(event, AggregationPeriod.HOUR)

        series = aggregator.get_time_series(
            event_type=EventType.INVOICE_CREATED.value,
            period=AggregationPeriod.HOUR,
            organization_id="org-123",
            metric="count",
        )

        assert len(series) >= 1


# ============================================================================
# TESTS: BusinessMetricsService
# ============================================================================

class TestBusinessMetricsService:
    """Tests para BusinessMetricsService."""

    @pytest.fixture
    def mock_collector(self):
        """Crea collector mock."""
        collector = AsyncMock(spec=MetricsCollector)
        collector.get_organization_counters = AsyncMock(return_value={
            EventType.INVOICE_CREATED.value: MetricCounter(),
            EventType.BOT_PHOTO.value: MetricCounter(),
        })
        collector.get_global_counters = AsyncMock(return_value={
            EventType.INVOICE_CREATED.value: MetricCounter(),
        })
        collector.get_events = AsyncMock(return_value=[])
        collector.get_summary = AsyncMock(return_value={
            "events_in_memory": 100,
            "organizations_tracked": 5,
        })
        return collector

    @pytest.fixture
    def service(self, mock_collector):
        """Crea servicio con mock."""
        return BusinessMetricsService(
            collector=mock_collector,
            aggregator=MetricsAggregator(),
        )

    @pytest.mark.asyncio
    async def test_get_organization_metrics(self, service):
        """Test obtención de métricas de organización."""
        metrics = await service.get_organization_metrics("org-123")

        assert isinstance(metrics, OrganizationMetrics)
        assert metrics.organization_id == "org-123"
        assert isinstance(metrics.invoices, InvoiceMetrics)
        assert isinstance(metrics.bot, BotMetrics)

    @pytest.mark.asyncio
    async def test_get_product_metrics(self, service):
        """Test obtención de métricas de producto."""
        metrics = await service.get_product_metrics()

        assert metrics.period_start is not None
        assert metrics.period_end is not None

    @pytest.mark.asyncio
    async def test_get_usage_metrics(self, service):
        """Test obtención de métricas de uso."""
        metrics = await service.get_usage_metrics()

        assert metrics.period_start is not None
        assert "by_hour" in metrics.to_dict()["patterns"]

    @pytest.mark.asyncio
    async def test_get_organization_health_score(self, service):
        """Test cálculo de health score."""
        score = await service.get_organization_health_score("org-123")

        assert 0 <= score <= 100

    @pytest.mark.asyncio
    async def test_get_summary(self, service):
        """Test resumen general."""
        summary = await service.get_summary()

        assert "product" in summary
        assert "usage" in summary
        assert "collector" in summary


# ============================================================================
# TESTS: MetricsTracker
# ============================================================================

class TestMetricsTracker:
    """Tests para MetricsTracker."""

    @pytest.fixture
    def mock_collector(self):
        """Crea collector mock."""
        collector = AsyncMock(spec=MetricsCollector)
        collector.collect = AsyncMock()
        return collector

    @pytest.fixture
    def tracker(self, mock_collector):
        """Crea tracker con mock."""
        return MetricsTracker(collector=mock_collector)

    @pytest.mark.asyncio
    async def test_track_invoice_created(self, tracker, mock_collector):
        """Test tracking de factura creada."""
        await tracker.track_invoice_created(
            organization_id="org-123",
            amount=500000.0,
            user_id=1,
        )

        mock_collector.collect.assert_called_once()
        call_args = mock_collector.collect.call_args
        assert call_args.kwargs["event_type"] == EventType.INVOICE_CREATED
        assert call_args.kwargs["organization_id"] == "org-123"
        assert call_args.kwargs["value"] == 500000.0

    @pytest.mark.asyncio
    async def test_track_bot_photo(self, tracker, mock_collector):
        """Test tracking de foto."""
        await tracker.track_bot_photo(
            organization_id="org-123",
            user_id=1,
            success=True,
            duration_ms=150.0,
        )

        mock_collector.collect.assert_called_once()
        call_args = mock_collector.collect.call_args
        assert call_args.kwargs["event_type"] == EventType.BOT_PHOTO
        assert call_args.kwargs["success"] is True

    @pytest.mark.asyncio
    async def test_track_ai_extraction(self, tracker, mock_collector):
        """Test tracking de extracción IA."""
        await tracker.track_ai_extraction(
            organization_id="org-123",
            user_id=1,
            extraction_type="photo",
            success=True,
            duration_ms=200.0,
            items_extracted=5,
        )

        # Debe llamar collect 2 veces (evento específico + general)
        assert mock_collector.collect.call_count == 2

    @pytest.mark.asyncio
    async def test_track_bot_error(self, tracker, mock_collector):
        """Test tracking de error."""
        await tracker.track_bot_error(
            organization_id="org-123",
            user_id=1,
            error_type="input_processing",
            error_message="Test error",
        )

        mock_collector.collect.assert_called_once()
        call_args = mock_collector.collect.call_args
        assert call_args.kwargs["event_type"] == EventType.BOT_ERROR
        assert call_args.kwargs["success"] is False

    @pytest.mark.asyncio
    async def test_track_operation_context_manager(self, tracker, mock_collector):
        """Test context manager para operaciones."""
        async with tracker.track_operation(
            "test_operation",
            organization_id="org-123",
            user_id=1,
        ):
            pass  # Operación exitosa

        mock_collector.collect.assert_called_once()
        call_args = mock_collector.collect.call_args
        assert call_args.kwargs["success"] is True
        assert call_args.kwargs["duration_ms"] is not None

    @pytest.mark.asyncio
    async def test_track_operation_with_error(self, tracker, mock_collector):
        """Test context manager con error."""
        with pytest.raises(ValueError):
            async with tracker.track_operation(
                "test_operation",
                organization_id="org-123",
            ):
                raise ValueError("Test error")

        mock_collector.collect.assert_called_once()
        call_args = mock_collector.collect.call_args
        assert call_args.kwargs["success"] is False


# ============================================================================
# TESTS: Integración
# ============================================================================

class TestMetricsIntegration:
    """Tests de integración del sistema de métricas."""

    @pytest.mark.asyncio
    async def test_full_flow(self):
        """Test flujo completo de métricas."""
        collector = MetricsCollector(max_events=1000)
        tracker = MetricsTracker(collector=collector)
        service = BusinessMetricsService(collector=collector)

        # Simular actividad
        await tracker.track_invoice_created(
            organization_id="org-123",
            amount=500000.0,
            user_id=1,
        )
        await tracker.track_bot_photo(
            organization_id="org-123",
            user_id=1,
            success=True,
            duration_ms=150.0,
        )
        await tracker.track_ai_extraction(
            organization_id="org-123",
            user_id=1,
            extraction_type="photo",
            success=True,
            duration_ms=200.0,
            items_extracted=3,
        )

        # Verificar métricas
        org_metrics = await service.get_organization_metrics("org-123")

        assert org_metrics.invoices.total_created == 1
        assert org_metrics.invoices.total_amount == 500000.0
        assert org_metrics.bot.total_photos == 1
        assert org_metrics.bot.ai_extractions_total == 1
