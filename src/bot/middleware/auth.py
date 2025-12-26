"""
Authentication Middleware

Verifica que el usuario esté autenticado antes de ejecutar handlers protegidos.
"""

from typing import Optional, List
from telegram import Update
from telegram.ext import ContextTypes

from src.bot.middleware.base import BaseMiddleware
from src.bot.handlers.shared import MENSAJES


class AuthMiddleware(BaseMiddleware):
    """
    Middleware de autenticación.

    Verifica que el usuario esté autenticado en context.user_data.
    Permite excluir ciertos comandos de la verificación.
    """

    def __init__(
        self,
        excluded_commands: Optional[List[str]] = None,
        require_active: bool = True
    ):
        """
        Inicializa el middleware.

        Args:
            excluded_commands: Comandos que no requieren autenticación
            require_active: Si verificar que el usuario esté activo
        """
        super().__init__("auth")
        self.excluded_commands = excluded_commands or ["/start", "/help"]
        self.require_active = require_active

    async def before(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        """
        Verifica autenticación antes del handler.

        Returns:
            True si el usuario está autenticado o el comando está excluido
        """
        # Si no hay mensaje, permitir
        if not update.message:
            return True

        # Verificar si es un comando excluido
        if update.message.text:
            text = update.message.text.strip()
            for cmd in self.excluded_commands:
                if text.startswith(cmd):
                    self.logger.debug(f"Comando excluido: {cmd}")
                    return True

        # Verificar autenticación
        user_data = context.user_data or {}
        is_authenticated = user_data.get('autenticado', False)

        if not is_authenticated:
            self.logger.warning(
                f"Usuario no autenticado: {update.effective_user.id}"
            )
            await update.message.reply_text(MENSAJES['no_autenticado'])
            return False

        # Verificar si el usuario está activo
        if self.require_active:
            user_info = user_data.get('usuario', {})
            if isinstance(user_info, dict) and not user_info.get('activo', True):
                self.logger.warning(
                    f"Usuario inactivo: {user_data.get('cedula')}"
                )
                await update.message.reply_text(
                    "⏸ Cuenta suspendida\n\n"
                    "Tu cuenta ha sido desactivada.\n"
                    "Contacta al administrador."
                )
                return False

        self.logger.debug(
            f"Usuario autenticado: {user_data.get('cedula')}"
        )
        return True

    async def after(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        result
    ) -> None:
        """Actualiza último acceso del usuario."""
        user_data = context.user_data or {}
        if user_data.get('autenticado'):
            from datetime import datetime
            user_data['ultimo_acceso'] = datetime.utcnow().isoformat()


class RoleMiddleware(BaseMiddleware):
    """
    Middleware de verificación de roles.

    Verifica que el usuario tenga el rol requerido.
    """

    def __init__(self, required_roles: List[str]):
        """
        Inicializa el middleware.

        Args:
            required_roles: Lista de roles permitidos
        """
        super().__init__("role")
        self.required_roles = [r.upper() for r in required_roles]

    async def before(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        """
        Verifica el rol del usuario.

        Returns:
            True si el usuario tiene un rol permitido
        """
        user_data = context.user_data or {}
        user_rol = user_data.get('rol', '').upper()

        if user_rol not in self.required_roles:
            self.logger.warning(
                f"Acceso denegado. Rol: {user_rol}, Requerido: {self.required_roles}"
            )
            if update.message:
                await update.message.reply_text(
                    "🚫 Sin permisos\n\n"
                    "No tienes acceso a esta función."
                )
            return False

        return True


class TenantAuthMiddleware(BaseMiddleware):
    """
    Middleware de autenticación multi-tenant.

    Verifica autenticación y establece el contexto del tenant.
    """

    def __init__(self, excluded_commands: Optional[List[str]] = None):
        super().__init__("tenant_auth")
        self.excluded_commands = excluded_commands or ["/start", "/help"]

    async def before(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        """
        Verifica autenticación y establece contexto de tenant.
        """
        if not update.message:
            return True

        # Verificar comandos excluidos
        if update.message.text:
            text = update.message.text.strip()
            for cmd in self.excluded_commands:
                if text.startswith(cmd):
                    return True

        user_data = context.user_data or {}

        # Verificar autenticación
        if not user_data.get('autenticado'):
            await update.message.reply_text(MENSAJES['no_autenticado'])
            return False

        # Verificar que tenga organization_id
        org_id = user_data.get('organization_id')
        if not org_id:
            self.logger.error(
                f"Usuario sin organization_id: {user_data.get('cedula')}"
            )
            await update.message.reply_text(
                "⚠ Error de configuración\n\n"
                "Contacta al administrador."
            )
            return False

        # Establecer org_id en el contexto para fácil acceso
        context.user_data['_current_org_id'] = org_id

        return True