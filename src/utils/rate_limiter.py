"""
Servicio de Rate Limiting

Proporciona rate limiting por operación para proteger contra:
- Fuerza bruta en login
- Abuso de APIs externas (n8n)
- Spam de mensajes

Los límites se configuran en settings, no hardcodeados.

Uso:
    from src.utils.rate_limiter import rate_limiter

    # En handler
    if not rate_limiter.allow("login", user_id):
        await update.message.reply_text("Demasiados intentos...")
        return

    # Verificar límite de n8n
    if not rate_limiter.allow("n8n_request", org_id):
        # Manejar límite excedido
        ...
"""

from typing import Dict, Tuple, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict

from src.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

class OperationType(str, Enum):
    """Tipos de operación con rate limiting."""
    LOGIN_ATTEMPT = "login_attempt"
    N8N_REQUEST = "n8n_request"
    INVOICE_CREATE = "invoice_create"
    MESSAGE = "message"
    API_CALL = "api_call"


@dataclass
class RateLimitConfig:
    """Configuración de rate limit para una operación."""
    max_requests: int
    window_seconds: int
    block_seconds: int = 0  # Tiempo de bloqueo después de exceder (0 = sin bloqueo extra)
    message: str = ""

    def __post_init__(self):
        if not self.message:
            self.message = (
                f"Has excedido el límite de {self.max_requests} intentos.\n"
                f"Por favor, espera {self.window_seconds} segundos."
            )


def _get_default_limits() -> Dict[str, RateLimitConfig]:
    """
    Obtiene los límites por defecto desde settings.

    Los valores vienen de config/settings.py, no hardcodeados.
    """
    # Import aquí para evitar circular import
    from config.settings import settings

    return {
        OperationType.LOGIN_ATTEMPT.value: RateLimitConfig(
            max_requests=settings.RATE_LIMIT_LOGIN_MAX,
            window_seconds=settings.RATE_LIMIT_LOGIN_WINDOW,
            block_seconds=settings.RATE_LIMIT_LOGIN_BLOCK,
            message=(
                "🔒 Demasiados intentos de login\n\n"
                "Has excedido el límite de intentos.\n"
                f"Por favor, espera {settings.RATE_LIMIT_LOGIN_BLOCK // 60} minutos."
            )
        ),
        OperationType.N8N_REQUEST.value: RateLimitConfig(
            max_requests=settings.RATE_LIMIT_N8N_MAX,
            window_seconds=settings.RATE_LIMIT_N8N_WINDOW,
            message=(
                "⏳ Servicio ocupado\n\n"
                "Por favor, espera un momento antes de continuar."
            )
        ),
        OperationType.INVOICE_CREATE.value: RateLimitConfig(
            max_requests=settings.RATE_LIMIT_INVOICE_MAX,
            window_seconds=settings.RATE_LIMIT_INVOICE_WINDOW,
            message=(
                "📄 Límite de facturas alcanzado\n\n"
                "Has creado muchas facturas recientemente.\n"
                f"Por favor, espera {settings.RATE_LIMIT_INVOICE_WINDOW // 60} minutos."
            )
        ),
        OperationType.MESSAGE.value: RateLimitConfig(
            max_requests=settings.RATE_LIMIT_MESSAGE_MAX,
            window_seconds=settings.RATE_LIMIT_MESSAGE_WINDOW,
            message=(
                "⏳ Demasiados mensajes\n\n"
                "Por favor, espera un momento."
            )
        ),
        OperationType.API_CALL.value: RateLimitConfig(
            max_requests=settings.RATE_LIMIT_REQUESTS,
            window_seconds=settings.RATE_LIMIT_WINDOW,
            message="Rate limit excedido"
        ),
    }


# Lazy loading de límites (se cargan cuando se usan por primera vez)
_default_limits: Optional[Dict[str, RateLimitConfig]] = None


def get_default_limits() -> Dict[str, RateLimitConfig]:
    """Obtiene los límites por defecto (lazy loading)."""
    global _default_limits
    if _default_limits is None:
        _default_limits = _get_default_limits()
    return _default_limits




# ============================================================================
# RATE LIMITER SERVICE
# ============================================================================

class RateLimiter:
    """
    Servicio centralizado de rate limiting.

    Implementa sliding window con soporte para:
    - Múltiples tipos de operación
    - Bloqueo temporal después de exceder
    - Configuración por tenant (SaaS)
    - Métricas de uso
    """

    def __init__(self):
        # {operation: {key: [(timestamp, count), ...]}}
        self._requests: Dict[str, Dict[str, list]] = defaultdict(
            lambda: defaultdict(list)
        )
        # {operation: {key: blocked_until}}
        self._blocked: Dict[str, Dict[str, datetime]] = defaultdict(dict)
        # Configuraciones personalizadas por tenant
        self._tenant_configs: Dict[str, Dict[str, RateLimitConfig]] = {}

    def configure_tenant(
        self,
        tenant_id: str,
        operation: str,
        config: RateLimitConfig
    ) -> None:
        """
        Configura límites personalizados para un tenant.

        Args:
            tenant_id: ID del tenant/organización
            operation: Tipo de operación
            config: Configuración de rate limit
        """
        if tenant_id not in self._tenant_configs:
            self._tenant_configs[tenant_id] = {}
        self._tenant_configs[tenant_id][operation] = config
        logger.info(f"Rate limit configurado para tenant {tenant_id}: {operation}")

    def _get_config(
        self,
        operation: str,
        tenant_id: Optional[str] = None
    ) -> RateLimitConfig:
        """Obtiene la configuración para una operación."""
        # Primero buscar config de tenant
        if tenant_id and tenant_id in self._tenant_configs:
            if operation in self._tenant_configs[tenant_id]:
                return self._tenant_configs[tenant_id][operation]

        # Usar config por defecto desde settings
        defaults = get_default_limits()
        return defaults.get(
            operation,
            RateLimitConfig(max_requests=100, window_seconds=60)
        )

    def _cleanup(
        self,
        operation: str,
        key: str,
        now: datetime,
        window_seconds: int
    ) -> None:
        """Limpia requests antiguos."""
        cutoff = now - timedelta(seconds=window_seconds)
        self._requests[operation][key] = [
            (ts, count) for ts, count in self._requests[operation][key]
            if ts > cutoff
        ]

    def _get_count(
        self,
        operation: str,
        key: str,
        now: datetime,
        window_seconds: int
    ) -> int:
        """Obtiene el conteo de requests en la ventana."""
        self._cleanup(operation, key, now, window_seconds)
        return sum(count for _, count in self._requests[operation][key])

    def _is_blocked(self, operation: str, key: str, now: datetime) -> bool:
        """Verifica si el key está bloqueado."""
        if key in self._blocked[operation]:
            blocked_until = self._blocked[operation][key]
            if now < blocked_until:
                return True
            # Expiró el bloqueo
            del self._blocked[operation][key]
        return False

    def _block(
        self,
        operation: str,
        key: str,
        now: datetime,
        block_seconds: int
    ) -> None:
        """Bloquea un key por un tiempo."""
        if block_seconds > 0:
            self._blocked[operation][key] = now + timedelta(seconds=block_seconds)

    def allow(
        self,
        operation: str,
        key: str,
        tenant_id: Optional[str] = None,
        count: int = 1
    ) -> bool:
        """
        Verifica si una operación está permitida.

        Args:
            operation: Tipo de operación (login_attempt, n8n_request, etc.)
            key: Identificador único (user_id, org_id, IP, etc.)
            tenant_id: ID del tenant para config personalizada
            count: Número de requests a registrar

        Returns:
            True si la operación está permitida
        """
        config = self._get_config(operation, tenant_id)
        now = datetime.utcnow()
        key_str = str(key)

        # Verificar bloqueo
        if self._is_blocked(operation, key_str, now):
            logger.warning(f"Rate limit: {key_str} bloqueado para {operation}")
            return False

        # Obtener conteo actual
        current = self._get_count(operation, key_str, now, config.window_seconds)

        if current >= config.max_requests:
            # Bloquear si está configurado
            self._block(operation, key_str, now, config.block_seconds)
            logger.warning(
                f"Rate limit excedido: {operation} para {key_str} "
                f"({current}/{config.max_requests})"
            )
            return False

        # Registrar request
        self._requests[operation][key_str].append((now, count))
        return True

    def get_remaining(
        self,
        operation: str,
        key: str,
        tenant_id: Optional[str] = None
    ) -> Tuple[int, int]:
        """
        Obtiene requests restantes y tiempo hasta reset.

        Returns:
            Tupla (requests_restantes, segundos_hasta_reset)
        """
        config = self._get_config(operation, tenant_id)
        now = datetime.utcnow()
        key_str = str(key)

        # Si está bloqueado, retornar tiempo de bloqueo
        if key_str in self._blocked[operation]:
            blocked_until = self._blocked[operation][key_str]
            if now < blocked_until:
                remaining_block = int((blocked_until - now).total_seconds())
                return 0, remaining_block

        current = self._get_count(operation, key_str, now, config.window_seconds)
        remaining = max(0, config.max_requests - current)

        # Calcular tiempo hasta reset
        if self._requests[operation][key_str]:
            oldest = min(ts for ts, _ in self._requests[operation][key_str])
            reset_time = int(
                (oldest + timedelta(seconds=config.window_seconds) - now).total_seconds()
            )
            reset_time = max(0, reset_time)
        else:
            reset_time = 0

        return remaining, reset_time

    def get_message(
        self,
        operation: str,
        tenant_id: Optional[str] = None
    ) -> str:
        """Obtiene el mensaje de error para una operación."""
        config = self._get_config(operation, tenant_id)
        return config.message

    def reset(
        self,
        operation: Optional[str] = None,
        key: Optional[str] = None
    ) -> None:
        """
        Resetea contadores de rate limit.

        Args:
            operation: Operación específica o None para todas
            key: Key específico o None para todos
        """
        if operation and key:
            key_str = str(key)
            if key_str in self._requests[operation]:
                self._requests[operation][key_str] = []
            if key_str in self._blocked[operation]:
                del self._blocked[operation][key_str]
        elif operation:
            self._requests[operation].clear()
            self._blocked[operation].clear()
        else:
            self._requests.clear()
            self._blocked.clear()

    def get_stats(self) -> Dict[str, Dict[str, int]]:
        """Obtiene estadísticas de uso."""
        stats = {}
        now = datetime.utcnow()

        for operation, keys in self._requests.items():
            config = self._get_config(operation)
            stats[operation] = {
                "active_keys": len(keys),
                "total_requests": sum(
                    self._get_count(operation, k, now, config.window_seconds)
                    for k in keys
                ),
                "blocked_keys": len(self._blocked.get(operation, {}))
            }

        return stats


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

rate_limiter = RateLimiter()


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def check_login_rate(user_id: int) -> Tuple[bool, str]:
    """
    Verifica rate limit para login.

    Args:
        user_id: ID del usuario (Telegram ID)

    Returns:
        Tupla (permitido, mensaje_error)
    """
    allowed = rate_limiter.allow(OperationType.LOGIN_ATTEMPT.value, str(user_id))
    if not allowed:
        message = rate_limiter.get_message(OperationType.LOGIN_ATTEMPT.value)
        return False, message
    return True, ""


def check_n8n_rate(org_id: str) -> Tuple[bool, str]:
    """
    Verifica rate limit para llamadas a n8n.

    Returns:
        Tupla (permitido, mensaje_error)
    """
    allowed = rate_limiter.allow(
        OperationType.N8N_REQUEST.value,
        org_id,
        tenant_id=org_id
    )
    if not allowed:
        message = rate_limiter.get_message(
            OperationType.N8N_REQUEST.value,
            tenant_id=org_id
        )
        return False, message
    return True, ""


def check_invoice_rate(user_id: int, org_id: str) -> Tuple[bool, str]:
    """
    Verifica rate limit para crear facturas.

    Returns:
        Tupla (permitido, mensaje_error)
    """
    # Combinar user_id y org_id para el key
    key = f"{org_id}:{user_id}"
    allowed = rate_limiter.allow(
        OperationType.INVOICE_CREATE.value,
        key,
        tenant_id=org_id
    )
    if not allowed:
        message = rate_limiter.get_message(
            OperationType.INVOICE_CREATE.value,
            tenant_id=org_id
        )
        return False, message
    return True, ""


def check_message_rate(user_id: int) -> Tuple[bool, str]:
    """
    Verifica rate limit para mensajes generales.

    Args:
        user_id: ID del usuario (Telegram ID)

    Returns:
        Tupla (permitido, mensaje_error)
    """
    allowed = rate_limiter.allow(OperationType.MESSAGE.value, str(user_id))
    if not allowed:
        message = rate_limiter.get_message(OperationType.MESSAGE.value)
        return False, message
    return True, ""


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "OperationType",
    "RateLimitConfig",
    "RateLimiter",
    "rate_limiter",
    "check_login_rate",
    "check_n8n_rate",
    "check_invoice_rate",
    "check_message_rate",
    "get_default_limits",
]
