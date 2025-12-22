"""
Configuración centralizada del sistema

Carga variables de entorno y proporciona acceso a configuración
en todo el proyecto.
"""

from pydantic_settings import BaseSettings
from pydantic import SecretStr, field_validator
from typing import Optional

from config.environments import Environment, get_config


class Settings(BaseSettings):
    """Configuración del sistema con soporte multi-entorno"""

    # Entorno
    ENVIRONMENT: Environment = Environment.DEVELOPMENT

    # Información del proyecto
    PROJECT_NAME: str = "Jewelry Invoice Bot"
    VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str = ""

    # Base de datos
    DATABASE_URL: str = "sqlite+aiosqlite:///jewelry_invoices.db"
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_RECYCLE: int = 3600
    DATABASE_ECHO: bool = False

    # n8n Integration
    N8N_WEBHOOK_URL: str = ""  # Webhook para extracción de datos (texto/voz/foto)
    N8N_PDF_WEBHOOK_URL: str = ""  # Webhook para generación de PDF
    N8N_TIMEOUT_SECONDS: int = 60

    # Seguridad
    SECRET_KEY: SecretStr = SecretStr("")
    ENCRYPTION_KEY: Optional[str] = None
    JWT_EXPIRATION_HOURS: int = 24
    PASSWORD_MIN_LENGTH: int = 8

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60

    # Archivos
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 10

    # Formato de factura
    INVOICE_PREFIX: str = "JOY"
    TAX_RATE: float = 0.19  # Tasa de IVA (19% Colombia por defecto)

    # Feature Flags
    FEATURE_VOICE_INPUT: bool = True
    FEATURE_PHOTO_INPUT: bool = True
    FEATURE_MULTI_TENANT: bool = True

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # json o console

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str, info) -> str:
        """Valida que no se use SQLite en producción"""
        values = info.data
        if values.get("ENVIRONMENT") == Environment.PRODUCTION:
            if "sqlite" in v.lower():
                raise ValueError("SQLite no está permitido en producción. Use PostgreSQL.")
        return v

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: SecretStr, info) -> SecretStr:
        """Valida que SECRET_KEY esté configurado en producción"""
        values = info.data
        if values.get("ENVIRONMENT") == Environment.PRODUCTION:
            if not v.get_secret_value() or len(v.get_secret_value()) < 32:
                raise ValueError("SECRET_KEY debe tener al menos 32 caracteres en producción")
        return v

    def get_async_database_url(self) -> str:
        """Retorna la URL de base de datos para async"""
        url = self.DATABASE_URL

        # Convertir URL sync a async si es necesario
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://")
        elif url.startswith("sqlite:///"):
            return url.replace("sqlite:///", "sqlite+aiosqlite:///")

        return url

    def get_sync_database_url(self) -> str:
        """Retorna la URL de base de datos para sync (migraciones)"""
        url = self.DATABASE_URL

        # Convertir URL async a sync para Alembic
        if "asyncpg" in url:
            return url.replace("postgresql+asyncpg://", "postgresql://")
        elif "aiosqlite" in url:
            return url.replace("sqlite+aiosqlite:///", "sqlite:///")

        return url

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


# Instancia única de configuración
settings = Settings()

# Aplicar configuración del entorno
env_config = get_config(settings.ENVIRONMENT)
if not settings.DEBUG:
    settings.DEBUG = env_config.DEBUG