"""
Punto de entrada del Bot de Telegram

Configura e inicia el bot de Telegram para el sistema
de facturación de joyerías.

Incluye:
- Dependency Injection via AppContext
- Middlewares (auth, rate limit, audit, error handling)
- Multi-tenant support
"""

import os
import sys
import asyncio
from pathlib import Path

# Agregar el directorio raíz del proyecto al path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from telegram import Update
from telegram.ext import Application, CommandHandler

from config.settings import settings
from src.utils.logger import get_logger
from src.core.context import (
    get_app_context,
    initialize_app_context,
    shutdown_app_context
)
from src.bot.handlers.auth import get_auth_conversation_handler
from src.bot.handlers.invoice import get_invoice_conversation_handler
from src.bot.middleware.base import MiddlewareManager
from src.bot.middleware.auth import AuthMiddleware
from src.bot.middleware.rate_limit import RateLimitMiddleware
from src.bot.middleware.audit import AuditMiddleware
from src.bot.middleware.error_handler import ErrorMiddleware
from src.bot.middleware.tenant import TenantMiddleware

logger = get_logger(__name__)

# Middleware manager global
middleware_manager = MiddlewareManager()


def setup_middlewares() -> MiddlewareManager:
    """
    Configura los middlewares del bot.

    Returns:
        MiddlewareManager configurado
    """
    manager = MiddlewareManager()

    # Error handling (primero para capturar todo)
    manager.add(ErrorMiddleware(
        notify_user=True,
        end_conversation=True
    ))

    # Tenant context
    manager.add(TenantMiddleware(
        default_org_id=settings.DEFAULT_ORG_ID if hasattr(settings, 'DEFAULT_ORG_ID') else None
    ))

    # Rate limiting
    manager.add(RateLimitMiddleware(
        max_requests=settings.RATE_LIMIT_REQUESTS,
        window_seconds=settings.RATE_LIMIT_WINDOW
    ))

    # Audit logging
    manager.add(AuditMiddleware(
        log_messages=True,
        log_commands=True,
        log_callbacks=True
    ))

    logger.info(f"Middlewares configurados: {len(manager.middlewares)}")
    return manager


async def post_init(application: Application) -> None:
    """
    Hook que se ejecuta después de inicializar la aplicación.

    Inicializa el contexto de aplicación y la base de datos.
    """
    logger.info("Inicializando contexto de aplicación...")
    await initialize_app_context()
    logger.info("Contexto de aplicación inicializado")


async def post_shutdown(application: Application) -> None:
    """
    Hook que se ejecuta antes de cerrar la aplicación.

    Cierra conexiones y limpia recursos.
    """
    logger.info("Cerrando contexto de aplicación...")
    await shutdown_app_context()
    logger.info("Contexto de aplicación cerrado")


async def error_handler(update: Update, context) -> None:
    """
    Handler global de errores.

    Captura errores no manejados por los middlewares.
    """
    logger.error(
        f"Error no manejado: {context.error}",
        exc_info=context.error
    )

    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "Ocurrió un error inesperado. Por favor intenta de nuevo."
            )
        except Exception:
            pass


def main():
    """
    Función principal que inicia el bot.

    Configura:
    - Token de Telegram
    - Middlewares
    - Handlers de conversación
    - Hooks de inicio/cierre
    """
    # Validar que existe el token
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN no está configurado en .env")
        print("ERROR: Configura TELEGRAM_BOT_TOKEN en el archivo .env")
        return

    # Crear aplicación con hooks
    logger.info("Iniciando Bot de Facturación Joyería...")
    application = (
        Application.builder()
        .token(settings.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Configurar middlewares
    global middleware_manager
    middleware_manager = setup_middlewares()

    # Agregar handlers
    auth_handler = get_auth_conversation_handler()
    invoice_handler = get_invoice_conversation_handler()

    application.add_handler(auth_handler)
    application.add_handler(invoice_handler)

    # Handler global de errores
    application.add_error_handler(error_handler)

    # Log de inicio
    env_name = settings.ENVIRONMENT.value if hasattr(settings.ENVIRONMENT, 'value') else settings.ENVIRONMENT
    logger.info(f"Proyecto: {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info(f"Entorno: {env_name}")
    logger.info(f"Webhook n8n: {settings.N8N_WEBHOOK_URL or 'No configurado'}")
    logger.info("Bot iniciado correctamente")
    logger.info("Esperando mensajes...")

    print(f"\n{'='*50}")
    print(f"  {settings.PROJECT_NAME} v{settings.VERSION}")
    print(f"  Entorno: {env_name}")
    print(f"{'='*50}")
    print(f"  Bot iniciado correctamente")
    print(f"  Webhook n8n: {settings.N8N_WEBHOOK_URL or 'No configurado'}")
    print(f"  Esperando mensajes...")
    print(f"{'='*50}\n")

    # Iniciar bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)


async def main_async():
    """
    Versión asíncrona del punto de entrada.

    Útil para integración con otros frameworks async.
    """
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN no está configurado")
        return

    # Inicializar contexto
    await initialize_app_context()

    try:
        application = (
            Application.builder()
            .token(settings.TELEGRAM_BOT_TOKEN)
            .build()
        )

        # Configurar middlewares
        global middleware_manager
        middleware_manager = setup_middlewares()

        # Agregar handlers
        auth_handler = get_auth_conversation_handler()
        invoice_handler = get_invoice_conversation_handler()

        application.add_handler(auth_handler)
        application.add_handler(invoice_handler)
        application.add_error_handler(error_handler)

        # Iniciar
        await application.initialize()
        await application.start()
        await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)

        # Mantener corriendo
        logger.info("Bot corriendo en modo async...")
        while True:
            await asyncio.sleep(1)

    except asyncio.CancelledError:
        logger.info("Bot detenido")
    finally:
        await shutdown_app_context()


if __name__ == '__main__':
    main()