"""
Utilidades del Sistema

Módulo que exporta todas las utilidades:
- Logger: Logging estructurado con contexto
- Crypto: Passwords, JWT, PII encryption, sanitización
- Validators: Validación centralizada de entrada
- Errors: Manejo centralizado de errores
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

# Validators
from src.utils.validators import (
    ValidationResult,
    ValidationLimits,
    IdentityValidator,
    ContactValidator,
    ProductValidator,
    InvoiceValidator,
    FileValidator,
    ValidationService,
    get_validation_service,
    get_tenant_validation_service,
    # Funciones de conveniencia
    validar_cedula,
    validar_nombre,
    validar_precio,
    validar_cantidad,
    validar_email,
    parsear_precio,
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

# Errors
from src.utils.errors import (
    ErrorCategory,
    ErrorSeverity,
    ErrorContext,
    BotError,
    ValidationError,
    DatabaseError,
    ExternalAPIError,
    AuthenticationError,
    AuthorizationError,
    BusinessError,
    FileError,
    handle_errors,
    wrap_external_error,
    wrap_database_error,
    ErrorRegistry,
    error_registry,
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

# Rate Limiting
from src.utils.rate_limiter import (
    OperationType,
    RateLimitConfig,
    RateLimiter,
    rate_limiter,
    check_login_rate,
    check_n8n_rate,
    check_invoice_rate,
    check_message_rate,
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
    # Validators
    "ValidationResult",
    "ValidationLimits",
    "IdentityValidator",
    "ContactValidator",
    "ProductValidator",
    "InvoiceValidator",
    "FileValidator",
    "ValidationService",
    "get_validation_service",
    "get_tenant_validation_service",
    "validar_cedula",
    "validar_nombre",
    "validar_precio",
    "validar_cantidad",
    "validar_email",
    "parsear_precio",
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
    # Errors
    "ErrorCategory",
    "ErrorSeverity",
    "ErrorContext",
    "BotError",
    "ValidationError",
    "DatabaseError",
    "ExternalAPIError",
    "AuthenticationError",
    "AuthorizationError",
    "BusinessError",
    "FileError",
    "handle_errors",
    "wrap_external_error",
    "wrap_database_error",
    "ErrorRegistry",
    "error_registry",
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
    # Rate Limiting
    "OperationType",
    "RateLimitConfig",
    "RateLimiter",
    "rate_limiter",
    "check_login_rate",
    "check_n8n_rate",
    "check_invoice_rate",
    "check_message_rate",
]