"""
Configuración centralizada del sistema

Carga variables de entorno y proporciona acceso a configuración
en todo el proyecto.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Configuración del sistema"""

    # Información del proyecto
    PROJECT_NAME: str = "Jewelry Invoice Bot"
    VERSION: str = "1.0.0"

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str = ""

    # Base de datos
    DATABASE_URL: str = "sqlite:///jewelry_invoices.db"
    DATABASE_ECHO: bool = False

    # n8n Integration
    N8N_WEBHOOK_URL: str = ""
    N8N_TIMEOUT_SECONDS: int = 60

    # Seguridad
    SECRET_KEY: str = ""

    # Archivos
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 10

    # Formato de factura
    INVOICE_PREFIX: str = "JOY"

    class Config:
        env_file = ".env"
        case_sensitive = True


# Instancia única de configuración
settings = Settings()