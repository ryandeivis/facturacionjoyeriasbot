"""
Configuración Multi-Entorno

Define perfiles de configuración para development, staging y production.
"""

from enum import Enum
from typing import Dict, Type


class Environment(str, Enum):
    """Entornos disponibles"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class BaseConfig:
    """Configuración base compartida"""
    PROJECT_NAME: str = "Jewelry Invoice Bot"
    VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database defaults
    DATABASE_ECHO: bool = False

    # Pool de conexiones - Valores base
    DATABASE_POOL_SIZE: int = 5  # Conexiones base mantenidas
    DATABASE_MAX_OVERFLOW: int = 10  # Conexiones extra en picos
    DATABASE_POOL_TIMEOUT: int = 30  # Segundos esperando conexión
    DATABASE_POOL_RECYCLE: int = 1800  # Reciclar cada 30 min
    DATABASE_POOL_PRE_PING: bool = True  # Verificar conexión viva

    # Security defaults
    JWT_EXPIRATION_HOURS: int = 24
    PASSWORD_MIN_LENGTH: int = 8

    # Rate limiting defaults
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60


class DevelopmentConfig(BaseConfig):
    """Configuración para desarrollo"""
    DEBUG: bool = True
    DATABASE_URL: str = "sqlite+aiosqlite:///jewelry_invoices.db"
    DATABASE_ECHO: bool = True
    LOG_LEVEL: str = "DEBUG"

    # Development relaxed limits
    RATE_LIMIT_REQUESTS: int = 1000
    JWT_EXPIRATION_HOURS: int = 168  # 7 days


class StagingConfig(BaseConfig):
    """Configuración para staging"""
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost/jewelry_staging"
    LOG_LEVEL: str = "INFO"

    # Pool staging: valores intermedios para testing de carga
    DATABASE_POOL_SIZE: int = 15  # 15 conexiones base
    DATABASE_MAX_OVERFLOW: int = 15  # Hasta 30 total
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 1800


class ProductionConfig(BaseConfig):
    """
    Configuración para producción.

    Pool optimizado para alta concurrencia:
    - 30 conexiones base siempre disponibles
    - 20 conexiones extra para picos (hasta 50 total)
    - Timeout de 30s para evitar esperas infinitas
    - Recycle cada 30 min para evitar conexiones stale
    - Pre-ping para detectar conexiones muertas
    """
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost/jewelry_prod"
    LOG_LEVEL: str = "WARNING"

    # Pool producción: optimizado para alta concurrencia
    DATABASE_POOL_SIZE: int = 30  # 30 conexiones base
    DATABASE_MAX_OVERFLOW: int = 20  # Hasta 50 en picos extremos
    DATABASE_POOL_TIMEOUT: int = 30  # 30s máximo de espera
    DATABASE_POOL_RECYCLE: int = 1800  # Reciclar cada 30 min
    DATABASE_POOL_PRE_PING: bool = True  # Verificar siempre

    # Production strict limits
    RATE_LIMIT_REQUESTS: int = 60
    JWT_EXPIRATION_HOURS: int = 8


def get_config(env: Environment) -> Type[BaseConfig]:
    """
    Obtiene la configuración según el entorno.

    Args:
        env: Entorno seleccionado

    Returns:
        Clase de configuración correspondiente
    """
    configs: Dict[Environment, Type[BaseConfig]] = {
        Environment.DEVELOPMENT: DevelopmentConfig,
        Environment.STAGING: StagingConfig,
        Environment.PRODUCTION: ProductionConfig,
    }
    return configs.get(env, DevelopmentConfig)