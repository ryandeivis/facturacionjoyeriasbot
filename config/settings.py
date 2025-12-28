"""
Configuración centralizada del sistema

Carga variables de entorno y proporciona acceso a configuración
en todo el proyecto.

Uso:
    from config.settings import settings

    timeout = settings.N8N_TIMEOUT_SECONDS
    max_login = settings.RATE_LIMIT_LOGIN_MAX
"""

from pydantic_settings import BaseSettings
from pydantic import SecretStr, field_validator
from typing import Optional

from config.environments import Environment, get_config


class Settings(BaseSettings):
    """
    Configuración del sistema con soporte multi-entorno.

    Todas las configuraciones se cargan desde variables de entorno
    o archivo .env, con valores por defecto sensatos para desarrollo.
    """

    # =========================================================================
    # ENTORNO
    # =========================================================================
    ENVIRONMENT: Environment = Environment.DEVELOPMENT
    DEBUG: bool = False

    # =========================================================================
    # INFORMACIÓN DEL PROYECTO
    # =========================================================================
    PROJECT_NAME: str = "Jewelry Invoice Bot"
    VERSION: str = "1.0.0"
    API_VERSION: str = "v1"

    # =========================================================================
    # TELEGRAM BOT
    # =========================================================================
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_WEBHOOK_URL: Optional[str] = None  # Para producción con webhook
    TELEGRAM_MAX_CONNECTIONS: int = 40

    # =========================================================================
    # BASE DE DATOS
    # =========================================================================
    DATABASE_URL: str = "sqlite+aiosqlite:///jewelry_invoices.db"
    DATABASE_ECHO: bool = False

    # Pool de conexiones - Configuración por entorno
    # Desarrollo: valores bajos para recursos locales
    # Producción: valores altos para concurrencia
    DATABASE_POOL_SIZE: int = 5  # Conexiones base (dev: 5, prod: 30)
    DATABASE_MAX_OVERFLOW: int = 10  # Conexiones extra en picos (dev: 10, prod: 20)
    DATABASE_POOL_TIMEOUT: int = 30  # Segundos máximos esperando conexión
    DATABASE_POOL_RECYCLE: int = 1800  # Reciclar conexiones cada 30 min (evita stale)
    DATABASE_POOL_PRE_PING: bool = True  # Verificar conexión antes de usar
    DATABASE_CONNECT_TIMEOUT: int = 10  # Timeout de conexión inicial

    # =========================================================================
    # N8N INTEGRATION
    # =========================================================================
    N8N_WEBHOOK_URL: str = ""  # Webhook para extracción de datos
    N8N_PDF_WEBHOOK_URL: str = ""  # Webhook para generación de PDF
    N8N_TIMEOUT_SECONDS: int = 60
    N8N_MAX_RETRIES: int = 3
    N8N_RETRY_DELAY_SECONDS: int = 2

    # =========================================================================
    # SEGURIDAD
    # =========================================================================
    SECRET_KEY: SecretStr = SecretStr("")
    ENCRYPTION_KEY: Optional[str] = None
    JWT_EXPIRATION_HOURS: int = 24
    JWT_REFRESH_HOURS: int = 168  # 7 días
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_REQUIRE_SPECIAL: bool = True
    SESSION_TIMEOUT_MINUTES: int = 60

    # =========================================================================
    # RATE LIMITING - General
    # =========================================================================
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60

    # Rate Limiting - Login (anti fuerza bruta)
    RATE_LIMIT_LOGIN_MAX: int = 5
    RATE_LIMIT_LOGIN_WINDOW: int = 60
    RATE_LIMIT_LOGIN_BLOCK: int = 300  # 5 minutos de bloqueo

    # Rate Limiting - n8n API
    RATE_LIMIT_N8N_MAX: int = 20
    RATE_LIMIT_N8N_WINDOW: int = 60

    # Rate Limiting - Creación de facturas
    RATE_LIMIT_INVOICE_MAX: int = 10
    RATE_LIMIT_INVOICE_WINDOW: int = 300  # 5 minutos

    # Rate Limiting - Mensajes generales
    RATE_LIMIT_MESSAGE_MAX: int = 30
    RATE_LIMIT_MESSAGE_WINDOW: int = 60

    # =========================================================================
    # ARCHIVOS
    # =========================================================================
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_IMAGE_TYPES: str = "jpg,jpeg,png,webp"
    ALLOWED_AUDIO_TYPES: str = "ogg,mp3,wav"
    MAX_VOICE_DURATION_SECONDS: int = 300  # 5 minutos

    # =========================================================================
    # FACTURACIÓN
    # =========================================================================
    INVOICE_PREFIX: str = "JOY"
    TAX_RATE: float = 0.19  # IVA Colombia
    INVOICE_EXPIRY_DAYS: int = 30
    MAX_ITEMS_PER_INVOICE: int = 50
    MAX_INVOICE_TOTAL: float = 9999999999.0

    # =========================================================================
    # FEATURE FLAGS
    # =========================================================================
    FEATURE_VOICE_INPUT: bool = True
    FEATURE_PHOTO_INPUT: bool = True
    FEATURE_MULTI_TENANT: bool = True
    FEATURE_PDF_GENERATION: bool = True
    FEATURE_AUDIT_LOG: bool = True
    FEATURE_METRICS: bool = True

    # =========================================================================
    # LOGGING
    # =========================================================================
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # json o console
    LOG_DIR: str = "logs"
    LOG_MAX_SIZE_MB: int = 50
    LOG_BACKUP_COUNT: int = 10

    # =========================================================================
    # MONITOREO Y HEALTH
    # =========================================================================
    HEALTH_CHECK_ENABLED: bool = True
    METRICS_ENABLED: bool = True
    METRICS_PORT: int = 9090

    # =========================================================================
    # SAAS / MULTI-TENANT
    # =========================================================================
    DEFAULT_TENANT_ID: str = "default"
    MAX_USERS_PER_TENANT: int = 100
    MAX_INVOICES_PER_MONTH: int = 1000

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

    def get_allowed_image_types(self) -> list:
        """Retorna lista de tipos de imagen permitidos."""
        return [t.strip() for t in self.ALLOWED_IMAGE_TYPES.split(",")]

    def get_allowed_audio_types(self) -> list:
        """Retorna lista de tipos de audio permitidos."""
        return [t.strip() for t in self.ALLOWED_AUDIO_TYPES.split(",")]

    def get_max_upload_bytes(self) -> int:
        """Retorna el tamaño máximo de upload en bytes."""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    def is_production(self) -> bool:
        """Verifica si está en producción."""
        return self.ENVIRONMENT == Environment.PRODUCTION

    def is_development(self) -> bool:
        """Verifica si está en desarrollo."""
        return self.ENVIRONMENT == Environment.DEVELOPMENT

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