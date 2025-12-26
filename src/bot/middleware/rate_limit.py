"""
Rate Limiting Middleware

Limita el número de requests por usuario para prevenir abuso.
"""

from typing import Dict, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
from telegram import Update
from telegram.ext import ContextTypes

from src.bot.middleware.base import BaseMiddleware
from config.settings import settings


class RateLimitMiddleware(BaseMiddleware):
    """
    Middleware de rate limiting.

    Implementa un límite de requests por ventana de tiempo por usuario.
    Usa un algoritmo de sliding window simplificado.
    """

    def __init__(
        self,
        max_requests: int = None,
        window_seconds: int = None,
        message: str = None
    ):
        """
        Inicializa el middleware.

        Args:
            max_requests: Número máximo de requests por ventana
            window_seconds: Tamaño de la ventana en segundos
            message: Mensaje a mostrar cuando se excede el límite
        """
        super().__init__("rate_limit")
        self.max_requests = max_requests or settings.RATE_LIMIT_REQUESTS
        self.window_seconds = window_seconds or settings.RATE_LIMIT_WINDOW
        self.message = message or (
            f"⏳ Demasiados mensajes\n\n"
            f"Has excedido el límite de {self.max_requests} mensajes.\n"
            f"Por favor, espera un momento."
        )

        # Estructura: {user_id: [(timestamp, count), ...]}
        self._requests: Dict[int, list] = defaultdict(list)

    def _cleanup_old_requests(self, user_id: int, now: datetime) -> None:
        """Limpia requests antiguos fuera de la ventana."""
        cutoff = now - timedelta(seconds=self.window_seconds)
        self._requests[user_id] = [
            (ts, count) for ts, count in self._requests[user_id]
            if ts > cutoff
        ]

    def _get_request_count(self, user_id: int, now: datetime) -> int:
        """Obtiene el conteo de requests en la ventana actual."""
        self._cleanup_old_requests(user_id, now)
        return sum(count for _, count in self._requests[user_id])

    def _add_request(self, user_id: int, now: datetime) -> None:
        """Registra un nuevo request."""
        self._requests[user_id].append((now, 1))

    async def before(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        """
        Verifica rate limit antes del handler.

        Returns:
            True si el usuario no ha excedido el límite
        """
        if not update.effective_user:
            return True

        user_id = update.effective_user.id
        now = datetime.utcnow()

        # Obtener conteo actual
        current_count = self._get_request_count(user_id, now)

        if current_count >= self.max_requests:
            self.logger.warning(
                f"Rate limit excedido para usuario {user_id}: "
                f"{current_count}/{self.max_requests}"
            )

            if update.message:
                await update.message.reply_text(self.message)

            return False

        # Registrar request
        self._add_request(user_id, now)

        return True

    def reset(self, user_id: int = None) -> None:
        """
        Resetea el contador de rate limit.

        Args:
            user_id: Usuario específico o None para todos
        """
        if user_id:
            self._requests[user_id] = []
        else:
            self._requests.clear()

    def get_remaining(self, user_id: int) -> Tuple[int, int]:
        """
        Obtiene requests restantes y tiempo hasta reset.

        Args:
            user_id: ID del usuario

        Returns:
            Tupla (requests_restantes, segundos_hasta_reset)
        """
        now = datetime.utcnow()
        current_count = self._get_request_count(user_id, now)
        remaining = max(0, self.max_requests - current_count)

        # Calcular tiempo hasta que expire el request más antiguo
        if self._requests[user_id]:
            oldest = min(ts for ts, _ in self._requests[user_id])
            reset_time = (
                oldest + timedelta(seconds=self.window_seconds) - now
            ).total_seconds()
            reset_time = max(0, int(reset_time))
        else:
            reset_time = 0

        return remaining, reset_time


class AdaptiveRateLimitMiddleware(RateLimitMiddleware):
    """
    Rate limiting adaptativo basado en el rol del usuario.

    Diferentes límites para diferentes roles.
    """

    # Multiplicadores por rol (base * multiplicador = límite)
    ROLE_MULTIPLIERS = {
        'ADMIN': 5.0,
        'SUPERVISOR': 3.0,
        'VENDEDOR': 1.0,
    }

    async def before(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        """Aplica rate limit adaptativo según rol."""
        if not update.effective_user:
            return True

        # Obtener rol del usuario
        user_data = context.user_data or {}
        rol = user_data.get('rol', 'VENDEDOR').upper()

        # Ajustar límite según rol
        multiplier = self.ROLE_MULTIPLIERS.get(rol, 1.0)
        original_max = self.max_requests
        self.max_requests = int(original_max * multiplier)

        try:
            result = await super().before(update, context)
        finally:
            # Restaurar límite original
            self.max_requests = original_max

        return result


class BurstRateLimitMiddleware(BaseMiddleware):
    """
    Rate limiting con soporte para bursts.

    Permite bursts cortos pero limita el rate sostenido.
    """

    def __init__(
        self,
        burst_limit: int = 10,
        sustained_rate: float = 1.0,  # requests por segundo
        message: str = None
    ):
        """
        Inicializa el middleware.

        Args:
            burst_limit: Número máximo de requests en burst
            sustained_rate: Rate sostenido permitido (req/s)
            message: Mensaje cuando se excede
        """
        super().__init__("burst_rate_limit")
        self.burst_limit = burst_limit
        self.sustained_rate = sustained_rate
        self.message = message or "⏳ Demasiados mensajes\n\nPor favor, espera un momento."

        # Token bucket: {user_id: (tokens, last_update)}
        self._buckets: Dict[int, Tuple[float, datetime]] = {}

    def _get_tokens(self, user_id: int, now: datetime) -> float:
        """Obtiene tokens disponibles usando token bucket algorithm."""
        if user_id not in self._buckets:
            return float(self.burst_limit)

        tokens, last_update = self._buckets[user_id]
        elapsed = (now - last_update).total_seconds()

        # Agregar tokens según tiempo transcurrido
        new_tokens = tokens + (elapsed * self.sustained_rate)
        return min(new_tokens, float(self.burst_limit))

    def _consume_token(self, user_id: int, now: datetime) -> bool:
        """Intenta consumir un token. Retorna True si exitoso."""
        tokens = self._get_tokens(user_id, now)

        if tokens < 1.0:
            return False

        self._buckets[user_id] = (tokens - 1.0, now)
        return True

    async def before(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        """Verifica burst rate limit."""
        if not update.effective_user:
            return True

        user_id = update.effective_user.id
        now = datetime.utcnow()

        if not self._consume_token(user_id, now):
            self.logger.warning(f"Burst rate limit excedido: {user_id}")
            if update.message:
                await update.message.reply_text(self.message)
            return False

        return True