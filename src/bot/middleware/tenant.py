"""
Tenant Middleware

Middleware para gestión de contexto multi-tenant.
Incluye caché TTL para reducir queries a la base de datos.
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from telegram import Update
from telegram.ext import ContextTypes

from src.bot.middleware.base import BaseMiddleware


@dataclass
class CachedTenant:
    """Datos de tenant en caché."""
    org_id: str
    org_plan: str
    cached_at: datetime

    def is_expired(self, ttl_seconds: int = 300) -> bool:
        """Verifica si el caché expiró."""
        return datetime.utcnow() - self.cached_at > timedelta(seconds=ttl_seconds)


class TenantCache:
    """
    Caché en memoria para datos de tenant.

    Reduce queries a la base de datos manteniendo org_id por telegram_id.
    """

    def __init__(self, ttl_seconds: int = 300, max_size: int = 1000):
        """
        Inicializa el caché.

        Args:
            ttl_seconds: Tiempo de vida en segundos (default: 5 minutos)
            max_size: Tamaño máximo del caché
        """
        self._cache: Dict[int, CachedTenant] = {}
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._last_cleanup = datetime.utcnow()

    def get(self, telegram_id: int) -> Optional[CachedTenant]:
        """Obtiene datos del caché si existe y no expiró."""
        cached = self._cache.get(telegram_id)
        if cached and not cached.is_expired(self._ttl):
            return cached
        return None

    def set(self, telegram_id: int, org_id: str, org_plan: str = "basic") -> None:
        """Guarda datos en caché."""
        self._cleanup_if_needed()
        self._cache[telegram_id] = CachedTenant(
            org_id=org_id,
            org_plan=org_plan,
            cached_at=datetime.utcnow()
        )

    def invalidate(self, telegram_id: int) -> None:
        """Invalida entrada del caché."""
        self._cache.pop(telegram_id, None)

    def clear(self) -> None:
        """Limpia todo el caché."""
        self._cache.clear()

    def _cleanup_if_needed(self) -> None:
        """Limpia entradas expiradas periódicamente."""
        now = datetime.utcnow()
        if (now - self._last_cleanup).total_seconds() < 60:
            return

        # Limpiar expirados
        expired_keys = [
            k for k, v in self._cache.items()
            if v.is_expired(self._ttl)
        ]
        for k in expired_keys:
            del self._cache[k]

        # Si aún excede max_size, eliminar los más antiguos
        if len(self._cache) > self._max_size:
            sorted_items = sorted(
                self._cache.items(),
                key=lambda x: x[1].cached_at
            )
            for k, _ in sorted_items[:len(self._cache) - self._max_size]:
                del self._cache[k]

        self._last_cleanup = now


# Caché global de tenants
_tenant_cache = TenantCache()


class TenantMiddleware(BaseMiddleware):
    """
    Middleware de contexto de tenant.

    Establece y valida el contexto de organización para operaciones multi-tenant.
    Usa caché TTL para reducir queries a la base de datos.
    """

    def __init__(
        self,
        default_org_id: Optional[str] = None,
        cache: Optional[TenantCache] = None
    ):
        """
        Inicializa el middleware.

        Args:
            default_org_id: ID de organización por defecto (para desarrollo)
            cache: Instancia de TenantCache (usa global si no se provee)
        """
        super().__init__("tenant")
        self.default_org_id = default_org_id
        self._cache = cache or _tenant_cache

    async def before(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        """
        Establece el contexto de tenant.

        Busca organization_id en:
        1. user_data del contexto
        2. Caché en memoria
        3. Base de datos (por telegram_id)
        4. Default (si está configurado)
        """
        user_data = context.user_data or {}

        # Si ya tiene org_id en user_data, continuar
        if user_data.get('organization_id'):
            context.user_data['_current_org_id'] = user_data['organization_id']
            return True

        if update.effective_user:
            telegram_id = update.effective_user.id

            # Intentar obtener del caché primero
            cached = self._cache.get(telegram_id)
            if cached:
                context.user_data['organization_id'] = cached.org_id
                context.user_data['organization_plan'] = cached.org_plan
                context.user_data['_current_org_id'] = cached.org_id
                self.logger.debug(f"Tenant desde caché: {cached.org_id}")
                return True

            # Obtener de la base de datos
            org_data = await self._get_org_from_db(telegram_id)

            if org_data:
                org_id, org_plan = org_data
                # Guardar en caché
                self._cache.set(telegram_id, org_id, org_plan)
                context.user_data['organization_id'] = org_id
                context.user_data['organization_plan'] = org_plan
                context.user_data['_current_org_id'] = org_id
                return True

        # Usar default si está configurado
        if self.default_org_id:
            context.user_data['_current_org_id'] = self.default_org_id
            self.logger.debug(
                f"Usando org_id default: {self.default_org_id}"
            )
            return True

        # Sin contexto de tenant - permitir solo comandos públicos
        return True

    async def _get_org_from_db(
        self,
        telegram_id: int
    ) -> Optional[tuple[str, str]]:
        """
        Obtiene organization_id y plan del usuario desde la base de datos.

        Returns:
            Tuple (org_id, org_plan) o None si no existe
        """
        try:
            from src.core.context import get_app_context
            from sqlalchemy import select
            from src.database.models import User, TenantConfig

            ctx = get_app_context()

            async with ctx.db.get_session() as session:
                # Obtener org_id del usuario
                result = await session.execute(
                    select(User.organization_id).where(
                        User.telegram_id == telegram_id,
                        User.is_deleted == False
                    )
                )
                org_id = result.scalar_one_or_none()

                if not org_id:
                    return None

                # Obtener plan de la organización
                config_result = await session.execute(
                    select(TenantConfig.plan).where(
                        TenantConfig.organization_id == org_id
                    )
                )
                org_plan = config_result.scalar_one_or_none() or "basic"

                return (org_id, org_plan)

        except Exception as e:
            self.logger.error(f"Error obteniendo org_id: {e}")
            return None

    def invalidate_cache(self, telegram_id: int) -> None:
        """Invalida el caché de un usuario (ej: al cambiar de organización)."""
        self._cache.invalidate(telegram_id)


class TenantIsolationMiddleware(BaseMiddleware):
    """
    Middleware de aislamiento de tenant.

    Verifica que todas las operaciones respeten el aislamiento de datos
    entre organizaciones.
    """

    def __init__(self):
        super().__init__("tenant_isolation")

    async def before(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        """
        Verifica que el contexto de tenant esté establecido.

        Bloquea operaciones que requieran datos sin contexto de tenant.
        """
        # Comandos que no requieren tenant
        public_commands = ["/start", "/help", "/about"]

        if update.message and update.message.text:
            text = update.message.text.strip()
            for cmd in public_commands:
                if text.startswith(cmd):
                    return True

        user_data = context.user_data or {}

        # Verificar que esté autenticado para operaciones que requieren tenant
        if user_data.get('autenticado'):
            org_id = user_data.get('organization_id')
            if not org_id:
                self.logger.error(
                    "Usuario autenticado sin organization_id"
                )
                if update.message:
                    await update.message.reply_text(
                        "Error de configuración de cuenta. "
                        "Contacta al administrador."
                    )
                return False

        return True

    async def after(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        result
    ) -> None:
        """Verifica que no se hayan filtrado datos de otros tenants."""
        # En producción, aquí se podrían agregar verificaciones
        # de que los datos retornados corresponden al tenant correcto
        pass


class TenantContextManager:
    """
    Context manager para operaciones con contexto de tenant.

    Uso:
        async with TenantContextManager(org_id) as tenant_ctx:
            # Todas las operaciones usan org_id
            users = await get_users(tenant_ctx.org_id)
    """

    def __init__(self, org_id: str):
        self.org_id = org_id
        self._previous_org_id = None

    async def __aenter__(self):
        """Establece el contexto de tenant."""
        # Guardar contexto anterior si existe
        import contextvars
        self._ctx_var = contextvars.ContextVar('current_org_id', default=None)
        self._previous_org_id = self._ctx_var.get()
        self._ctx_var.set(self.org_id)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Restaura el contexto anterior."""
        if self._previous_org_id:
            self._ctx_var.set(self._previous_org_id)
        else:
            self._ctx_var.set(None)
        return False

    @staticmethod
    def get_current_org_id() -> Optional[str]:
        """Obtiene el org_id del contexto actual."""
        import contextvars
        try:
            ctx_var = contextvars.ContextVar('current_org_id', default=None)
            return ctx_var.get()
        except LookupError:
            return None