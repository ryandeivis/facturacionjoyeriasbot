"""
Sistema de Logging Estructurado

Configura el logging para toda la aplicación con:
- Salida a consola (colores en desarrollo, JSON en producción)
- Archivo rotativo para logs generales
- Archivo rotativo para errores
- Soporte para contexto (correlation ID, org_id, user_id)
- Logging estructurado JSON para producción
"""

import logging
import json
import uuid
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from contextvars import ContextVar
from functools import wraps

# Context variables para información de contexto
correlation_id_var: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)
org_id_var: ContextVar[Optional[str]] = ContextVar('org_id', default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar('user_id', default=None)
action_var: ContextVar[Optional[str]] = ContextVar('action', default=None)


# ============================================================================
# FORMATTERS
# ============================================================================

class ColoredFormatter(logging.Formatter):
    """
    Formatter con colores para desarrollo.
    """

    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'

    def format(self, record: logging.LogRecord) -> str:
        # Agregar contexto
        record.correlation_id = correlation_id_var.get() or '-'
        record.org_id = org_id_var.get() or '-'
        record.user_id = user_id_var.get() or '-'

        # Aplicar color
        color = self.COLORS.get(record.levelname, '')
        record.levelname = f"{color}{record.levelname}{self.RESET}"

        return super().format(record)


class JSONFormatter(logging.Formatter):
    """
    Formatter JSON para producción.

    Genera logs estructurados fáciles de procesar por herramientas
    como ELK Stack, Datadog, etc.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Agregar contexto
        correlation_id = correlation_id_var.get()
        if correlation_id:
            log_data["correlation_id"] = correlation_id

        org_id = org_id_var.get()
        if org_id:
            log_data["org_id"] = org_id

        user_id = user_id_var.get()
        if user_id:
            log_data["user_id"] = user_id

        action = action_var.get()
        if action:
            log_data["action"] = action

        # Agregar exception info si existe
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
            }

        # Agregar campos extra
        if hasattr(record, 'extra_data'):
            log_data["extra"] = record.extra_data

        return json.dumps(log_data, ensure_ascii=False, default=str)


class ContextFormatter(logging.Formatter):
    """
    Formatter que incluye contexto en formato legible.
    """

    def format(self, record: logging.LogRecord) -> str:
        # Agregar contexto al record
        context_parts = []

        correlation_id = correlation_id_var.get()
        if correlation_id:
            context_parts.append(f"cid={correlation_id[:8]}")

        org_id = org_id_var.get()
        if org_id:
            context_parts.append(f"org={org_id[:8]}")

        user_id = user_id_var.get()
        if user_id:
            context_parts.append(f"user={user_id}")

        record.context = f"[{' '.join(context_parts)}]" if context_parts else ""

        return super().format(record)


# ============================================================================
# LOGGER CONFIGURATION
# ============================================================================

_configured = False
_log_level = logging.INFO


def setup_logging(
    environment: str = "development",
    log_level: str = "INFO",
    log_dir: str = "logs"
) -> None:
    """
    Configura el sistema de logging según el entorno.

    Args:
        environment: Entorno (development, staging, production)
        log_level: Nivel de log (DEBUG, INFO, WARNING, ERROR)
        log_dir: Directorio para archivos de log
    """
    global _configured, _log_level

    if _configured:
        return

    _log_level = getattr(logging, log_level.upper(), logging.INFO)

    # Crear directorio de logs
    logs_path = Path(log_dir)
    logs_path.mkdir(exist_ok=True)

    # Configurar root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Limpiar handlers existentes
    root_logger.handlers = []

    # Handler de consola según entorno
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(_log_level)

    if environment == "production":
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(ColoredFormatter(
            '%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s',
            datefmt='%H:%M:%S'
        ))

    root_logger.addHandler(console_handler)

    # Handler de archivo general (siempre JSON para procesamiento)
    file_handler = RotatingFileHandler(
        logs_path / "app.log",
        maxBytes=50*1024*1024,  # 50MB
        backupCount=10,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(file_handler)

    # Handler de errores
    error_handler = RotatingFileHandler(
        logs_path / "errors.log",
        maxBytes=50*1024*1024,  # 50MB
        backupCount=10,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(error_handler)

    # Handler de auditoría
    audit_handler = RotatingFileHandler(
        logs_path / "audit.log",
        maxBytes=100*1024*1024,  # 100MB
        backupCount=30,  # Mantener más tiempo
        encoding='utf-8'
    )
    audit_handler.setLevel(logging.INFO)
    audit_handler.setFormatter(JSONFormatter())
    # Solo logs de auditoría
    audit_handler.addFilter(lambda r: r.name.startswith('audit'))
    root_logger.addHandler(audit_handler)

    _configured = True

    # Log de inicio
    root_logger.info(
        f"Logging configurado: environment={environment}, level={log_level}"
    )


def get_logger(name: str) -> logging.Logger:
    """
    Obtiene un logger configurado para el módulo especificado.

    Args:
        name: Nombre del módulo (típicamente __name__)

    Returns:
        Logger configurado
    """
    global _configured

    # Configurar si no se ha hecho
    if not _configured:
        try:
            from config.settings import settings
            setup_logging(
                environment=settings.ENVIRONMENT.value if hasattr(settings.ENVIRONMENT, 'value') else str(settings.ENVIRONMENT),
                log_level=settings.LOG_LEVEL
            )
        except Exception:
            # Configuración por defecto si falla
            setup_logging()

    return logging.getLogger(name)


# ============================================================================
# CONTEXT MANAGEMENT
# ============================================================================

def bind_context(
    correlation_id: str = None,
    org_id: str = None,
    user_id: str = None,
    action: str = None
) -> None:
    """
    Establece variables de contexto para logging.

    Args:
        correlation_id: ID de correlación para tracking
        org_id: ID de organización
        user_id: ID de usuario
        action: Acción actual
    """
    if correlation_id:
        correlation_id_var.set(correlation_id)
    if org_id:
        org_id_var.set(org_id)
    if user_id:
        user_id_var.set(user_id)
    if action:
        action_var.set(action)


def clear_context() -> None:
    """Limpia todas las variables de contexto."""
    correlation_id_var.set(None)
    org_id_var.set(None)
    user_id_var.set(None)
    action_var.set(None)


def new_correlation_id() -> str:
    """
    Genera y establece un nuevo correlation ID.

    Returns:
        El correlation ID generado
    """
    cid = str(uuid.uuid4())
    correlation_id_var.set(cid)
    return cid


def get_correlation_id() -> Optional[str]:
    """Obtiene el correlation ID actual."""
    return correlation_id_var.get()


class LogContext:
    """
    Context manager para establecer contexto de logging temporalmente.

    Uso:
        with LogContext(org_id="org-123", user_id="user-456"):
            logger.info("Este log incluirá el contexto")
    """

    def __init__(
        self,
        correlation_id: str = None,
        org_id: str = None,
        user_id: str = None,
        action: str = None,
        auto_correlation: bool = True
    ):
        self.correlation_id = correlation_id
        self.org_id = org_id
        self.user_id = user_id
        self.action = action
        self.auto_correlation = auto_correlation

        # Guardar valores anteriores
        self._prev_correlation = None
        self._prev_org = None
        self._prev_user = None
        self._prev_action = None

    def __enter__(self):
        # Guardar estado anterior
        self._prev_correlation = correlation_id_var.get()
        self._prev_org = org_id_var.get()
        self._prev_user = user_id_var.get()
        self._prev_action = action_var.get()

        # Establecer nuevo contexto
        if self.correlation_id:
            correlation_id_var.set(self.correlation_id)
        elif self.auto_correlation and not self._prev_correlation:
            correlation_id_var.set(str(uuid.uuid4()))

        if self.org_id:
            org_id_var.set(self.org_id)
        if self.user_id:
            user_id_var.set(self.user_id)
        if self.action:
            action_var.set(self.action)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restaurar estado anterior
        correlation_id_var.set(self._prev_correlation)
        org_id_var.set(self._prev_org)
        user_id_var.set(self._prev_user)
        action_var.set(self._prev_action)
        return False


def with_context(**context_kwargs):
    """
    Decorador para establecer contexto de logging en una función.

    Uso:
        @with_context(action="create_invoice")
        async def create_invoice(org_id: str):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            with LogContext(**context_kwargs):
                return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with LogContext(**context_kwargs):
                return func(*args, **kwargs)

        if asyncio_iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def asyncio_iscoroutinefunction(func) -> bool:
    """Verifica si una función es async."""
    import asyncio
    return asyncio.iscoroutinefunction(func)


# ============================================================================
# AUDIT LOGGER
# ============================================================================

class AuditLogger:
    """
    Logger especializado para auditoría.

    Registra acciones de usuarios de forma estructurada.
    """

    def __init__(self, name: str = "audit"):
        self.logger = logging.getLogger(f"audit.{name}")

    def log(
        self,
        action: str,
        entity_type: str = None,
        entity_id: str = None,
        user_id: str = None,
        org_id: str = None,
        details: Dict[str, Any] = None,
        old_values: Dict[str, Any] = None,
        new_values: Dict[str, Any] = None,
        status: str = "success"
    ) -> None:
        """
        Registra una acción de auditoría.

        Args:
            action: Tipo de acción (create, update, delete, login, etc.)
            entity_type: Tipo de entidad afectada
            entity_id: ID de la entidad
            user_id: ID del usuario (si no se proporciona, usa el contexto)
            org_id: ID de organización (si no se proporciona, usa el contexto)
            details: Detalles adicionales
            old_values: Valores anteriores (para updates)
            new_values: Valores nuevos (para creates/updates)
            status: Estado de la acción (success, failure, error)
        """
        audit_data = {
            "action": action,
            "status": status,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        # Usar contexto si no se proporciona
        if user_id:
            audit_data["user_id"] = user_id
        elif user_id_var.get():
            audit_data["user_id"] = user_id_var.get()

        if org_id:
            audit_data["org_id"] = org_id
        elif org_id_var.get():
            audit_data["org_id"] = org_id_var.get()

        if correlation_id_var.get():
            audit_data["correlation_id"] = correlation_id_var.get()

        if entity_type:
            audit_data["entity_type"] = entity_type
        if entity_id:
            audit_data["entity_id"] = entity_id
        if details:
            audit_data["details"] = details
        if old_values:
            audit_data["old_values"] = old_values
        if new_values:
            audit_data["new_values"] = new_values

        # Crear record con extra data
        self.logger.info(
            f"AUDIT: {action} on {entity_type or 'unknown'}",
            extra={"extra_data": audit_data}
        )

    def login(self, user_id: str, org_id: str, success: bool = True) -> None:
        """Registra un intento de login."""
        self.log(
            action="login",
            user_id=user_id,
            org_id=org_id,
            status="success" if success else "failure"
        )

    def logout(self, user_id: str, org_id: str) -> None:
        """Registra un logout."""
        self.log(
            action="logout",
            user_id=user_id,
            org_id=org_id
        )

    def create(
        self,
        entity_type: str,
        entity_id: str,
        new_values: Dict[str, Any] = None
    ) -> None:
        """Registra una creación."""
        self.log(
            action="create",
            entity_type=entity_type,
            entity_id=entity_id,
            new_values=new_values
        )

    def update(
        self,
        entity_type: str,
        entity_id: str,
        old_values: Dict[str, Any] = None,
        new_values: Dict[str, Any] = None
    ) -> None:
        """Registra una actualización."""
        self.log(
            action="update",
            entity_type=entity_type,
            entity_id=entity_id,
            old_values=old_values,
            new_values=new_values
        )

    def delete(self, entity_type: str, entity_id: str) -> None:
        """Registra una eliminación."""
        self.log(
            action="delete",
            entity_type=entity_type,
            entity_id=entity_id
        )


# Instancia global del audit logger
audit_logger = AuditLogger()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def log_exception(logger: logging.Logger, message: str, exc: Exception) -> None:
    """
    Loggea una excepción con contexto completo.

    Args:
        logger: Logger a usar
        message: Mensaje descriptivo
        exc: Excepción a loggear
    """
    logger.error(
        f"{message}: {type(exc).__name__}: {str(exc)}",
        exc_info=True,
        extra={
            "extra_data": {
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
            }
        }
    )


def log_performance(logger: logging.Logger, operation: str, duration_ms: float) -> None:
    """
    Loggea métricas de rendimiento.

    Args:
        logger: Logger a usar
        operation: Nombre de la operación
        duration_ms: Duración en milisegundos
    """
    logger.info(
        f"Performance: {operation} completed in {duration_ms:.2f}ms",
        extra={
            "extra_data": {
                "metric_type": "performance",
                "operation": operation,
                "duration_ms": duration_ms,
            }
        }
    )