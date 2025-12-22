"""
Application Context

Contenedor de dependencias para inyección en toda la aplicación.
Implementa el patrón Dependency Injection para mejor testabilidad.
"""

from dataclasses import dataclass, field
from typing import Protocol, Optional, AsyncGenerator, Any
from contextlib import asynccontextmanager
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings, Settings
from src.utils.logger import get_logger


# ============================================================================
# PROTOCOLOS (Interfaces)
# ============================================================================

class DatabaseProviderProtocol(Protocol):
    """Protocolo para proveedores de base de datos."""

    async def initialize(self) -> None:
        """Inicializa la conexión."""
        ...

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Proporciona una sesión de base de datos."""
        ...

    async def close(self) -> None:
        """Cierra las conexiones."""
        ...


class N8NServiceProtocol(Protocol):
    """Protocolo para el servicio de N8N."""

    async def send_text_input(self, text: str, user_id: int, org_id: str) -> dict:
        """Envía texto a N8N para procesamiento."""
        ...

    async def send_voice_input(self, audio_path: str, user_id: int, org_id: str) -> dict:
        """Envía audio a N8N para procesamiento."""
        ...

    async def send_photo_input(self, photo_path: str, user_id: int, org_id: str) -> dict:
        """Envía foto a N8N para procesamiento."""
        ...


class CryptoServiceProtocol(Protocol):
    """Protocolo para servicios de criptografía."""

    def hash_password(self, password: str) -> str:
        """Hash de contraseña."""
        ...

    def verify_password(self, password: str, hashed: str) -> bool:
        """Verifica contraseña."""
        ...

    def create_access_token(self, user_id: int, org_id: str) -> str:
        """Crea token JWT."""
        ...

    def verify_token(self, token: str) -> dict:
        """Verifica token JWT."""
        ...


class AuditServiceProtocol(Protocol):
    """Protocolo para servicio de auditoría."""

    async def log(
        self,
        user_id: int,
        org_id: str,
        action: str,
        entity_type: str,
        entity_id: str,
        details: Optional[dict] = None
    ) -> None:
        """Registra una acción de auditoría."""
        ...


# ============================================================================
# IMPLEMENTACIONES
# ============================================================================

class DatabaseProvider:
    """Proveedor de base de datos con lazy initialization."""

    def __init__(self):
        self._initialized = False
        self._session_factory = None

    async def initialize(self) -> None:
        """Inicializa la conexión a la base de datos."""
        if not self._initialized:
            from src.database.connection import init_async_db, AsyncSessionLocal
            init_async_db()
            from src.database.connection import AsyncSessionLocal as factory
            self._session_factory = factory
            self._initialized = True

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Proporciona una sesión de base de datos."""
        if not self._initialized:
            await self.initialize()

        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def close(self) -> None:
        """Cierra las conexiones."""
        from src.database.connection import close_async_db
        await close_async_db()
        self._initialized = False


class N8NServiceAdapter:
    """Adaptador para el servicio N8N existente."""

    def __init__(self):
        self._service = None

    def _get_service(self):
        if self._service is None:
            from src.services.n8n_service import n8n_service
            self._service = n8n_service
        return self._service

    async def send_text_input(self, text: str, user_id: int, org_id: str) -> dict:
        """Envía texto a N8N."""
        service = self._get_service()
        return await asyncio.to_thread(
            service.send_text_input, text
        ) if hasattr(service, 'send_text_input') else {}

    async def send_voice_input(self, audio_path: str, user_id: int, org_id: str) -> dict:
        """Envía audio a N8N."""
        service = self._get_service()
        return await asyncio.to_thread(
            service.send_voice_input, audio_path
        ) if hasattr(service, 'send_voice_input') else {}

    async def send_photo_input(self, photo_path: str, user_id: int, org_id: str) -> dict:
        """Envía foto a N8N."""
        service = self._get_service()
        return await asyncio.to_thread(
            service.send_photo_input, photo_path
        ) if hasattr(service, 'send_photo_input') else {}


# ============================================================================
# APPLICATION CONTEXT
# ============================================================================

@dataclass
class AppContext:
    """
    Contenedor de contexto de aplicación.

    Centraliza todas las dependencias de la aplicación para:
    - Facilitar testing con mocks
    - Desacoplar componentes
    - Permitir configuración por entorno

    Uso:
        ctx = AppContext.create()
        await ctx.initialize()

        async with ctx.db.get_session() as session:
            # usar session...
    """

    db: DatabaseProviderProtocol = field(default_factory=DatabaseProvider)
    n8n: N8NServiceProtocol = field(default_factory=N8NServiceAdapter)
    config: Settings = field(default_factory=lambda: settings)
    _logger: Any = field(default=None, repr=False)
    _initialized: bool = field(default=False, repr=False)

    @property
    def logger(self):
        """Logger con lazy initialization."""
        if self._logger is None:
            self._logger = get_logger("app")
        return self._logger

    async def initialize(self) -> None:
        """Inicializa todas las dependencias."""
        if not self._initialized:
            await self.db.initialize()
            self._initialized = True
            self.logger.info("AppContext inicializado")

    async def shutdown(self) -> None:
        """Cierra todas las conexiones."""
        await self.db.close()
        self._initialized = False
        self.logger.info("AppContext cerrado")

    @classmethod
    def create(cls, **overrides) -> "AppContext":
        """
        Factory method para crear el contexto.

        Args:
            **overrides: Dependencias a sobrescribir (útil para testing)

        Returns:
            Instancia de AppContext configurada
        """
        return cls(
            db=overrides.get('db', DatabaseProvider()),
            n8n=overrides.get('n8n', N8NServiceAdapter()),
            config=overrides.get('config', settings),
        )

    @classmethod
    def create_for_testing(
        cls,
        mock_db: Optional[DatabaseProviderProtocol] = None,
        mock_n8n: Optional[N8NServiceProtocol] = None,
    ) -> "AppContext":
        """
        Factory method para testing con mocks.

        Args:
            mock_db: Mock del proveedor de DB
            mock_n8n: Mock del servicio N8N

        Returns:
            Instancia de AppContext con mocks
        """
        from config.environments import DevelopmentConfig

        return cls(
            db=mock_db or DatabaseProvider(),
            n8n=mock_n8n or N8NServiceAdapter(),
            config=DevelopmentConfig(),
        )


# ============================================================================
# SINGLETON GLOBAL
# ============================================================================

_app_context: Optional[AppContext] = None


def get_app_context() -> AppContext:
    """
    Obtiene la instancia global del contexto de aplicación.

    Returns:
        Instancia de AppContext
    """
    global _app_context
    if _app_context is None:
        _app_context = AppContext.create()
    return _app_context


async def initialize_app_context() -> AppContext:
    """
    Inicializa y retorna el contexto de aplicación.

    Returns:
        Instancia inicializada de AppContext
    """
    ctx = get_app_context()
    await ctx.initialize()
    return ctx


async def shutdown_app_context() -> None:
    """Cierra el contexto de aplicación."""
    global _app_context
    if _app_context is not None:
        await _app_context.shutdown()
        _app_context = None


def set_app_context(ctx: AppContext) -> None:
    """
    Establece el contexto de aplicación global.
    Útil para testing.

    Args:
        ctx: Contexto a establecer
    """
    global _app_context
    _app_context = ctx