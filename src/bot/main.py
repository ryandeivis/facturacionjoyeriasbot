"""
Punto de entrada del Bot de Telegram

Configura e inicia el bot de Telegram para el sistema
de facturación de joyerías.
"""

import os
import sys
from pathlib import Path

# Agregar el directorio raíz del proyecto al path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from telegram import Update
from telegram.ext import Application

from config.settings import settings
from src.utils.logger import get_logger
from src.bot.handlers.auth import get_auth_conversation_handler
from src.bot.handlers.invoice import get_invoice_conversation_handler

logger = get_logger(__name__)


def main():
    """
    Función principal que inicia el bot
    """
    # Validar que existe el token
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN no está configurado en .env")
        print("ERROR: Configura TELEGRAM_BOT_TOKEN en el archivo .env")
        return

    # Crear aplicación
    logger.info("Iniciando Bot de Facturación Joyería...")
    application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

    # Agregar handlers
    auth_handler = get_auth_conversation_handler()
    invoice_handler = get_invoice_conversation_handler()

    application.add_handler(auth_handler)
    application.add_handler(invoice_handler)

    # Log de inicio
    logger.info(f"Proyecto: {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info(f"Webhook n8n: {settings.N8N_WEBHOOK_URL or 'No configurado'}")
    logger.info("Bot iniciado correctamente")
    logger.info("Esperando mensajes...")

    print(f"\n{'='*50}")
    print(f"  {settings.PROJECT_NAME} v{settings.VERSION}")
    print(f"{'='*50}")
    print(f"  Bot iniciado correctamente")
    print(f"  Webhook n8n: {settings.N8N_WEBHOOK_URL or 'No configurado'}")
    print(f"  Esperando mensajes...")
    print(f"{'='*50}\n")

    # Iniciar bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()