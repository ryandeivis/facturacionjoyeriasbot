"""
Error Handler Middleware

Manejo centralizado de errores en handlers del bot.
"""

from typing import Optional, Callable, Dict, Type
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from src.bot.middleware.base import BaseMiddleware
from src.bot.handlers.shared import MENSAJES


class ErrorMiddleware(BaseMiddleware):
    """
    Middleware de manejo de errores.

    Captura excepciones en handlers y proporciona respuestas amigables.
    """

    # Mensajes de error por tipo de excepción
    ERROR_MESSAGES: Dict[Type[Exception], str] = {
        ValueError: "Datos inválidos. Por favor verifica e intenta de nuevo.",
        TimeoutError: "La operación tardó demasiado. Intenta de nuevo.",
        ConnectionError: "Error de conexión. Verifica tu internet.",
        PermissionError: "No tienes permisos para esta acción.",
    }

    def __init__(
        self,
        default_message: str = None,
        notify_user: bool = True,
        end_conversation: bool = True,
        error_callback: Optional[Callable] = None
    ):
        """
        Inicializa el middleware.

        Args:
            default_message: Mensaje por defecto para errores
            notify_user: Si notificar al usuario del error
            end_conversation: Si terminar la conversación en error
            error_callback: Callback personalizado para errores
        """
        super().__init__("error_handler")
        self.default_message = default_message or MENSAJES['error_general']
        self.notify_user = notify_user
        self.end_conversation = end_conversation
        self.error_callback = error_callback

    def _get_error_message(self, error: Exception) -> str:
        """Obtiene mensaje amigable para el tipo de error."""
        for error_type, message in self.ERROR_MESSAGES.items():
            if isinstance(error, error_type):
                return message
        return self.default_message

    async def before(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        """Siempre permite continuar (los errores se manejan en on_error)."""
        return True

    async def on_error(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        error: Exception
    ) -> None:
        """Maneja errores de forma centralizada."""
        # Log detallado del error
        user_id = update.effective_user.id if update.effective_user else "unknown"
        chat_id = update.effective_chat.id if update.effective_chat else "unknown"

        self.logger.error(
            f"Error en handler | "
            f"User: {user_id} | "
            f"Chat: {chat_id} | "
            f"Error: {type(error).__name__}: {str(error)}",
            exc_info=True
        )

        # Ejecutar callback personalizado si existe
        if self.error_callback:
            try:
                await self.error_callback(update, context, error)
            except Exception as callback_error:
                self.logger.error(f"Error en callback: {callback_error}")

        # Notificar al usuario
        if self.notify_user and update.message:
            error_message = self._get_error_message(error)
            try:
                await update.message.reply_text(error_message)
            except Exception as notify_error:
                self.logger.error(f"Error notificando usuario: {notify_error}")


class RecoveryMiddleware(BaseMiddleware):
    """
    Middleware de recuperación de errores.

    Intenta recuperarse de errores comunes automáticamente.
    """

    def __init__(
        self,
        max_retries: int = 2,
        retry_delay: float = 0.5
    ):
        """
        Inicializa el middleware.

        Args:
            max_retries: Número máximo de reintentos
            retry_delay: Delay entre reintentos en segundos
        """
        super().__init__("recovery")
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    async def before(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        """Inicializa contador de reintentos."""
        if '_retry_count' not in context.user_data:
            context.user_data['_retry_count'] = 0
        return True

    async def on_error(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        error: Exception
    ) -> None:
        """Intenta recuperarse del error."""
        retry_count = context.user_data.get('_retry_count', 0)

        # Errores recuperables
        recoverable_errors = (
            TimeoutError,
            ConnectionError,
        )

        if isinstance(error, recoverable_errors) and retry_count < self.max_retries:
            context.user_data['_retry_count'] = retry_count + 1
            self.logger.warning(
                f"Error recuperable, reintentando ({retry_count + 1}/{self.max_retries})"
            )

            # Delay antes de reintentar
            import asyncio
            await asyncio.sleep(self.retry_delay)

            # El retry se manejará en el siguiente ciclo
            return

        # Resetear contador si no es recuperable o se agotaron reintentos
        context.user_data['_retry_count'] = 0

        if retry_count >= self.max_retries:
            self.logger.error(
                f"Reintentos agotados para error: {type(error).__name__}"
            )


class ConversationErrorMiddleware(BaseMiddleware):
    """
    Middleware especializado para errores en ConversationHandler.

    Limpia el estado de la conversación cuando hay errores.
    """

    def __init__(self, fallback_state: int = ConversationHandler.END):
        """
        Inicializa el middleware.

        Args:
            fallback_state: Estado al que volver en caso de error
        """
        super().__init__("conversation_error")
        self.fallback_state = fallback_state

    async def before(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        return True

    async def on_error(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        error: Exception
    ) -> None:
        """Limpia estado de conversación y notifica al usuario."""
        self.logger.error(f"Error en conversación: {error}")

        # Limpiar datos de conversación
        from src.bot.handlers.shared import limpiar_datos_factura

        try:
            limpiar_datos_factura(context)
        except Exception as cleanup_error:
            self.logger.error(f"Error limpiando datos: {cleanup_error}")

        # Notificar al usuario
        if update.message:
            try:
                await update.message.reply_text(
                    "Ocurrió un error. La operación ha sido cancelada.\n"
                    "Usa /menu para volver al menú principal."
                )
            except Exception:
                pass