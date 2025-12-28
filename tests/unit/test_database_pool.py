"""
Tests para la configuración del pool de conexiones de base de datos.

Verifica:
- Configuración correcta de parámetros de pool por entorno
- Valores por defecto apropiados
- Validación de límites
"""

import pytest
from unittest.mock import patch, MagicMock

from config.environments import (
    Environment,
    BaseConfig,
    DevelopmentConfig,
    StagingConfig,
    ProductionConfig,
    get_config,
)


class TestPoolConfigByEnvironment:
    """Tests para configuración de pool por entorno."""

    def test_development_pool_config(self):
        """Verifica valores de pool para desarrollo."""
        config = DevelopmentConfig()

        # Desarrollo usa valores conservadores
        assert config.DATABASE_POOL_SIZE == 5
        assert config.DATABASE_MAX_OVERFLOW == 10
        assert config.DATABASE_POOL_TIMEOUT == 30
        assert config.DATABASE_POOL_RECYCLE == 1800
        assert config.DATABASE_POOL_PRE_PING is True

    def test_staging_pool_config(self):
        """Verifica valores de pool para staging."""
        config = StagingConfig()

        # Staging usa valores intermedios
        assert config.DATABASE_POOL_SIZE == 15
        assert config.DATABASE_MAX_OVERFLOW == 15
        assert config.DATABASE_POOL_TIMEOUT == 30
        assert config.DATABASE_POOL_RECYCLE == 1800

    def test_production_pool_config(self):
        """Verifica valores de pool para producción."""
        config = ProductionConfig()

        # Producción usa valores altos para concurrencia
        assert config.DATABASE_POOL_SIZE == 30
        assert config.DATABASE_MAX_OVERFLOW == 20
        assert config.DATABASE_POOL_TIMEOUT == 30
        assert config.DATABASE_POOL_RECYCLE == 1800
        assert config.DATABASE_POOL_PRE_PING is True

    def test_production_max_connections(self):
        """Verifica el total de conexiones máximas en producción."""
        config = ProductionConfig()

        max_total = config.DATABASE_POOL_SIZE + config.DATABASE_MAX_OVERFLOW
        assert max_total == 50  # 30 + 20 = 50 conexiones máximas

    def test_staging_max_connections(self):
        """Verifica el total de conexiones máximas en staging."""
        config = StagingConfig()

        max_total = config.DATABASE_POOL_SIZE + config.DATABASE_MAX_OVERFLOW
        assert max_total == 30  # 15 + 15 = 30 conexiones máximas

    def test_development_max_connections(self):
        """Verifica el total de conexiones máximas en desarrollo."""
        config = DevelopmentConfig()

        max_total = config.DATABASE_POOL_SIZE + config.DATABASE_MAX_OVERFLOW
        assert max_total == 15  # 5 + 10 = 15 conexiones máximas


class TestGetConfig:
    """Tests para la función get_config."""

    def test_get_development_config(self):
        """Verifica que get_config retorna DevelopmentConfig."""
        config = get_config(Environment.DEVELOPMENT)
        assert config == DevelopmentConfig

    def test_get_staging_config(self):
        """Verifica que get_config retorna StagingConfig."""
        config = get_config(Environment.STAGING)
        assert config == StagingConfig

    def test_get_production_config(self):
        """Verifica que get_config retorna ProductionConfig."""
        config = get_config(Environment.PRODUCTION)
        assert config == ProductionConfig


class TestPoolRecycleTime:
    """Tests para el tiempo de reciclaje de conexiones."""

    def test_recycle_time_is_30_minutes(self):
        """Verifica que las conexiones se reciclan cada 30 minutos."""
        for config_class in [DevelopmentConfig, StagingConfig, ProductionConfig]:
            config = config_class()
            # 1800 segundos = 30 minutos
            assert config.DATABASE_POOL_RECYCLE == 1800

    def test_recycle_prevents_stale_connections(self):
        """
        Verifica que el tiempo de reciclaje es menor al timeout típico
        de conexiones de PostgreSQL (que es de ~1 hora por defecto).
        """
        config = ProductionConfig()
        postgres_default_timeout = 3600  # 1 hora
        assert config.DATABASE_POOL_RECYCLE < postgres_default_timeout


class TestPoolTimeout:
    """Tests para el timeout del pool."""

    def test_timeout_is_reasonable(self):
        """Verifica que el timeout es razonable (no muy largo)."""
        config = ProductionConfig()

        # 30 segundos es suficiente para esperar una conexión
        # pero no tan largo que degrade la experiencia
        assert config.DATABASE_POOL_TIMEOUT == 30
        assert config.DATABASE_POOL_TIMEOUT <= 60  # Máximo razonable

    def test_timeout_consistent_across_environments(self):
        """Verifica que el timeout es consistente en todos los entornos."""
        dev = DevelopmentConfig()
        staging = StagingConfig()
        prod = ProductionConfig()

        assert dev.DATABASE_POOL_TIMEOUT == staging.DATABASE_POOL_TIMEOUT
        assert staging.DATABASE_POOL_TIMEOUT == prod.DATABASE_POOL_TIMEOUT


class TestPoolPrePing:
    """Tests para la verificación pre-ping."""

    def test_pre_ping_enabled_in_production(self):
        """Verifica que pre-ping está habilitado en producción."""
        config = ProductionConfig()
        assert config.DATABASE_POOL_PRE_PING is True

    def test_pre_ping_enabled_in_base(self):
        """Verifica que pre-ping está habilitado por defecto."""
        config = BaseConfig()
        assert config.DATABASE_POOL_PRE_PING is True


class TestPoolScaling:
    """Tests para verificar el escalado del pool."""

    def test_pool_scales_with_environment(self):
        """Verifica que el pool escala apropiadamente por entorno."""
        dev = DevelopmentConfig()
        staging = StagingConfig()
        prod = ProductionConfig()

        # Producción debe tener más conexiones que staging
        assert prod.DATABASE_POOL_SIZE > staging.DATABASE_POOL_SIZE

        # Staging debe tener más conexiones que desarrollo
        assert staging.DATABASE_POOL_SIZE > dev.DATABASE_POOL_SIZE

    def test_overflow_ratio_is_reasonable(self):
        """Verifica que la proporción de overflow es razonable."""
        prod = ProductionConfig()

        # El overflow no debería ser mayor que el pool base
        # para evitar crear demasiadas conexiones temporales
        assert prod.DATABASE_MAX_OVERFLOW <= prod.DATABASE_POOL_SIZE
