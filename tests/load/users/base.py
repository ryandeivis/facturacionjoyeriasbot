# ==============================================================================
# Base User for Load Testing
# ==============================================================================
"""
Usuario base con autenticación y funcionalidad común.

Todos los usuarios virtuales heredan de esta clase para:
- Autenticación automática en on_start()
- Headers comunes (X-Organization-ID, Authorization)
- Manejo de errores y métricas
"""

from typing import Optional, Dict, Any
import logging

from locust import HttpUser, between, events
from locust.exception import StopUser

from tests.load.config import (
    DEFAULT_CREDENTIALS,
    ENDPOINTS,
    WAIT_TIME_MIN,
    WAIT_TIME_MAX,
    REQUEST_TIMEOUT,
    TestCredentials,
)


logger = logging.getLogger(__name__)


class BaseAPIUser(HttpUser):
    """
    Usuario base para pruebas de carga.

    Proporciona:
    - Autenticación automática al iniciar
    - Headers comunes para multi-tenancy
    - Métodos helper para requests
    - Manejo de errores

    Attributes:
        credentials: Credenciales del usuario
        token: JWT token después de autenticación
        organization_id: ID de la organización del usuario
    """

    # Tiempo de espera entre tareas (simula comportamiento humano)
    wait_time = between(WAIT_TIME_MIN, WAIT_TIME_MAX)

    # No ejecutar directamente (clase abstracta)
    abstract = True

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.credentials: TestCredentials = DEFAULT_CREDENTIALS
        self.token: Optional[str] = None
        self.organization_id: str = self.credentials.organization_id
        self._authenticated: bool = False

    def on_start(self) -> None:
        """
        Ejecutado al iniciar el usuario virtual.

        Realiza autenticación y configura headers.
        """
        self._authenticate()

    def on_stop(self) -> None:
        """
        Ejecutado al detener el usuario virtual.

        Limpia recursos y hace logout si es necesario.
        """
        if self._authenticated:
            self._logout()

    def _authenticate(self) -> None:
        """
        Autentica al usuario y obtiene token JWT.

        Raises:
            StopUser: Si la autenticación falla
        """
        try:
            response = self.client.post(
                ENDPOINTS.auth_login,
                json={
                    "cedula": self.credentials.cedula,
                    "password": self.credentials.password,
                    "organization_id": self.organization_id,
                },
                timeout=REQUEST_TIMEOUT,
                name="auth_login",
            )

            if response.status_code == 200:
                data = response.json()
                self.token = data.get("access_token") or data.get("token")
                self._authenticated = True
                logger.debug(f"Usuario {self.credentials.cedula} autenticado")
            else:
                logger.error(
                    f"Error autenticando {self.credentials.cedula}: "
                    f"{response.status_code} - {response.text}"
                )
                # Continuar sin autenticación para pruebas de health
                self._authenticated = False

        except Exception as e:
            logger.error(f"Excepción en autenticación: {e}")
            self._authenticated = False

    def _logout(self) -> None:
        """Cierra sesión del usuario."""
        if not self.token:
            return

        try:
            self.client.post(
                ENDPOINTS.auth_logout,
                headers=self._get_headers(),
                timeout=REQUEST_TIMEOUT,
                name="auth_logout",
            )
        except Exception as e:
            logger.debug(f"Error en logout: {e}")
        finally:
            self.token = None
            self._authenticated = False

    def _get_headers(self) -> Dict[str, str]:
        """
        Genera headers comunes para requests.

        Returns:
            Dict con headers incluyendo Authorization y X-Organization-ID
        """
        headers = {
            "Content-Type": "application/json",
            "X-Organization-ID": self.organization_id,
        }

        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        return headers

    def api_get(
        self,
        endpoint: str,
        name: Optional[str] = None,
        **kwargs: Any
    ) -> Any:
        """
        GET request con headers de autenticación.

        Args:
            endpoint: URL del endpoint
            name: Nombre para métricas de Locust
            **kwargs: Argumentos adicionales para requests

        Returns:
            Response object
        """
        return self.client.get(
            endpoint,
            headers=self._get_headers(),
            timeout=REQUEST_TIMEOUT,
            name=name or endpoint,
            **kwargs
        )

    def api_post(
        self,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
        **kwargs: Any
    ) -> Any:
        """
        POST request con headers de autenticación.

        Args:
            endpoint: URL del endpoint
            json_data: Datos JSON a enviar
            name: Nombre para métricas de Locust
            **kwargs: Argumentos adicionales

        Returns:
            Response object
        """
        return self.client.post(
            endpoint,
            json=json_data,
            headers=self._get_headers(),
            timeout=REQUEST_TIMEOUT,
            name=name or endpoint,
            **kwargs
        )

    def api_patch(
        self,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
        **kwargs: Any
    ) -> Any:
        """
        PATCH request con headers de autenticación.

        Args:
            endpoint: URL del endpoint
            json_data: Datos JSON a enviar
            name: Nombre para métricas de Locust
            **kwargs: Argumentos adicionales

        Returns:
            Response object
        """
        return self.client.patch(
            endpoint,
            json=json_data,
            headers=self._get_headers(),
            timeout=REQUEST_TIMEOUT,
            name=name or endpoint,
            **kwargs
        )

    def api_delete(
        self,
        endpoint: str,
        name: Optional[str] = None,
        **kwargs: Any
    ) -> Any:
        """
        DELETE request con headers de autenticación.

        Args:
            endpoint: URL del endpoint
            name: Nombre para métricas de Locust
            **kwargs: Argumentos adicionales

        Returns:
            Response object
        """
        return self.client.delete(
            endpoint,
            headers=self._get_headers(),
            timeout=REQUEST_TIMEOUT,
            name=name or endpoint,
            **kwargs
        )

    @property
    def is_authenticated(self) -> bool:
        """Indica si el usuario está autenticado."""
        return self._authenticated and self.token is not None
