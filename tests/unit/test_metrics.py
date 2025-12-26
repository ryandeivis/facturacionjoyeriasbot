"""
Tests para el sistema de métricas.
"""

import pytest
import time

from src.utils.metrics import (
    Counter,
    Gauge,
    Histogram,
    Summary,
    MetricsRegistry,
    Timer,
    timed,
    counted,
    get_metrics,
    get_prometheus_metrics,
)


class TestCounter:
    """Tests para Counter."""

    def test_counter_init(self):
        """Verifica inicialización."""
        counter = Counter("test_counter", "Test description")
        assert counter.name == "test_counter"
        assert counter.get() == 0.0

    def test_counter_inc(self):
        """Verifica incremento."""
        counter = Counter("test_counter")
        counter.inc()
        assert counter.get() == 1.0

    def test_counter_inc_value(self):
        """Verifica incremento con valor."""
        counter = Counter("test_counter")
        counter.inc(5.0)
        assert counter.get() == 5.0

    def test_counter_inc_negative_raises(self):
        """Verifica que no permite valores negativos."""
        counter = Counter("test_counter")
        with pytest.raises(ValueError):
            counter.inc(-1.0)

    def test_counter_with_labels(self):
        """Verifica contador con labels."""
        counter = Counter("test_counter")
        counter.inc(labels={"status": "success"})
        counter.inc(labels={"status": "error"})
        counter.inc(labels={"status": "success"})

        assert counter.get({"status": "success"}) == 2.0
        assert counter.get({"status": "error"}) == 1.0

    def test_counter_get_all(self):
        """Verifica obtener todos los valores."""
        counter = Counter("test_counter")
        counter.inc(labels={"type": "a"})
        counter.inc(labels={"type": "b"})

        all_values = counter.get_all()
        assert len(all_values) == 2


class TestGauge:
    """Tests para Gauge."""

    def test_gauge_init(self):
        """Verifica inicialización."""
        gauge = Gauge("test_gauge", "Test description")
        assert gauge.name == "test_gauge"
        assert gauge.get() == 0.0

    def test_gauge_set(self):
        """Verifica set."""
        gauge = Gauge("test_gauge")
        gauge.set(42.0)
        assert gauge.get() == 42.0

    def test_gauge_inc_dec(self):
        """Verifica incremento y decremento."""
        gauge = Gauge("test_gauge")
        gauge.set(10.0)
        gauge.inc(5.0)
        assert gauge.get() == 15.0

        gauge.dec(3.0)
        assert gauge.get() == 12.0

    def test_gauge_with_labels(self):
        """Verifica gauge con labels."""
        gauge = Gauge("test_gauge")
        gauge.set(10.0, {"region": "us"})
        gauge.set(20.0, {"region": "eu"})

        assert gauge.get({"region": "us"}) == 10.0
        assert gauge.get({"region": "eu"}) == 20.0


class TestHistogram:
    """Tests para Histogram."""

    def test_histogram_init(self):
        """Verifica inicialización."""
        histogram = Histogram("test_histogram", "Test description")
        assert histogram.name == "test_histogram"
        assert histogram.buckets == Histogram.DEFAULT_BUCKETS

    def test_histogram_custom_buckets(self):
        """Verifica buckets personalizados."""
        buckets = (0.1, 0.5, 1.0, 5.0)
        histogram = Histogram("test_histogram", buckets=buckets)
        assert histogram.buckets == buckets

    def test_histogram_observe(self):
        """Verifica observe."""
        histogram = Histogram("test_histogram")
        histogram.observe(0.5)
        histogram.observe(1.0)
        histogram.observe(2.0)

        stats = histogram.get_stats()
        assert stats["count"] == 3
        assert stats["sum"] == 3.5
        assert stats["avg"] == pytest.approx(1.166, rel=0.01)

    def test_histogram_percentiles(self):
        """Verifica cálculo de percentiles."""
        histogram = Histogram("test_histogram", buckets=(0.1, 0.5, 1.0, 2.0, 5.0))

        # Agregar valores
        for _ in range(50):
            histogram.observe(0.3)
        for _ in range(30):
            histogram.observe(0.8)
        for _ in range(20):
            histogram.observe(1.5)

        p50 = histogram.get_percentile(0.50)
        p90 = histogram.get_percentile(0.90)

        assert p50 is not None
        assert p90 is not None


class TestSummary:
    """Tests para Summary."""

    def test_summary_init(self):
        """Verifica inicialización."""
        summary = Summary("test_summary", "Test description")
        assert summary.name == "test_summary"

    def test_summary_observe(self):
        """Verifica observe."""
        summary = Summary("test_summary")
        summary.observe(1.0)
        summary.observe(2.0)
        summary.observe(3.0)

        stats = summary.get_stats()
        assert stats["count"] == 3
        assert stats["sum"] == 6.0
        assert stats["min"] == 1.0
        assert stats["max"] == 3.0

    def test_summary_max_samples(self):
        """Verifica límite de muestras."""
        summary = Summary("test_summary", max_samples=10)

        # Agregar más del límite
        for i in range(20):
            summary.observe(float(i))

        stats = summary.get_stats()
        assert stats["count"] == 10  # Solo mantiene 10


class TestMetricsRegistry:
    """Tests para MetricsRegistry."""

    def test_registry_counter(self):
        """Verifica creación de counter via registry."""
        registry = MetricsRegistry()
        counter = registry.counter("test_counter", "Test")

        assert isinstance(counter, Counter)
        assert counter.name == "test_counter"

    def test_registry_gauge(self):
        """Verifica creación de gauge via registry."""
        registry = MetricsRegistry()
        gauge = registry.gauge("test_gauge", "Test")

        assert isinstance(gauge, Gauge)

    def test_registry_histogram(self):
        """Verifica creación de histogram via registry."""
        registry = MetricsRegistry()
        histogram = registry.histogram("test_histogram", "Test")

        assert isinstance(histogram, Histogram)

    def test_registry_summary(self):
        """Verifica creación de summary via registry."""
        registry = MetricsRegistry()
        summary = registry.summary("test_summary", "Test")

        assert isinstance(summary, Summary)

    def test_registry_reuses_metric(self):
        """Verifica que reutiliza métricas existentes."""
        registry = MetricsRegistry()
        counter1 = registry.counter("test_counter")
        counter1.inc()

        counter2 = registry.counter("test_counter")

        assert counter1 is counter2
        assert counter2.get() == 1.0

    def test_registry_get_all(self):
        """Verifica obtener todas las métricas."""
        registry = MetricsRegistry()
        registry.counter("counter1").inc()
        registry.gauge("gauge1").set(42)

        all_metrics = registry.get_all()

        assert "counter1" in all_metrics
        assert "gauge1" in all_metrics

    def test_registry_to_prometheus(self):
        """Verifica export a formato Prometheus."""
        registry = MetricsRegistry()
        counter = registry.counter("test_requests_total", "Total requests")
        counter.inc()

        prometheus_output = registry.to_prometheus()

        assert "test_requests_total" in prometheus_output
        assert "# TYPE test_requests_total counter" in prometheus_output


class TestTimer:
    """Tests para Timer context manager."""

    def test_timer_measures_time(self):
        """Verifica que mide tiempo correctamente."""
        histogram = Histogram("test_duration")

        with Timer(histogram) as timer:
            time.sleep(0.1)

        assert timer.elapsed >= 0.1
        stats = histogram.get_stats()
        assert stats["count"] == 1
        assert stats["sum"] >= 0.1


class TestDecorators:
    """Tests para decoradores de métricas."""

    def test_timed_decorator_sync(self):
        """Verifica decorador @timed con función sync."""
        histogram = Histogram("test_timed")

        @timed(histogram)
        def slow_function():
            time.sleep(0.05)
            return "done"

        result = slow_function()

        assert result == "done"
        stats = histogram.get_stats()
        assert stats["count"] == 1
        assert stats["sum"] >= 0.05

    @pytest.mark.asyncio
    async def test_timed_decorator_async(self):
        """Verifica decorador @timed con función async."""
        import asyncio
        histogram = Histogram("test_timed_async")

        @timed(histogram)
        async def slow_async_function():
            await asyncio.sleep(0.05)
            return "async done"

        result = await slow_async_function()

        assert result == "async done"
        stats = histogram.get_stats()
        assert stats["count"] == 1

    def test_counted_decorator_sync(self):
        """Verifica decorador @counted con función sync."""
        counter = Counter("test_counted")

        @counted(counter)
        def my_function():
            return "counted"

        my_function()
        my_function()
        my_function()

        assert counter.get() == 3

    @pytest.mark.asyncio
    async def test_counted_decorator_async(self):
        """Verifica decorador @counted con función async."""
        counter = Counter("test_counted_async")

        @counted(counter)
        async def my_async_function():
            return "async counted"

        await my_async_function()
        await my_async_function()

        assert counter.get() == 2


class TestGlobalFunctions:
    """Tests para funciones globales de métricas."""

    def test_get_metrics(self):
        """Verifica get_metrics retorna diccionario."""
        metrics = get_metrics()
        assert isinstance(metrics, dict)

    def test_get_prometheus_metrics(self):
        """Verifica get_prometheus_metrics retorna string."""
        prometheus = get_prometheus_metrics()
        assert isinstance(prometheus, str)