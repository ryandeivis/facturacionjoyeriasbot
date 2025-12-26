"""
Cliente HTTP con Retry y Circuit Breaker

Proporciona un cliente HTTP robusto con:
- Retry automático con backoff exponencial
- Circuit breaker para evitar cascadas de fallos
- Timeouts configurables
- Logging detallado

Uso:
    client = ResilientHTTPClient(
        base_timeout=30.0,
        max_retries=3,
        circuit_breaker_threshold=5
    )
    response = await client.post(url, json=data)
"""

import asyncio
import httpx
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from src.utils.logger import get_logger

logger = get_logger(__name__)


class CircuitState(Enum):
    """Estados del circuit breaker."""
    CLOSED = "closed"      # Funcionando normal
    OPEN = "open"          # Circuito abierto, rechaza requests
    HALF_OPEN = "half_open"  # Probando si el servicio se recuperó


@dataclass
class CircuitBreaker:
    """
    Implementación de Circuit Breaker pattern.

    Previene cascadas de fallos cuando un servicio externo no responde.
    """
    failure_threshold: int = 5
    recovery_timeout: int = 60  # segundos
    half_open_max_calls: int = 3

    state: CircuitState = field(default=CircuitState.CLOSED)
    failure_count: int = field(default=0)
    success_count: int = field(default=0)
    last_failure_time: Optional[datetime] = field(default=None)
    half_open_calls: int = field(default=0)

    def record_success(self):
        """Registra una llamada exitosa."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.half_open_max_calls:
                self._close()
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0

    def record_failure(self):
        """Registra una llamada fallida."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()

        if self.state == CircuitState.HALF_OPEN:
            self._open()
        elif self.failure_count >= self.failure_threshold:
            self._open()

    def can_execute(self) -> bool:
        """Verifica si se puede ejecutar una llamada."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            if self._should_try_reset():
                self._half_open()
                return True
            return False

        # HALF_OPEN: permitir llamadas limitadas
        if self.half_open_calls < self.half_open_max_calls:
            self.half_open_calls += 1
            return True
        return False

    def _open(self):
        """Abre el circuito."""
        self.state = CircuitState.OPEN
        logger.warning(f"Circuit breaker ABIERTO después de {self.failure_count} fallos")

    def _close(self):
        """Cierra el circuito (normal)."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0
        logger.info("Circuit breaker CERRADO - servicio recuperado")

    def _half_open(self):
        """Estado de prueba."""
        self.state = CircuitState.HALF_OPEN
        self.half_open_calls = 0
        self.success_count = 0
        logger.info("Circuit breaker HALF-OPEN - probando servicio")

    def _should_try_reset(self) -> bool:
        """Verifica si debemos intentar resetear."""
        if not self.last_failure_time:
            return True
        elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout


@dataclass
class RetryConfig:
    """Configuración de reintentos."""
    max_retries: int = 3
    base_delay: float = 1.0  # segundos
    max_delay: float = 30.0  # segundos
    exponential_base: float = 2.0
    jitter: bool = True

    def get_delay(self, attempt: int) -> float:
        """Calcula delay con backoff exponencial."""
        delay = min(
            self.base_delay * (self.exponential_base ** attempt),
            self.max_delay
        )
        if self.jitter:
            import random
            delay = delay * (0.5 + random.random())
        return delay


class ResilientHTTPClient:
    """
    Cliente HTTP resiliente con retry y circuit breaker.

    Características:
    - Retry automático con backoff exponencial
    - Circuit breaker para evitar sobrecarga
    - Timeouts configurables
    - Compatible con httpx async
    """

    def __init__(
        self,
        base_timeout: float = 30.0,
        max_retries: int = 3,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_recovery: int = 60
    ):
        """
        Inicializa el cliente.

        Args:
            base_timeout: Timeout base en segundos
            max_retries: Número máximo de reintentos
            circuit_breaker_threshold: Fallos antes de abrir circuito
            circuit_breaker_recovery: Segundos antes de probar recuperación
        """
        self.timeout = base_timeout
        self.retry_config = RetryConfig(max_retries=max_retries)
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=circuit_breaker_threshold,
            recovery_timeout=circuit_breaker_recovery
        )

    async def post(
        self,
        url: str,
        json: Dict[str, Any] = None,
        headers: Dict[str, str] = None,
        timeout: float = None
    ) -> httpx.Response:
        """
        Realiza POST con retry y circuit breaker.

        Args:
            url: URL destino
            json: Datos JSON a enviar
            headers: Headers HTTP
            timeout: Timeout opcional (usa default si no se especifica)

        Returns:
            httpx.Response

        Raises:
            CircuitBreakerOpen: Si el circuito está abierto
            httpx.HTTPError: Si todos los reintentos fallan
        """
        if not self.circuit_breaker.can_execute():
            raise CircuitBreakerOpen(
                f"Circuit breaker abierto para {url}. Reintentando en "
                f"{self.circuit_breaker.recovery_timeout}s"
            )

        request_timeout = timeout or self.timeout
        last_exception = None

        for attempt in range(self.retry_config.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=request_timeout) as client:
                    response = await client.post(
                        url,
                        json=json,
                        headers=headers or {"Content-Type": "application/json"}
                    )

                    # Considerar 5xx como fallo para retry
                    if response.status_code >= 500:
                        raise httpx.HTTPStatusError(
                            f"Server error {response.status_code}",
                            request=response.request,
                            response=response
                        )

                    self.circuit_breaker.record_success()
                    return response

            except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError) as e:
                last_exception = e
                self.circuit_breaker.record_failure()

                if attempt < self.retry_config.max_retries:
                    delay = self.retry_config.get_delay(attempt)
                    logger.warning(
                        f"Intento {attempt + 1}/{self.retry_config.max_retries + 1} "
                        f"falló para {url}: {e}. Reintentando en {delay:.1f}s"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Todos los reintentos fallaron para {url}: {e}"
                    )

            except Exception as e:
                self.circuit_breaker.record_failure()
                logger.error(f"Error inesperado en request a {url}: {e}")
                raise

        raise last_exception

    async def get(
        self,
        url: str,
        headers: Dict[str, str] = None,
        timeout: float = None
    ) -> httpx.Response:
        """
        Realiza GET con retry y circuit breaker.

        Args:
            url: URL destino
            headers: Headers HTTP
            timeout: Timeout opcional

        Returns:
            httpx.Response
        """
        if not self.circuit_breaker.can_execute():
            raise CircuitBreakerOpen(f"Circuit breaker abierto para {url}")

        request_timeout = timeout or self.timeout
        last_exception = None

        for attempt in range(self.retry_config.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=request_timeout) as client:
                    response = await client.get(url, headers=headers)

                    if response.status_code >= 500:
                        raise httpx.HTTPStatusError(
                            f"Server error {response.status_code}",
                            request=response.request,
                            response=response
                        )

                    self.circuit_breaker.record_success()
                    return response

            except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError) as e:
                last_exception = e
                self.circuit_breaker.record_failure()

                if attempt < self.retry_config.max_retries:
                    delay = self.retry_config.get_delay(attempt)
                    logger.warning(
                        f"GET intento {attempt + 1} falló para {url}: {e}. "
                        f"Reintentando en {delay:.1f}s"
                    )
                    await asyncio.sleep(delay)

            except Exception as e:
                self.circuit_breaker.record_failure()
                raise

        raise last_exception

    def get_circuit_status(self) -> Dict[str, Any]:
        """Retorna estado actual del circuit breaker."""
        return {
            "state": self.circuit_breaker.state.value,
            "failure_count": self.circuit_breaker.failure_count,
            "last_failure": self.circuit_breaker.last_failure_time.isoformat()
            if self.circuit_breaker.last_failure_time else None
        }


class CircuitBreakerOpen(Exception):
    """Excepción cuando el circuit breaker está abierto."""
    pass


# Cliente global por defecto
default_client = ResilientHTTPClient()