"""
Utilidades del Sistema

Módulo que exporta todas las utilidades:
- Logger: Logging estructurado con contexto
- Crypto: Passwords, JWT, PII encryption, sanitización
- Metrics: Contadores, gauges, histogramas, Prometheus
- Health: Health checks unificados
"""

# Logger
from src.utils.logger import (
    get_logger,
    setup_logging,
    bind_context,
    clear_context,
    new_correlation_id,
    get_correlation_id,
    LogContext,
    with_context,
    AuditLogger,
    audit_logger,
    log_exception,
    log_performance,
)

# Crypto
from src.utils.crypto import (
    hash_password,
    verify_password,
    validate_password_strength,
    JWTService,
    PIIEncryption,
    InputSanitizer,
    CryptoService,
    get_crypto_service,
)

# Metrics
from src.utils.metrics import (
    Counter,
    Gauge,
    Histogram,
    Summary,
    MetricsRegistry,
    registry,
    Timer,
    timed,
    counted,
    get_metrics,
    get_prometheus_metrics,
    # Métricas pre-definidas
    invoices_created,
    invoices_processed,
    active_users,
    request_duration,
    n8n_requests,
    db_queries,
    errors,
    bot_messages,
)

# Health Checks
from src.utils.health_check import (
    HealthStatus,
    ComponentHealth,
    SystemHealth,
    HealthChecker,
    health_checker,
    register_default_checks,
    get_health,
    is_healthy,
    get_readiness,
    get_liveness,
)

__all__ = [
    # Logger
    "get_logger",
    "setup_logging",
    "bind_context",
    "clear_context",
    "new_correlation_id",
    "get_correlation_id",
    "LogContext",
    "with_context",
    "AuditLogger",
    "audit_logger",
    "log_exception",
    "log_performance",
    # Crypto
    "hash_password",
    "verify_password",
    "validate_password_strength",
    "JWTService",
    "PIIEncryption",
    "InputSanitizer",
    "CryptoService",
    "get_crypto_service",
    # Metrics
    "Counter",
    "Gauge",
    "Histogram",
    "Summary",
    "MetricsRegistry",
    "registry",
    "Timer",
    "timed",
    "counted",
    "get_metrics",
    "get_prometheus_metrics",
    "invoices_created",
    "invoices_processed",
    "active_users",
    "request_duration",
    "n8n_requests",
    "db_queries",
    "errors",
    "bot_messages",
    # Health
    "HealthStatus",
    "ComponentHealth",
    "SystemHealth",
    "HealthChecker",
    "health_checker",
    "register_default_checks",
    "get_health",
    "is_healthy",
    "get_readiness",
    "get_liveness",
]