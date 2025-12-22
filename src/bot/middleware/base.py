"""
Base Middleware

Clase base para todos los middlewares del bot.
"""

from abc import ABC, abstractmethod
from typing import Callable, Any, Optional
from telegram import Update
from telegram.ext import ContextTypes

from src.utils.logger import get_logger


class BaseMiddleware(ABC):
    """
    Clase base abstracta para middlewares.

    Los middlewares pueden:
    - Ejecutar lógica antes del handler
    - Modificar el contexto
    - Bloquear la ejecución del handler
    - Ejecutar lógica después del handler
    """

    def __init__(self, name: Optional[str] = None):
        self.name = name or self.__class__.__name__
        self.logger = get_logger(f"middleware.{self.name}")

    @abstractmethod
    async def before(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        """
        Ejecuta antes del handler.

        Args:
            update: Update de Telegram
            context: Contexto del bot

        Returns:
            True si debe continuar, False para bloquear
        """
        pass

    async def after(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        result: Any
    ) -> None:
        """
        Ejecuta después del handler.

        Args:
            update: Update de Telegram
            context: Contexto del bot
            result: Resultado del handler
        """
        pass

    async def on_error(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        error: Exception
    ) -> None:
        """
        Ejecuta cuando hay un error en el handler.

        Args:
            update: Update de Telegram
            context: Contexto del bot
            error: Excepción capturada
        """
        self.logger.error(f"Error en handler: {error}", exc_info=True)


class MiddlewareManager:
    """
    Gestor de middlewares.

    Permite registrar y ejecutar múltiples middlewares en orden.
    """

    def __init__(self):
        self.middlewares: list[BaseMiddleware] = []
        self.logger = get_logger("middleware.manager")

    def add(self, middleware: BaseMiddleware) -> "MiddlewareManager":
        """
        Agrega un middleware al pipeline.

        Args:
            middleware: Middleware a agregar

        Returns:
            Self para method chaining
        """
        self.middlewares.append(middleware)
        self.logger.debug(f"Middleware agregado: {middleware.name}")
        return self

    def remove(self, name: str) -> bool:
        """
        Remueve un middleware por nombre.

        Args:
            name: Nombre del middleware

        Returns:
            True si se removió
        """
        for i, mw in enumerate(self.middlewares):
            if mw.name == name:
                self.middlewares.pop(i)
                return True
        return False

    def wrap(self, handler: Callable) -> Callable:
        """
        Envuelve un handler con todos los middlewares.

        Args:
            handler: Handler original

        Returns:
            Handler envuelto con middlewares
        """
        async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE):
            # Ejecutar before de todos los middlewares
            for middleware in self.middlewares:
                try:
                    should_continue = await middleware.before(update, context)
                    if not should_continue:
                        self.logger.debug(
                            f"Handler bloqueado por {middleware.name}"
                        )
                        return
                except Exception as e:
                    self.logger.error(
                        f"Error en {middleware.name}.before: {e}"
                    )
                    await middleware.on_error(update, context, e)
                    return

            # Ejecutar handler
            result = None
            error = None
            try:
                result = await handler(update, context)
            except Exception as e:
                error = e
                # Ejecutar on_error de todos los middlewares
                for middleware in reversed(self.middlewares):
                    try:
                        await middleware.on_error(update, context, e)
                    except Exception as mw_error:
                        self.logger.error(
                            f"Error en {middleware.name}.on_error: {mw_error}"
                        )

            # Ejecutar after de todos los middlewares (en orden inverso)
            if error is None:
                for middleware in reversed(self.middlewares):
                    try:
                        await middleware.after(update, context, result)
                    except Exception as e:
                        self.logger.error(
                            f"Error en {middleware.name}.after: {e}"
                        )

            if error:
                raise error

            return result

        return wrapped


# Instancia global del manager
middleware_manager = MiddlewareManager()


def apply_middleware(*middlewares: BaseMiddleware):
    """
    Decorador para aplicar middlewares a un handler.

    Uso:
        @apply_middleware(AuthMiddleware(), RateLimitMiddleware())
        async def my_handler(update, context):
            ...
    """
    def decorator(handler: Callable) -> Callable:
        manager = MiddlewareManager()
        for mw in middlewares:
            manager.add(mw)
        return manager.wrap(handler)
    return decorator