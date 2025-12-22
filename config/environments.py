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
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_RECYCLE: int = 3600
    DATABASE_ECHO: bool = False

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
    DATABASE_POOL_SIZE: int = 10


class ProductionConfig(BaseConfig):
    """Configuración para producción"""
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost/jewelry_prod"
    LOG_LEVEL: str = "WARNING"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 30

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