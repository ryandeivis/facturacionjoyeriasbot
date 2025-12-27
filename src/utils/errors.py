"""
Sistema Centralizado de Manejo de Errores

Proporciona:
- Tipos de error categorizados (BotError, ValidationError, etc.)
- Mensajes amigables para usuarios
- Correlation IDs para soporte técnico
- Decorador para manejo automático en handlers
- Logging estructurado de excepciones
"""

import logging
from enum import Enum
from functools import wraps
from typing import Optional, Callable, Any, Dict
from dataclasses import dataclass

from src.utils.logger import (
    get_logger,
    new_correlation_id,
    get_correlation_id,
    LogContext,
)

logger = get_logger(__name__)


# ============================================================================
# ERROR CATEGORIES
# ============================================================================

class ErrorCategory(str, Enum):
    """Categorías de error para clasificación."""
    VALIDATION = "VALIDATION"
    DATABASE = "DATABASE"
    EXTERNAL_API = "EXTERNAL_API"
    AUTHENTICATION = "AUTHENTICATION"
    AUTHORIZATION = "AUTHORIZATION"
    NETWORK = "NETWORK"
    FILE = "FILE"
    BUSINESS = "BUSINESS"
    INTERNAL = "INTERNAL"


class ErrorSeverity(str, Enum):
    """Severidad del error para priorización."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# ============================================================================
# USER-FRIENDLY MESSAGES
# ============================================================================

USER_MESSAGES = {
    ErrorCategory.VALIDATION: (
        "Los datos ingresados no son válidos.\n"
        "Por favor verifica e intenta nuevamente."
    ),
    ErrorCategory.DATABASE: (
        "Hubo un problema al guardar la información.\n"
        "Por favor intenta en unos momentos."
    ),
    ErrorCategory.EXTERNAL_API: (
        "No se pudo conectar con el servicio externo.\n"
        "Por favor intenta nuevamente."
    ),
    ErrorCategory.AUTHENTICATION: (
        "No se pudo verificar tu identidad.\n"
        "Por favor inicia sesión nuevamente."
    ),
    ErrorCategory.AUTHORIZATION: (
        "No tienes permiso para realizar esta acción."
    ),
    ErrorCategory.NETWORK: (
        "Problema de conexión.\n"
        "Verifica tu conexión e intenta nuevamente."
    ),
    ErrorCategory.FILE: (
        "Error procesando el archivo.\n"
        "Verifica el formato e intenta nuevamente."
    ),
    ErrorCategory.BUSINESS: (
        "No se puede completar esta operación.\n"
        "Verifica los datos e intenta nuevamente."
    ),
    ErrorCategory.INTERNAL: (
        "Ocurrió un error inesperado.\n"
        "Nuestro equipo ha sido notificado."
    ),
}


# ============================================================================
# ERROR CONTEXT
# ============================================================================

@dataclass
class ErrorContext:
    """Contexto adicional para un error."""
    user_id: Optional[str] = None
    org_id: Optional[str] = None
    operation: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


# ============================================================================
# CUSTOM EXCEPTIONS
# ============================================================================

class BotError(Exception):
    """
    Excepción base para errores del bot.

    Incluye categoría, severidad y mensaje amigable.
    """

    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.INTERNAL,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        user_message: Optional[str] = None,
        context: Optional[ErrorContext] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.severity = severity
        self.user_message = user_message or USER_MESSAGES.get(
            category, USER_MESSAGES[ErrorCategory.INTERNAL]
        )
        self.context = context or ErrorContext()
        self.original_error = original_error
        self.correlation_id = get_correlation_id() or new_correlation_id()

    def get_user_message(self, include_reference: bool = True) -> str:
        """Obtiene el mensaje para mostrar al usuario."""
        if include_reference and self.severity in (
            ErrorSeverity.HIGH, ErrorSeverity.CRITICAL
        ):
            return (
                f"⚠ {self.user_message}\n\n"
                f"📋 Referencia: {self.correlation_id[:8]}"
            )
        return f"⚠ {self.user_message}"

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el error a diccionario para logging."""
        return {
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "correlation_id": self.correlation_id,
            "context": {
                "user_id": self.context.user_id,
                "org_id": self.context.org_id,
                "operation": self.context.operation,
                "entity_type": self.context.entity_type,
                "entity_id": self.context.entity_id,
                "extra": self.context.extra,
            },
            "original_error": str(self.original_error) if self.original_error else None,
        }


class ValidationError(BotError):
    """Error de validación de datos."""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        user_message: Optional[str] = None,
        **kwargs
    ):
        self.field = field
        super().__init__(
            message=message,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.LOW,
            user_message=user_message,
            **kwargs
        )


class DatabaseError(BotError):
    """Error de base de datos."""

    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.DATABASE,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )


class ExternalAPIError(BotError):
    """Error de API externa (n8n, servicios de terceros)."""

    def __init__(
        self,
        message: str,
        service: str = "external",
        status_code: Optional[int] = None,
        **kwargs
    ):
        self.service = service
        self.status_code = status_code
        super().__init__(
            message=message,
            category=ErrorCategory.EXTERNAL_API,
            severity=ErrorSeverity.MEDIUM,
            **kwargs
        )


class AuthenticationError(BotError):
    """Error de autenticación."""

    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.MEDIUM,
            **kwargs
        )


class AuthorizationError(BotError):
    """Error de autorización/permisos."""

    def __init__(
        self,
        message: str,
        required_role: Optional[str] = None,
        **kwargs
    ):
        self.required_role = required_role
        super().__init__(
            message=message,
            category=ErrorCategory.AUTHORIZATION,
            severity=ErrorSeverity.LOW,
            **kwargs
        )


class BusinessError(BotError):
    """Error de lógica de negocio."""

    def __init__(
        self,
        message: str,
        user_message: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            message=message,
            category=ErrorCategory.BUSINESS,
            severity=ErrorSeverity.LOW,
            user_message=user_message,
            **kwargs
        )


class FileError(BotError):
    """Error de procesamiento de archivos."""

    def __init__(
        self,
        message: str,
        filename: Optional[str] = None,
        **kwargs
    ):
        self.filename = filename
        super().__init__(
            message=message,
            category=ErrorCategory.FILE,
            severity=ErrorSeverity.LOW,
            **kwargs
        )


# ============================================================================
# ERROR HANDLER DECORATOR
# ============================================================================

def handle_errors(
    user_message: Optional[str] = None,
    log_level: int = logging.ERROR,
    reraise: bool = False,
    notify_user: bool = True,
    default_return: Any = None
) -> Callable:
    """
    Decorador para manejo automático de errores en handlers.

    Args:
        user_message: Mensaje personalizado para el usuario
        log_level: Nivel de logging (default: ERROR)
        reraise: Si relanzar la excepción después de manejarla
        notify_user: Si notificar al usuario del error
        default_return: Valor a retornar en caso de error

    Usage:
        @handle_errors(user_message="Error procesando factura")
        async def crear_factura(update, context):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            correlation_id = get_correlation_id() or new_correlation_id()

            try:
                with LogContext(correlation_id=correlation_id):
                    return await func(*args, **kwargs)

            except BotError as e:
                _log_bot_error(e, func.__name__, log_level)

                if notify_user:
                    await _notify_user_of_error(args, e.get_user_message())

                if reraise:
                    raise
                return default_return

            except Exception as e:
                bot_error = BotError(
                    message=f"Error inesperado en {func.__name__}: {str(e)}",
                    category=ErrorCategory.INTERNAL,
                    severity=ErrorSeverity.HIGH,
                    original_error=e
                )

                _log_bot_error(bot_error, func.__name__, log_level, exc_info=True)

                if notify_user:
                    msg = user_message or bot_error.get_user_message()
                    await _notify_user_of_error(args, msg)

                if reraise:
                    raise bot_error from e
                return default_return

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            correlation_id = get_correlation_id() or new_correlation_id()

            try:
                with LogContext(correlation_id=correlation_id):
                    return func(*args, **kwargs)

            except BotError as e:
                _log_bot_error(e, func.__name__, log_level)
                if reraise:
                    raise
                return default_return

            except Exception as e:
                bot_error = BotError(
                    message=f"Error inesperado en {func.__name__}: {str(e)}",
                    category=ErrorCategory.INTERNAL,
                    severity=ErrorSeverity.HIGH,
                    original_error=e
                )
                _log_bot_error(bot_error, func.__name__, log_level, exc_info=True)
                if reraise:
                    raise bot_error from e
                return default_return

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def _log_bot_error(
    error: BotError,
    function_name: str,
    log_level: int,
    exc_info: bool = False
) -> None:
    """Loggea un BotError con contexto completo."""
    error_dict = error.to_dict()
    error_dict["function"] = function_name

    logger.log(
        log_level,
        f"[{error.correlation_id[:8]}] {error.category.value}: {error.message}",
        extra={"extra_data": error_dict},
        exc_info=exc_info
    )


async def _notify_user_of_error(args: tuple, message: str) -> None:
    """Intenta notificar al usuario del error."""
    update = None

    for arg in args:
        if hasattr(arg, 'message') or hasattr(arg, 'callback_query'):
            update = arg
            break

    if update is None:
        return

    try:
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.answer(message[:200], show_alert=True)
        elif hasattr(update, 'message') and update.message:
            await update.message.reply_text(message)
    except Exception as notify_error:
        logger.warning(f"No se pudo notificar error al usuario: {notify_error}")


# ============================================================================
# ERROR CONVERSION UTILITIES
# ============================================================================

def wrap_external_error(
    error: Exception,
    service: str = "external",
    operation: Optional[str] = None
) -> ExternalAPIError:
    """Envuelve un error de servicio externo en ExternalAPIError."""
    return ExternalAPIError(
        message=f"Error en {service}: {str(error)}",
        service=service,
        original_error=error,
        context=ErrorContext(operation=operation)
    )


def wrap_database_error(
    error: Exception,
    operation: Optional[str] = None,
    entity_type: Optional[str] = None
) -> DatabaseError:
    """Envuelve un error de base de datos."""
    return DatabaseError(
        message=f"Error de base de datos: {str(error)}",
        original_error=error,
        context=ErrorContext(
            operation=operation,
            entity_type=entity_type
        )
    )


# ============================================================================
# ERROR REGISTRY (para métricas)
# ============================================================================

class ErrorRegistry:
    """
    Registro de errores para métricas y análisis.

    Permite trackear errores por categoría, severidad, etc.
    """

    def __init__(self):
        self._counts: Dict[str, int] = {}
        self._recent_errors: list = []
        self._max_recent = 100

    def record(self, error: BotError) -> None:
        """Registra un error en el registry."""
        key = f"{error.category.value}:{error.severity.value}"
        self._counts[key] = self._counts.get(key, 0) + 1

        self._recent_errors.append({
            "correlation_id": error.correlation_id,
            "category": error.category.value,
            "message": error.message[:100],
        })
        if len(self._recent_errors) > self._max_recent:
            self._recent_errors.pop(0)

    def get_counts(self) -> Dict[str, int]:
        """Obtiene conteo de errores por categoría:severidad."""
        return self._counts.copy()

    def get_recent(self, limit: int = 10) -> list:
        """Obtiene los errores más recientes."""
        return self._recent_errors[-limit:]

    def reset(self) -> None:
        """Resetea los contadores."""
        self._counts.clear()
        self._recent_errors.clear()


# Instancia global del registry
error_registry = ErrorRegistry()


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Categories & Severity
    "ErrorCategory",
    "ErrorSeverity",
    # Exceptions
    "BotError",
    "ValidationError",
    "DatabaseError",
    "ExternalAPIError",
    "AuthenticationError",
    "AuthorizationError",
    "BusinessError",
    "FileError",
    "ErrorContext",
    # Decorator
    "handle_errors",
    # Utilities
    "wrap_external_error",
    "wrap_database_error",
    # Registry
    "ErrorRegistry",
    "error_registry",
    # Messages
    "USER_MESSAGES",
]
