"""
Audit Middleware

Registra todas las acciones de los usuarios para auditoría.
"""

from typing import Optional, Dict, Any
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from src.bot.middleware.base import BaseMiddleware


class AuditMiddleware(BaseMiddleware):
    """
    Middleware de auditoría.

    Registra todas las interacciones del usuario con el bot.
    """

    def __init__(
        self,
        log_messages: bool = True,
        log_commands: bool = True,
        log_callbacks: bool = True,
        sensitive_commands: Optional[list] = None
    ):
        """
        Inicializa el middleware.

        Args:
            log_messages: Si registrar mensajes de texto
            log_commands: Si registrar comandos
            log_callbacks: Si registrar callbacks de botones
            sensitive_commands: Comandos cuyos argumentos no se loggean
        """
        super().__init__("audit")
        self.log_messages = log_messages
        self.log_commands = log_commands
        self.log_callbacks = log_callbacks
        self.sensitive_commands = sensitive_commands or ["/login", "/password"]

    def _extract_action_info(self, update: Update) -> Dict[str, Any]:
        """Extrae información de la acción del update."""
        info: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": None,
            "username": None,
            "action_type": None,
            "action_data": None,
            "chat_id": None,
        }

        if update.effective_user:
            info["user_id"] = update.effective_user.id
            info["username"] = update.effective_user.username

        if update.effective_chat:
            info["chat_id"] = update.effective_chat.id

        # Determinar tipo de acción
        if update.message:
            if update.message.text:
                text = update.message.text.strip()

                if text.startswith("/"):
                    info["action_type"] = "command"
                    # Sanitizar comandos sensibles
                    parts = text.split(maxsplit=1)
                    cmd = parts[0]
                    if cmd in self.sensitive_commands:
                        info["action_data"] = f"{cmd} [REDACTED]"
                    else:
                        info["action_data"] = text[:100]  # Limitar longitud
                else:
                    info["action_type"] = "message"
                    # No loggear contenido completo de mensajes
                    info["action_data"] = f"[TEXT:{len(text)} chars]"

            elif update.message.voice:
                info["action_type"] = "voice"
                info["action_data"] = f"[VOICE:{update.message.voice.duration}s]"

            elif update.message.photo:
                info["action_type"] = "photo"
                info["action_data"] = "[PHOTO]"

            elif update.message.document:
                info["action_type"] = "document"
                info["action_data"] = f"[DOC:{update.message.document.file_name}]"

        elif update.callback_query:
            info["action_type"] = "callback"
            info["action_data"] = update.callback_query.data

        return info

    async def before(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        """Registra la acción antes de procesarla."""
        action_info = self._extract_action_info(update)

        # Agregar info del contexto de usuario
        user_data = context.user_data or {}
        action_info["authenticated"] = user_data.get('autenticado', False)
        action_info["cedula"] = user_data.get('cedula')
        action_info["organization_id"] = user_data.get('organization_id')
        action_info["rol"] = user_data.get('rol')

        # Almacenar en contexto para uso posterior
        context.user_data['_current_action'] = action_info

        # Log según tipo
        action_type = action_info.get("action_type")

        if action_type == "command" and self.log_commands:
            self.logger.info(
                f"Command: {action_info['action_data']} | "
                f"User: {action_info['cedula'] or action_info['user_id']} | "
                f"Org: {action_info['organization_id']}"
            )
        elif action_type == "message" and self.log_messages:
            self.logger.debug(
                f"Message: {action_info['action_data']} | "
                f"User: {action_info['cedula'] or action_info['user_id']}"
            )
        elif action_type == "callback" and self.log_callbacks:
            self.logger.debug(
                f"Callback: {action_info['action_data']} | "
                f"User: {action_info['cedula'] or action_info['user_id']}"
            )
        elif action_type in ["voice", "photo", "document"]:
            self.logger.info(
                f"Media: {action_info['action_data']} | "
                f"User: {action_info['cedula'] or action_info['user_id']}"
            )

        return True

    async def after(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        result: Any
    ) -> None:
        """Registra el resultado de la acción."""
        action_info = context.user_data.get('_current_action', {})

        if action_info.get('action_type') == 'command':
            self.logger.debug(
                f"Command completed: {action_info.get('action_data')} | "
                f"Result: {type(result).__name__ if result else 'None'}"
            )

    async def on_error(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        error: Exception
    ) -> None:
        """Registra errores en las acciones."""
        action_info = context.user_data.get('_current_action', {})

        self.logger.error(
            f"Action failed: {action_info.get('action_type')} | "
            f"Data: {action_info.get('action_data')} | "
            f"User: {action_info.get('cedula') or action_info.get('user_id')} | "
            f"Error: {str(error)}"
        )


class DatabaseAuditMiddleware(AuditMiddleware):
    """
    Middleware de auditoría que persiste en base de datos.

    Extiende AuditMiddleware para guardar logs en la tabla audit_logs.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._pending_logs = []

    async def after(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        result: Any
    ) -> None:
        """Persiste el log de auditoría en la base de datos."""
        await super().after(update, context, result)

        action_info = context.user_data.get('_current_action', {})

        # Solo persistir acciones significativas
        if action_info.get('action_type') not in ['command', 'callback']:
            return

        # Solo si está autenticado
        if not action_info.get('authenticated'):
            return

        try:
            from src.core.context import get_app_context
            from src.database.models import AuditLog

            ctx = get_app_context()

            async with ctx.db.get_session() as session:
                audit_log = AuditLog(
                    organization_id=action_info.get('organization_id'),
                    usuario_cedula=action_info.get('cedula', 'unknown'),
                    accion=f"bot:{action_info.get('action_type')}",
                    entidad_tipo="telegram",
                    entidad_id=str(action_info.get('chat_id')),
                    detalles=action_info.get('action_data'),
                )
                session.add(audit_log)

        except Exception as e:
            self.logger.error(f"Error persistiendo audit log: {e}")