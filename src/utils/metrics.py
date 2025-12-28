"""
Metrics Collection

Sistema de métricas para monitoreo de la aplicación.
Compatible con Prometheus cuando está disponible.
"""

import time
from datetime import datetime
from typing import Dict, Any, Optional, Callable, cast, Union
from dataclasses import dataclass, field
from collections import defaultdict
from functools import wraps
from threading import Lock

from src.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# METRIC TYPES
# ============================================================================

@dataclass
class MetricValue:
    """Valor de una métrica con metadata."""
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    labels: Dict[str, str] = field(default_factory=dict)


class Counter:
    """
    Contador que solo puede incrementar.

    Uso:
        invoices_created = Counter("invoices_created_total", "Total de facturas creadas")
        invoices_created.inc()
        invoices_created.inc(labels={"org_id": "org-123", "status": "success"})
    """

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self._values: Dict[str, float] = defaultdict(float)
        self._lock = Lock()

    def _labels_key(self, labels: Dict[str, str] = None) -> str:
        """Genera una clave única para un conjunto de labels."""
        if not labels:
            return ""
        return ",".join(f"{k}={v}" for k, v in sorted(labels.items()))

    def inc(self, value: float = 1.0, labels: Dict[str, str] = None) -> None:
        """Incrementa el contador."""
        if value < 0:
            raise ValueError("Counter solo puede incrementar")

        key = self._labels_key(labels)
        with self._lock:
            self._values[key] += value

    def get(self, labels: Dict[str, str] = None) -> float:
        """Obtiene el valor actual."""
        key = self._labels_key(labels)
        return self._values.get(key, 0.0)

    def get_all(self) -> Dict[str, float]:
        """Obtiene todos los valores."""
        return dict(self._values)


class Gauge:
    """
    Medidor que puede subir y bajar.

    Uso:
        active_users = Gauge("active_users", "Usuarios activos")
        active_users.set(10)
        active_users.inc()
        active_users.dec()
    """

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self._values: Dict[str, float] = defaultdict(float)
        self._lock = Lock()

    def _labels_key(self, labels: Dict[str, str] = None) -> str:
        if not labels:
            return ""
        return ",".join(f"{k}={v}" for k, v in sorted(labels.items()))

    def set(self, value: float, labels: Dict[str, str] = None) -> None:
        """Establece el valor."""
        key = self._labels_key(labels)
        with self._lock:
            self._values[key] = value

    def inc(self, value: float = 1.0, labels: Dict[str, str] = None) -> None:
        """Incrementa el valor."""
        key = self._labels_key(labels)
        with self._lock:
            self._values[key] += value

    def dec(self, value: float = 1.0, labels: Dict[str, str] = None) -> None:
        """Decrementa el valor."""
        key = self._labels_key(labels)
        with self._lock:
            self._values[key] -= value

    def get(self, labels: Dict[str, str] = None) -> float:
        """Obtiene el valor actual."""
        key = self._labels_key(labels)
        return self._values.get(key, 0.0)

    def get_all(self) -> Dict[str, float]:
        """Obtiene todos los valores."""
        return dict(self._values)


class Histogram:
    """
    Histograma para distribuciones de valores.

    Uso:
        request_duration = Histogram("request_duration_seconds", "Duración de requests")
        request_duration.observe(0.5)
    """

    DEFAULT_BUCKETS = (
        0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0
    )

    def __init__(
        self,
        name: str,
        description: str = "",
        buckets: tuple = None
    ):
        self.name = name
        self.description = description
        self.buckets = buckets or self.DEFAULT_BUCKETS

        self._counts: Dict[str, Dict[float, int]] = defaultdict(lambda: defaultdict(int))
        self._sums: Dict[str, float] = defaultdict(float)
        self._total_counts: Dict[str, int] = defaultdict(int)
        self._lock = Lock()

    def _labels_key(self, labels: Dict[str, str] = None) -> str:
        if not labels:
            return ""
        return ",".join(f"{k}={v}" for k, v in sorted(labels.items()))

    def observe(self, value: float, labels: Dict[str, str] = None) -> None:
        """Registra una observación."""
        key = self._labels_key(labels)
        with self._lock:
            self._sums[key] += value
            self._total_counts[key] += 1

            for bucket in self.buckets:
                if value <= bucket:
                    self._counts[key][bucket] += 1

    def get_percentile(self, percentile: float, labels: Dict[str, str] = None) -> Optional[float]:
        """
        Estima un percentil basado en los buckets.

        Nota: Esta es una aproximación ya que solo tenemos los buckets.
        """
        key = self._labels_key(labels)
        total = self._total_counts.get(key, 0)

        if total == 0:
            return None

        target_count = total * percentile
        accumulated = 0

        for bucket in sorted(self.buckets):
            accumulated += self._counts[key].get(bucket, 0)
            if accumulated >= target_count:
                return float(bucket)

        return float(self.buckets[-1])

    def get_stats(self, labels: Dict[str, str] = None) -> Dict[str, Any]:
        """Obtiene estadísticas del histograma."""
        key = self._labels_key(labels)
        total = self._total_counts.get(key, 0)
        total_sum = self._sums.get(key, 0.0)

        return {
            "count": total,
            "sum": total_sum,
            "avg": total_sum / total if total > 0 else 0.0,
            "p50": self.get_percentile(0.50, labels),
            "p90": self.get_percentile(0.90, labels),
            "p99": self.get_percentile(0.99, labels),
        }


class Summary:
    """
    Resumen con estadísticas básicas.

    Similar a Histogram pero sin buckets predefinidos.
    """

    def __init__(self, name: str, description: str = "", max_samples: int = 1000):
        self.name = name
        self.description = description
        self.max_samples = max_samples

        self._samples: Dict[str, list] = defaultdict(list)
        self._lock = Lock()

    def _labels_key(self, labels: Dict[str, str] = None) -> str:
        if not labels:
            return ""
        return ",".join(f"{k}={v}" for k, v in sorted(labels.items()))

    def observe(self, value: float, labels: Dict[str, str] = None) -> None:
        """Registra una observación."""
        key = self._labels_key(labels)
        with self._lock:
            samples = self._samples[key]
            samples.append(value)

            # Mantener solo los últimos max_samples
            if len(samples) > self.max_samples:
                self._samples[key] = samples[-self.max_samples:]

    def get_stats(self, labels: Dict[str, str] = None) -> Dict[str, Any]:
        """Obtiene estadísticas."""
        key = self._labels_key(labels)
        samples = self._samples.get(key, [])

        if not samples:
            return {
                "count": 0,
                "sum": 0.0,
                "avg": 0.0,
                "min": None,
                "max": None,
            }

        sorted_samples = sorted(samples)
        count = len(sorted_samples)

        return {
            "count": count,
            "sum": sum(sorted_samples),
            "avg": sum(sorted_samples) / count,
            "min": sorted_samples[0],
            "max": sorted_samples[-1],
            "p50": sorted_samples[int(count * 0.50)],
            "p90": sorted_samples[int(count * 0.90)],
            "p99": sorted_samples[min(int(count * 0.99), count - 1)],
        }


# ============================================================================
# METRICS REGISTRY
# ============================================================================

class MetricsRegistry:
    """
    Registro central de métricas.

    Almacena y gestiona todas las métricas de la aplicación.
    """

    def __init__(self):
        self._metrics: Dict[str, Any] = {}
        self._lock = Lock()

    def register(self, metric: Any) -> Any:
        """Registra una métrica."""
        with self._lock:
            if metric.name in self._metrics:
                return self._metrics[metric.name]
            self._metrics[metric.name] = metric
            return metric

    def counter(self, name: str, description: str = "") -> Counter:
        """Crea o obtiene un Counter."""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = Counter(name, description)
            return cast(Counter, self._metrics[name])

    def gauge(self, name: str, description: str = "") -> Gauge:
        """Crea o obtiene un Gauge."""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = Gauge(name, description)
            return cast(Gauge, self._metrics[name])

    def histogram(self, name: str, description: str = "", buckets: tuple = None) -> Histogram:
        """Crea o obtiene un Histogram."""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = Histogram(name, description, buckets)
            return cast(Histogram, self._metrics[name])

    def summary(self, name: str, description: str = "") -> Summary:
        """Crea o obtiene un Summary."""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = Summary(name, description)
            return cast(Summary, self._metrics[name])

    def get_all(self) -> Dict[str, Any]:
        """Obtiene todas las métricas."""
        result = {}
        for name, metric in self._metrics.items():
            if isinstance(metric, (Counter, Gauge)):
                result[name] = metric.get_all()
            elif isinstance(metric, (Histogram, Summary)):
                result[name] = metric.get_stats()
        return result

    def to_prometheus(self) -> str:
        """
        Exporta métricas en formato Prometheus.

        Returns:
            String en formato Prometheus exposition
        """
        lines = []

        for name, metric in self._metrics.items():
            if isinstance(metric, Counter):
                lines.append(f"# HELP {name} {metric.description}")
                lines.append(f"# TYPE {name} counter")
                for labels_key, value in metric.get_all().items():
                    if labels_key:
                        lines.append(f"{name}{{{labels_key}}} {value}")
                    else:
                        lines.append(f"{name} {value}")

            elif isinstance(metric, Gauge):
                lines.append(f"# HELP {name} {metric.description}")
                lines.append(f"# TYPE {name} gauge")
                for labels_key, value in metric.get_all().items():
                    if labels_key:
                        lines.append(f"{name}{{{labels_key}}} {value}")
                    else:
                        lines.append(f"{name} {value}")

            elif isinstance(metric, Histogram):
                lines.append(f"# HELP {name} {metric.description}")
                lines.append(f"# TYPE {name} histogram")
                stats = metric.get_stats()
                lines.append(f"{name}_count {stats['count']}")
                lines.append(f"{name}_sum {stats['sum']}")

        return "\n".join(lines)


# ============================================================================
# GLOBAL REGISTRY AND METRICS
# ============================================================================

registry = MetricsRegistry()

# Métricas de la aplicación
invoices_created = registry.counter(
    "invoices_created_total",
    "Total de facturas creadas"
)

invoices_processed = registry.counter(
    "invoices_processed_total",
    "Total de facturas procesadas por N8N"
)

active_users = registry.gauge(
    "active_users",
    "Usuarios actualmente activos"
)

request_duration = registry.histogram(
    "request_duration_seconds",
    "Duración de requests en segundos"
)

n8n_requests = registry.counter(
    "n8n_requests_total",
    "Total de requests a N8N"
)

db_queries = registry.counter(
    "db_queries_total",
    "Total de queries a la base de datos"
)

errors = registry.counter(
    "errors_total",
    "Total de errores"
)

bot_messages = registry.counter(
    "bot_messages_total",
    "Total de mensajes procesados por el bot"
)


# ============================================================================
# DECORATORS
# ============================================================================

def timed(metric: Histogram = None, labels: Dict[str, str] = None):
    """
    Decorador para medir tiempo de ejecución.

    Uso:
        @timed(request_duration, {"endpoint": "create_invoice"})
        async def create_invoice():
            ...
    """
    def decorator(func: Callable) -> Callable:
        metric_to_use = metric or request_duration

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            try:
                return await func(*args, **kwargs)
            finally:
                duration = time.time() - start
                metric_to_use.observe(duration, labels)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.time() - start
                metric_to_use.observe(duration, labels)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def counted(metric: Counter = None, labels: Dict[str, str] = None):
    """
    Decorador para contar llamadas.

    Uso:
        @counted(invoices_created, {"type": "manual"})
        def create_invoice():
            ...
    """
    def decorator(func: Callable) -> Callable:
        metric_to_use = metric or registry.counter(f"{func.__name__}_calls_total")

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            metric_to_use.inc(labels=labels)
            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            metric_to_use.inc(labels=labels)
            return result

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# ============================================================================
# CONTEXT MANAGER
# ============================================================================

class Timer:
    """
    Context manager para medir tiempo.

    Uso:
        with Timer(request_duration, {"operation": "db_query"}):
            # código a medir
            ...
    """

    def __init__(
        self,
        histogram: Histogram = None,
        labels: Dict[str, str] = None
    ):
        self.histogram = histogram or request_duration
        self.labels = labels
        self._start: Optional[float] = None

    def __enter__(self):
        self._start = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self._start
        self.histogram.observe(duration, self.labels)
        return False

    @property
    def elapsed(self) -> float:
        """Tiempo transcurrido en segundos."""
        if self._start is None:
            return 0.0
        return time.time() - self._start


# ============================================================================
# EXPORT FUNCTIONS
# ============================================================================

def get_metrics() -> Dict[str, Any]:
    """Obtiene todas las métricas en formato JSON."""
    return registry.get_all()


def get_prometheus_metrics() -> str:
    """Obtiene métricas en formato Prometheus."""
    return registry.to_prometheus()