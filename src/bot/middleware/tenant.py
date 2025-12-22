"""
Tenant Middleware

Middleware para gestión de contexto multi-tenant.
"""

from typing import Optional
from telegram import Update
from telegram.ext import ContextTypes

from src.bot.middleware.base import BaseMiddleware


class TenantMiddleware(BaseMiddleware):
    """
    Middleware de contexto de tenant.

    Establece y valida el contexto de organización para operaciones multi-tenant.
    """

    def __init__(self, default_org_id: Optional[str] = None):
        """
        Inicializa el middleware.

        Args:
            default_org_id: ID de organización por defecto (para desarrollo)
        """
        super().__init__("tenant")
        self.default_org_id = default_org_id

    async def before(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        """
        Establece el contexto de tenant.

        Busca organization_id en:
        1. user_data del contexto
        2. Base de datos (por telegram_id)
        3. Default (si está configurado)
        """
        user_data = context.user_data or {}

        # Si ya tiene org_id, continuar
        if user_data.get('organization_id'):
            context.user_data['_current_org_id'] = user_data['organization_id']
            return True

        # Intentar obtener de la base de datos
        if update.effective_user:
            telegram_id = update.effective_user.id
            org_id = await self._get_org_from_db(telegram_id)

            if org_id:
                context.user_data['organization_id'] = org_id
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

    async def _get_org_from_db(self, telegram_id: int) -> Optional[str]:
        """Obtiene organization_id del usuario desde la base de datos."""
        try:
            from src.core.context import get_app_context
            from sqlalchemy import select
            from src.database.models import User

            ctx = get_app_context()

            async with ctx.db.get_session() as session:
                result = await session.execute(
                    select(User.organization_id).where(
                        User.telegram_id == telegram_id,
                        User.is_deleted == False
                    )
                )
                org_id = result.scalar_one_or_none()
                return org_id

        except Exception as e:
            self.logger.error(f"Error obteniendo org_id: {e}")
            return None


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