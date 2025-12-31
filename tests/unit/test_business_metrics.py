"""
Tests para el módulo de métricas de negocio.

Prueba collectors, aggregators y business metrics service.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

from src.metrics.collectors import (
    MetricsCollector,
    EventType,
    MetricEventData,
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
        event = MetricEventData(
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
            MetricEventData(
                event_type=EventType.INVOICE_CREATED,
                timestamp=now,
                organization_id="org-123",
                metadata={"value": 100.0},
            ),
            MetricEventData(
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
            event = MetricEventData(
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
        # Crear un contador real con datos
        invoice_counter = MetricCounter()
        invoice_counter.increment(value=500.0, success=True)

        photo_counter = MetricCounter()
        photo_counter.increment(success=True)

        collector = AsyncMock(spec=MetricsCollector)
        collector.get_organization_counters = AsyncMock(return_value={
            EventType.INVOICE_CREATED.value: invoice_counter,
            EventType.BOT_PHOTO.value: photo_counter,
        })
        collector.get_global_counters = AsyncMock(return_value={
            EventType.INVOICE_CREATED.value: invoice_counter,
        })
        collector.get_events = AsyncMock(return_value=[])
        collector.get_summary = AsyncMock(return_value={
            "events_in_memory": 100,
            "organizations_tracked": 5,
        })
        # Mock para BD (aunque no se use en estos tests)
        collector.get_organization_summary_from_db = Mock(return_value={})
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
        # Usar un ID de org único para evitar conflictos con otros tests
        import uuid
        org_id = f"test-org-{uuid.uuid4().hex[:8]}"

        # Crear nuevo collector para evitar datos residuales de otros tests
        collector = MetricsCollector(max_events=1000, persist_to_db=False)
        tracker = MetricsTracker(collector=collector)
        service = BusinessMetricsService(collector=collector)

        # Simular actividad
        await tracker.track_invoice_created(
            organization_id=org_id,
            amount=500000.0,
            user_id=1,
        )
        await tracker.track_bot_photo(
            organization_id=org_id,
            user_id=1,
            success=True,
            duration_ms=150.0,
        )
        await tracker.track_ai_extraction(
            organization_id=org_id,
            user_id=1,
            extraction_type="photo",
            success=True,
            duration_ms=200.0,
            items_extracted=3,
        )

        # Verificar métricas (forzar uso de memoria, no BD)
        from src.metrics.business import DataSource
        org_metrics = await service.get_organization_metrics(
            org_id,
            source=DataSource.MEMORY
        )

        assert org_metrics.invoices.total_created == 1
        assert org_metrics.invoices.total_amount == 500000.0
        assert org_metrics.bot.total_photos == 1
        assert org_metrics.bot.ai_extractions_total == 1


# ============================================================================
# TESTS: Métricas de Joyería (Fase 10)
# ============================================================================

class TestJewelryMetricsTracker:
    """Tests para tracking de métricas de joyería."""

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
    async def test_track_new_customer(self, tracker, mock_collector):
        """Test tracking de cliente nuevo."""
        await tracker.track_customer_new(
            organization_id="org-123",
            customer_cedula="123456789",
            customer_name="María García",
            user_id=1,
        )

        mock_collector.collect.assert_called_once()
        call_args = mock_collector.collect.call_args
        assert call_args.kwargs["event_type"] == EventType.CUSTOMER_NEW
        assert call_args.kwargs["organization_id"] == "org-123"
        assert call_args.kwargs["metadata"]["customer_cedula"] == "123456789"
        assert call_args.kwargs["metadata"]["customer_name"] == "María García"

    @pytest.mark.asyncio
    async def test_track_returning_customer(self, tracker, mock_collector):
        """Test tracking de cliente recurrente."""
        await tracker.track_customer_returning(
            organization_id="org-123",
            customer_cedula="987654321",
            customer_name="Juan Pérez",
            previous_purchases=5,
            user_id=1,
        )

        mock_collector.collect.assert_called_once()
        call_args = mock_collector.collect.call_args
        assert call_args.kwargs["event_type"] == EventType.CUSTOMER_RETURNING
        assert call_args.kwargs["value"] == 5.0  # previous_purchases como valor
        assert call_args.kwargs["metadata"]["previous_purchases"] == 5

    @pytest.mark.asyncio
    async def test_track_customer_activity_new(self, tracker, mock_collector):
        """Test track_customer_activity para cliente nuevo."""
        await tracker.track_customer_activity(
            organization_id="org-123",
            customer_cedula="111222333",
            customer_name="Ana López",
            is_new=True,
            user_id=1,
        )

        mock_collector.collect.assert_called_once()
        call_args = mock_collector.collect.call_args
        assert call_args.kwargs["event_type"] == EventType.CUSTOMER_NEW

    @pytest.mark.asyncio
    async def test_track_customer_activity_returning(self, tracker, mock_collector):
        """Test track_customer_activity para cliente recurrente."""
        await tracker.track_customer_activity(
            organization_id="org-123",
            customer_cedula="444555666",
            customer_name="Carlos Ruiz",
            is_new=False,
            previous_purchases=3,
            user_id=1,
        )

        mock_collector.collect.assert_called_once()
        call_args = mock_collector.collect.call_args
        assert call_args.kwargs["event_type"] == EventType.CUSTOMER_RETURNING

    @pytest.mark.asyncio
    async def test_track_product_sale_with_metadata(self, tracker, mock_collector):
        """Test tracking de venta de producto con metadata completa."""
        item = {
            "descripcion": "Anillo de oro 18k con diamante",
            "cantidad": 1,
            "precio_unitario": 2500000,
            "subtotal": 2500000,
            "material": "oro_18k",
            "tipo_prenda": "anillo",
            "peso_gramos": 8.5,
        }

        await tracker.track_product_sale(
            organization_id="org-123",
            item=item,
            invoice_id="inv-001",
            user_id=1,
        )

        # Debe llamar collect 3 veces: PRODUCT_SOLD, SALE_BY_MATERIAL, SALE_BY_CATEGORY
        assert mock_collector.collect.call_count == 3

        # Verificar llamadas
        calls = mock_collector.collect.call_args_list

        # Primera llamada: PRODUCT_SOLD
        product_call = calls[0]
        assert product_call.kwargs["event_type"] == EventType.PRODUCT_SOLD
        assert product_call.kwargs["value"] == 2500000
        assert product_call.kwargs["metadata"]["descripcion"] == "Anillo de oro 18k con diamante"
        assert product_call.kwargs["metadata"]["material"] == "oro_18k"
        assert product_call.kwargs["metadata"]["tipo_prenda"] == "anillo"
        assert product_call.kwargs["metadata"]["peso_gramos"] == 8.5

        # Segunda llamada: SALE_BY_MATERIAL
        material_call = calls[1]
        assert material_call.kwargs["event_type"] == EventType.SALE_BY_MATERIAL
        assert material_call.kwargs["metadata"]["material"] == "oro_18k"

        # Tercera llamada: SALE_BY_CATEGORY
        category_call = calls[2]
        assert category_call.kwargs["event_type"] == EventType.SALE_BY_CATEGORY
        assert category_call.kwargs["metadata"]["tipo_prenda"] == "anillo"

    @pytest.mark.asyncio
    async def test_track_product_sale_without_material(self, tracker, mock_collector):
        """Test tracking de venta sin material ni tipo_prenda."""
        item = {
            "descripcion": "Reparación de joya",
            "cantidad": 1,
            "precio_unitario": 50000,
            "subtotal": 50000,
        }

        await tracker.track_product_sale(
            organization_id="org-123",
            item=item,
            user_id=1,
        )

        # Solo debe llamar collect 1 vez (solo PRODUCT_SOLD)
        assert mock_collector.collect.call_count == 1
        call_args = mock_collector.collect.call_args
        assert call_args.kwargs["event_type"] == EventType.PRODUCT_SOLD

    @pytest.mark.asyncio
    async def test_track_sale_completed(self, tracker, mock_collector):
        """Test tracking de venta completada."""
        await tracker.track_sale_completed(
            organization_id="org-123",
            invoice_id="inv-001",
            total_amount=3500000,
            items_count=3,
            customer_cedula="123456789",
            user_id=1,
        )

        # Debe llamar collect 2 veces: SALE_COMPLETED y SELLER_SALE
        assert mock_collector.collect.call_count == 2

        calls = mock_collector.collect.call_args_list

        # Primera llamada: SALE_COMPLETED
        sale_call = calls[0]
        assert sale_call.kwargs["event_type"] == EventType.SALE_COMPLETED
        assert sale_call.kwargs["value"] == 3500000
        assert sale_call.kwargs["metadata"]["items_count"] == 3
        assert sale_call.kwargs["metadata"]["customer_cedula"] == "123456789"

        # Segunda llamada: SELLER_SALE
        seller_call = calls[1]
        assert seller_call.kwargs["event_type"] == EventType.SELLER_SALE
        assert seller_call.kwargs["user_id"] == 1

    @pytest.mark.asyncio
    async def test_track_full_sale(self, tracker, mock_collector):
        """Test tracking de venta completa con todos los componentes."""
        items = [
            {
                "descripcion": "Cadena de plata 925",
                "cantidad": 1,
                "precio_unitario": 150000,
                "subtotal": 150000,
                "material": "plata_925",
                "tipo_prenda": "cadena",
            },
            {
                "descripcion": "Aretes de oro 14k",
                "cantidad": 2,
                "precio_unitario": 200000,
                "subtotal": 400000,
                "material": "oro_14k",
                "tipo_prenda": "aretes",
            },
        ]
        customer_data = {
            "nombre": "Laura Martínez",
            "cedula": "555666777",
        }

        await tracker.track_full_sale(
            organization_id="org-123",
            invoice_id="inv-002",
            items=items,
            total_amount=550000,
            customer_data=customer_data,
            is_new_customer=True,
            user_id=1,
        )

        # Conteo esperado:
        # - 1 CUSTOMER_NEW
        # - 3 por item1 (PRODUCT_SOLD + SALE_BY_MATERIAL + SALE_BY_CATEGORY)
        # - 3 por item2 (PRODUCT_SOLD + SALE_BY_MATERIAL + SALE_BY_CATEGORY)
        # - 2 por venta completada (SALE_COMPLETED + SELLER_SALE)
        # Total: 1 + 3 + 3 + 2 = 9
        assert mock_collector.collect.call_count == 9

        # Verificar que se llamaron los eventos correctos
        event_types = [c.kwargs["event_type"] for c in mock_collector.collect.call_args_list]
        assert EventType.CUSTOMER_NEW in event_types
        assert event_types.count(EventType.PRODUCT_SOLD) == 2
        assert event_types.count(EventType.SALE_BY_MATERIAL) == 2
        assert event_types.count(EventType.SALE_BY_CATEGORY) == 2
        assert EventType.SALE_COMPLETED in event_types
        assert EventType.SELLER_SALE in event_types


class TestJewelryMetricsService:
    """Tests para el servicio de métricas de joyería."""

    @pytest.fixture
    def org_id(self):
        """ID de organización único para tests."""
        import uuid
        return f"org-jewelry-{uuid.uuid4().hex[:8]}"

    @pytest.mark.asyncio
    async def test_get_top_products(self, org_id):
        """Test obtención de productos más vendidos."""
        # Crear collector real
        collector = MetricsCollector(max_events=1000, persist_to_db=False)
        tracker = MetricsTracker(collector=collector)
        service = BusinessMetricsService(collector=collector)

        # Simular ventas de productos
        items = [
            {"descripcion": "Anillo oro", "cantidad": 5, "precio_unitario": 500000, "material": "oro_18k"},
            {"descripcion": "Cadena plata", "cantidad": 10, "precio_unitario": 100000, "material": "plata_925"},
            {"descripcion": "Anillo oro", "cantidad": 3, "precio_unitario": 500000, "material": "oro_18k"},
        ]

        for item in items:
            await tracker.track_product_sale(
                organization_id=org_id,
                item=item,
                user_id=1,
            )

        # Obtener top products
        from src.metrics.business import TopProduct
        top_products = await service.get_top_products(org_id, limit=5)

        assert len(top_products) >= 1
        assert isinstance(top_products[0], TopProduct)

        # Cadena plata debería ser el más vendido (10 unidades)
        # o Anillo oro (5 + 3 = 8 unidades)
        top_desc = [p.descripcion for p in top_products]
        assert "Cadena plata" in top_desc or "Anillo oro" in top_desc

    @pytest.mark.asyncio
    async def test_get_customer_stats(self, org_id):
        """Test estadísticas de cliente."""
        collector = MetricsCollector(max_events=1000, persist_to_db=False)
        tracker = MetricsTracker(collector=collector)
        service = BusinessMetricsService(collector=collector)

        customer_cedula = "111222333"

        # Simular múltiples compras del cliente
        for i in range(3):
            await tracker.track_sale_completed(
                organization_id=org_id,
                invoice_id=f"inv-{i}",
                total_amount=500000 * (i + 1),
                items_count=i + 1,
                customer_cedula=customer_cedula,
                user_id=1,
            )

        # Obtener estadísticas
        from src.metrics.business import CustomerStats
        stats = await service.get_customer_stats(org_id, customer_cedula)

        assert isinstance(stats, CustomerStats)
        assert stats.customer_cedula == customer_cedula
        assert stats.total_purchases == 3

    @pytest.mark.asyncio
    async def test_get_seller_performance(self, org_id):
        """Test rendimiento de vendedores."""
        collector = MetricsCollector(max_events=1000, persist_to_db=False)
        tracker = MetricsTracker(collector=collector)
        service = BusinessMetricsService(collector=collector)

        # Simular ventas de diferentes vendedores
        for user_id in [1, 2, 1, 1, 2]:  # User 1: 3 ventas, User 2: 2 ventas
            await tracker.track_sale_completed(
                organization_id=org_id,
                invoice_id=f"inv-{user_id}-{id(user_id)}",
                total_amount=100000,
                items_count=1,
                user_id=user_id,
            )

        # Obtener rendimiento
        from src.metrics.business import SellerPerformance
        seller_perf = await service.get_seller_performance(org_id)

        assert len(seller_perf) >= 1
        assert isinstance(seller_perf[0], SellerPerformance)

        # El vendedor con más ventas debería estar primero
        if len(seller_perf) >= 2:
            assert seller_perf[0].total_sales >= seller_perf[1].total_sales

    @pytest.mark.asyncio
    async def test_get_sales_by_material(self, org_id):
        """Test ventas agrupadas por material."""
        collector = MetricsCollector(max_events=1000, persist_to_db=False)
        tracker = MetricsTracker(collector=collector)
        service = BusinessMetricsService(collector=collector)

        # Simular ventas por material
        items = [
            {"descripcion": "Anillo 1", "cantidad": 2, "precio_unitario": 500000, "material": "oro_18k"},
            {"descripcion": "Anillo 2", "cantidad": 1, "precio_unitario": 600000, "material": "oro_18k"},
            {"descripcion": "Cadena", "cantidad": 3, "precio_unitario": 100000, "material": "plata_925"},
        ]

        for item in items:
            await tracker.track_product_sale(
                organization_id=org_id,
                item=item,
                user_id=1,
            )

        # Obtener ventas por material
        sales_by_material = await service.get_sales_by_material(org_id)

        assert isinstance(sales_by_material, dict)
        assert "oro_18k" in sales_by_material
        assert "plata_925" in sales_by_material
        assert sales_by_material["oro_18k"]["cantidad"] == 3  # 2 + 1
        assert sales_by_material["plata_925"]["cantidad"] == 3

    @pytest.mark.asyncio
    async def test_get_sales_by_category(self, org_id):
        """Test ventas agrupadas por categoría."""
        collector = MetricsCollector(max_events=1000, persist_to_db=False)
        tracker = MetricsTracker(collector=collector)
        service = BusinessMetricsService(collector=collector)

        # Simular ventas por categoría
        items = [
            {"descripcion": "Anillo 1", "cantidad": 2, "tipo_prenda": "anillo"},
            {"descripcion": "Anillo 2", "cantidad": 1, "tipo_prenda": "anillo"},
            {"descripcion": "Cadena", "cantidad": 1, "tipo_prenda": "cadena"},
            {"descripcion": "Aretes", "cantidad": 3, "tipo_prenda": "aretes"},
        ]

        for item in items:
            await tracker.track_product_sale(
                organization_id=org_id,
                item=item,
                user_id=1,
            )

        # Obtener ventas por categoría
        sales_by_category = await service.get_sales_by_category(org_id)

        assert isinstance(sales_by_category, dict)
        assert "anillo" in sales_by_category
        assert "cadena" in sales_by_category
        assert "aretes" in sales_by_category
        assert sales_by_category["anillo"]["cantidad"] == 3  # 2 + 1
        assert sales_by_category["aretes"]["cantidad"] == 3

    @pytest.mark.asyncio
    async def test_get_jewelry_metrics(self, org_id):
        """Test obtención de métricas completas de joyería."""
        collector = MetricsCollector(max_events=1000, persist_to_db=False)
        tracker = MetricsTracker(collector=collector)
        service = BusinessMetricsService(collector=collector)

        # Simular actividad completa
        # Cliente nuevo
        await tracker.track_customer_new(
            organization_id=org_id,
            customer_cedula="111111111",
            customer_name="Cliente Nuevo",
            user_id=1,
        )

        # Cliente recurrente
        await tracker.track_customer_returning(
            organization_id=org_id,
            customer_cedula="222222222",
            customer_name="Cliente Recurrente",
            previous_purchases=5,
            user_id=1,
        )

        # Venta de productos
        item = {
            "descripcion": "Anillo oro",
            "cantidad": 2,
            "precio_unitario": 500000,
            "material": "oro_18k",
            "tipo_prenda": "anillo",
        }
        await tracker.track_product_sale(
            organization_id=org_id,
            item=item,
            user_id=1,
        )

        # Obtener métricas de joyería
        from src.metrics.business import JewelryMetrics
        metrics = await service.get_jewelry_metrics(org_id)

        assert isinstance(metrics, JewelryMetrics)
        assert metrics.new_customers == 1
        assert metrics.returning_customers == 1
        assert metrics.total_customers_served == 2
        assert metrics.total_items_sold >= 1

        # Verificar serialización
        metrics_dict = metrics.to_dict()
        assert "customers" in metrics_dict
        assert "products" in metrics_dict
        assert "by_material" in metrics_dict
        assert "by_category" in metrics_dict
        assert "sellers" in metrics_dict


class TestJewelryDataClasses:
    """Tests para las data classes de métricas de joyería."""

    def test_customer_stats_to_dict(self):
        """Test serialización de CustomerStats."""
        from src.metrics.business import CustomerStats
        stats = CustomerStats(
            customer_cedula="123456789",
            customer_name="Test Customer",
            total_purchases=5,
            total_spent=2500000.55,
            avg_purchase_amount=500000.11,
            first_purchase=datetime(2024, 1, 1),
            last_purchase=datetime(2024, 12, 30),
            favorite_material="oro_18k",
            favorite_category="anillo",
        )

        result = stats.to_dict()

        assert result["customer_cedula"] == "123456789"
        assert result["customer_name"] == "Test Customer"
        assert result["total_purchases"] == 5
        assert result["total_spent"] == 2500000.55
        assert result["avg_purchase_amount"] == 500000.11
        assert result["first_purchase"] == "2024-01-01T00:00:00"
        assert result["last_purchase"] == "2024-12-30T00:00:00"
        assert result["favorite_material"] == "oro_18k"
        assert result["favorite_category"] == "anillo"

    def test_seller_performance_to_dict(self):
        """Test serialización de SellerPerformance."""
        from src.metrics.business import SellerPerformance
        perf = SellerPerformance(
            user_id=1,
            user_name="Vendedor Test",
            total_sales=10,
            total_amount=5000000.99,
            avg_sale_amount=500000.1,
            items_sold=25,
            new_customers=3,
            returning_customers=7,
        )

        result = perf.to_dict()

        assert result["user_id"] == 1
        assert result["user_name"] == "Vendedor Test"
        assert result["total_sales"] == 10
        assert result["total_amount"] == 5000000.99
        assert result["avg_sale_amount"] == 500000.1
        assert result["items_sold"] == 25
        assert result["new_customers"] == 3
        assert result["returning_customers"] == 7

    def test_top_product_to_dict(self):
        """Test serialización de TopProduct."""
        from src.metrics.business import TopProduct
        product = TopProduct(
            descripcion="Anillo de compromiso oro 18k",
            cantidad_vendida=50,
            total_ingresos=25000000.5,
            material="oro_18k",
            tipo_prenda="anillo",
        )

        result = product.to_dict()

        assert result["descripcion"] == "Anillo de compromiso oro 18k"
        assert result["cantidad_vendida"] == 50
        assert result["total_ingresos"] == 25000000.5
        assert result["material"] == "oro_18k"
        assert result["tipo_prenda"] == "anillo"

    def test_jewelry_metrics_to_dict(self):
        """Test serialización de JewelryMetrics."""
        from src.metrics.business import JewelryMetrics, TopProduct, SellerPerformance
        metrics = JewelryMetrics(
            period_start=datetime(2024, 12, 1),
            period_end=datetime(2024, 12, 30),
            new_customers=10,
            returning_customers=25,
            total_customers_served=35,
            total_items_sold=150,
            top_products=[
                TopProduct(descripcion="Anillo", cantidad_vendida=50, total_ingresos=25000000),
            ],
            sales_by_material={"oro_18k": 15000000, "plata_925": 5000000},
            quantity_by_material={"oro_18k": 80, "plata_925": 70},
            sales_by_category={"anillo": 10000000, "cadena": 5000000},
            quantity_by_category={"anillo": 60, "cadena": 40},
            seller_performance=[
                SellerPerformance(user_id=1, total_sales=30),
            ],
        )

        result = metrics.to_dict()

        assert "period" in result
        assert result["period"]["start"] == "2024-12-01T00:00:00"
        assert result["customers"]["new"] == 10
        assert result["customers"]["returning"] == 25
        assert result["customers"]["total_served"] == 35
        assert result["products"]["total_items_sold"] == 150
        assert len(result["products"]["top_products"]) == 1
        assert result["by_material"]["sales"]["oro_18k"] == 15000000
        assert result["by_category"]["quantity"]["anillo"] == 60
        assert len(result["sellers"]) == 1
