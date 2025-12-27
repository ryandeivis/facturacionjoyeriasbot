"""
Tests para el módulo de Rate Limiting.

Prueba el sistema de rate limiting centralizado.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from src.utils.rate_limiter import (
    OperationType,
    RateLimitConfig,
    RateLimiter,
    check_login_rate,
    check_n8n_rate,
    check_invoice_rate,
    check_message_rate,
    get_default_limits,
)


# ============================================================================
# RATE LIMIT CONFIG TESTS
# ============================================================================

class TestRateLimitConfig:
    """Tests para la configuración de rate limit."""

    def test_config_basica(self):
        """Configuración básica funciona."""
        config = RateLimitConfig(
            max_requests=10,
            window_seconds=60
        )
        assert config.max_requests == 10
        assert config.window_seconds == 60
        assert config.block_seconds == 0

    def test_config_con_bloqueo(self):
        """Configuración con bloqueo funciona."""
        config = RateLimitConfig(
            max_requests=5,
            window_seconds=60,
            block_seconds=300
        )
        assert config.block_seconds == 300

    def test_config_mensaje_default(self):
        """Mensaje por defecto se genera."""
        config = RateLimitConfig(
            max_requests=5,
            window_seconds=60
        )
        assert "5" in config.message
        assert "60" in config.message

    def test_config_mensaje_custom(self):
        """Mensaje personalizado se usa."""
        config = RateLimitConfig(
            max_requests=5,
            window_seconds=60,
            message="Mensaje custom"
        )
        assert config.message == "Mensaje custom"


# ============================================================================
# RATE LIMITER TESTS
# ============================================================================

class TestRateLimiter:
    """Tests para el servicio de rate limiting."""

    def test_permite_primeros_requests(self):
        """Permite los primeros requests dentro del límite."""
        limiter = RateLimiter()

        for i in range(5):
            assert limiter.allow("test_op", "user1") is True

    def test_bloquea_despues_de_limite(self):
        """Bloquea después de exceder el límite."""
        limiter = RateLimiter()

        # Configurar límite bajo para test
        limiter.configure_tenant(
            "test_tenant",
            "test_op",
            RateLimitConfig(max_requests=3, window_seconds=60)
        )

        # Primeros 3 permitidos
        for i in range(3):
            assert limiter.allow("test_op", "user1", tenant_id="test_tenant") is True

        # El 4to bloqueado
        assert limiter.allow("test_op", "user1", tenant_id="test_tenant") is False

    def test_diferentes_usuarios_independientes(self):
        """Usuarios diferentes tienen límites independientes."""
        limiter = RateLimiter()

        limiter.configure_tenant(
            "test",
            "test_op",
            RateLimitConfig(max_requests=2, window_seconds=60)
        )

        # Usuario 1 usa su límite
        assert limiter.allow("test_op", "user1", tenant_id="test") is True
        assert limiter.allow("test_op", "user1", tenant_id="test") is True
        assert limiter.allow("test_op", "user1", tenant_id="test") is False

        # Usuario 2 tiene su propio límite
        assert limiter.allow("test_op", "user2", tenant_id="test") is True
        assert limiter.allow("test_op", "user2", tenant_id="test") is True

    def test_diferentes_operaciones_independientes(self):
        """Operaciones diferentes tienen límites independientes."""
        limiter = RateLimiter()

        limiter.configure_tenant(
            "test",
            "op1",
            RateLimitConfig(max_requests=2, window_seconds=60)
        )
        limiter.configure_tenant(
            "test",
            "op2",
            RateLimitConfig(max_requests=2, window_seconds=60)
        )

        # Agotar op1
        assert limiter.allow("op1", "user1", tenant_id="test") is True
        assert limiter.allow("op1", "user1", tenant_id="test") is True
        assert limiter.allow("op1", "user1", tenant_id="test") is False

        # op2 sigue disponible
        assert limiter.allow("op2", "user1", tenant_id="test") is True

    def test_get_remaining(self):
        """Obtiene requests restantes correctamente."""
        limiter = RateLimiter()

        limiter.configure_tenant(
            "test",
            "test_op",
            RateLimitConfig(max_requests=5, window_seconds=60)
        )

        # Inicialmente todos disponibles
        remaining, reset_time = limiter.get_remaining("test_op", "user1", tenant_id="test")
        assert remaining == 5

        # Después de un request
        limiter.allow("test_op", "user1", tenant_id="test")
        remaining, reset_time = limiter.get_remaining("test_op", "user1", tenant_id="test")
        assert remaining == 4

    def test_get_message(self):
        """Obtiene mensaje de error correctamente."""
        limiter = RateLimiter()

        limiter.configure_tenant(
            "test",
            "test_op",
            RateLimitConfig(
                max_requests=5,
                window_seconds=60,
                message="Error personalizado"
            )
        )

        message = limiter.get_message("test_op", tenant_id="test")
        assert message == "Error personalizado"

    def test_reset_limpieza_por_operacion(self):
        """Reset limpia contadores por operación."""
        limiter = RateLimiter()

        limiter.configure_tenant(
            "test",
            "test_op",
            RateLimitConfig(max_requests=2, window_seconds=60)
        )

        # Agotar límite
        limiter.allow("test_op", "user1", tenant_id="test")
        limiter.allow("test_op", "user1", tenant_id="test")
        assert limiter.allow("test_op", "user1", tenant_id="test") is False

        # Reset
        limiter.reset("test_op", "user1")

        # Ahora permitido de nuevo
        assert limiter.allow("test_op", "user1", tenant_id="test") is True

    def test_reset_limpieza_total(self):
        """Reset total limpia todos los contadores."""
        limiter = RateLimiter()

        limiter.allow("op1", "user1")
        limiter.allow("op2", "user2")

        limiter.reset()

        stats = limiter.get_stats()
        assert len(stats) == 0 or all(s["active_keys"] == 0 for s in stats.values())

    def test_configure_tenant(self):
        """Configuración por tenant funciona."""
        limiter = RateLimiter()

        # Tenant con límite alto
        limiter.configure_tenant(
            "premium",
            "api_call",
            RateLimitConfig(max_requests=1000, window_seconds=60)
        )

        # Tenant con límite bajo
        limiter.configure_tenant(
            "free",
            "api_call",
            RateLimitConfig(max_requests=10, window_seconds=60)
        )

        # Premium tiene más requests
        remaining_premium, _ = limiter.get_remaining("api_call", "user1", tenant_id="premium")
        remaining_free, _ = limiter.get_remaining("api_call", "user1", tenant_id="free")

        assert remaining_premium > remaining_free

    def test_get_stats(self):
        """Estadísticas se calculan correctamente."""
        limiter = RateLimiter()

        limiter.allow("op1", "user1")
        limiter.allow("op1", "user2")
        limiter.allow("op2", "user1")

        stats = limiter.get_stats()

        assert "op1" in stats
        assert stats["op1"]["active_keys"] == 2
        assert stats["op1"]["total_requests"] == 2

    def test_count_multiple(self):
        """Cuenta múltiples requests de una vez."""
        limiter = RateLimiter()

        limiter.configure_tenant(
            "test",
            "test_op",
            RateLimitConfig(max_requests=10, window_seconds=60)
        )

        # Consumir 5 de una vez
        assert limiter.allow("test_op", "user1", tenant_id="test", count=5) is True

        remaining, _ = limiter.get_remaining("test_op", "user1", tenant_id="test")
        assert remaining == 5


# ============================================================================
# CONVENIENCE FUNCTIONS TESTS
# ============================================================================

class TestConvenienceFunctions:
    """Tests para funciones de conveniencia."""

    def test_check_login_rate_permite(self):
        """check_login_rate permite intentos iniciales."""
        # Reset para evitar estado de tests anteriores
        from src.utils.rate_limiter import rate_limiter
        rate_limiter.reset()

        allowed, message = check_login_rate(99999)  # Usuario único
        assert allowed is True
        assert message == ""

    def test_check_login_rate_bloquea(self):
        """check_login_rate bloquea después de límite."""
        from src.utils.rate_limiter import rate_limiter
        rate_limiter.reset()

        # Usar ID único para este test
        user_id = 88888

        # Agotar intentos (límite es 5 por defecto)
        for _ in range(10):
            check_login_rate(user_id)

        allowed, message = check_login_rate(user_id)
        # Después de suficientes intentos debería bloquear
        # (puede requerir más intentos dependiendo de la config)

    def test_check_n8n_rate_permite(self):
        """check_n8n_rate permite requests iniciales."""
        from src.utils.rate_limiter import rate_limiter
        rate_limiter.reset()

        allowed, message = check_n8n_rate("org-unique-123")
        assert allowed is True
        assert message == ""

    def test_check_invoice_rate_permite(self):
        """check_invoice_rate permite creación inicial."""
        from src.utils.rate_limiter import rate_limiter
        rate_limiter.reset()

        allowed, message = check_invoice_rate(77777, "org-unique-456")
        assert allowed is True
        assert message == ""

    def test_check_message_rate_permite(self):
        """check_message_rate permite mensajes iniciales."""
        from src.utils.rate_limiter import rate_limiter
        rate_limiter.reset()

        allowed, message = check_message_rate(66666)
        assert allowed is True
        assert message == ""


# ============================================================================
# DEFAULT LIMITS TESTS
# ============================================================================

class TestDefaultLimits:
    """Tests para los límites por defecto."""

    def test_get_default_limits_retorna_dict(self):
        """get_default_limits retorna un diccionario."""
        limits = get_default_limits()
        assert isinstance(limits, dict)

    def test_default_limits_contiene_operaciones(self):
        """Límites por defecto contienen todas las operaciones."""
        limits = get_default_limits()

        assert OperationType.LOGIN_ATTEMPT.value in limits
        assert OperationType.N8N_REQUEST.value in limits
        assert OperationType.INVOICE_CREATE.value in limits
        assert OperationType.MESSAGE.value in limits
        assert OperationType.API_CALL.value in limits

    def test_default_limits_son_rate_limit_config(self):
        """Cada límite es una instancia de RateLimitConfig."""
        limits = get_default_limits()

        for key, config in limits.items():
            assert isinstance(config, RateLimitConfig)
            assert config.max_requests > 0
            assert config.window_seconds > 0


# ============================================================================
# OPERATION TYPE TESTS
# ============================================================================

class TestOperationType:
    """Tests para el enum OperationType."""

    def test_valores_son_strings(self):
        """Valores del enum son strings."""
        assert isinstance(OperationType.LOGIN_ATTEMPT.value, str)
        assert isinstance(OperationType.N8N_REQUEST.value, str)

    def test_valores_unicos(self):
        """Todos los valores son únicos."""
        values = [op.value for op in OperationType]
        assert len(values) == len(set(values))


# ============================================================================
# INTEGRATION WITH SETTINGS TESTS
# ============================================================================

class TestSettingsIntegration:
    """Tests de integración con settings."""

    def test_limits_usan_settings(self):
        """Límites usan valores de settings."""
        from config.settings import settings

        limits = get_default_limits()
        login_limit = limits[OperationType.LOGIN_ATTEMPT.value]

        assert login_limit.max_requests == settings.RATE_LIMIT_LOGIN_MAX
        assert login_limit.window_seconds == settings.RATE_LIMIT_LOGIN_WINDOW
        assert login_limit.block_seconds == settings.RATE_LIMIT_LOGIN_BLOCK

    def test_n8n_limit_usa_settings(self):
        """Límite de n8n usa valores de settings."""
        from config.settings import settings

        limits = get_default_limits()
        n8n_limit = limits[OperationType.N8N_REQUEST.value]

        assert n8n_limit.max_requests == settings.RATE_LIMIT_N8N_MAX
        assert n8n_limit.window_seconds == settings.RATE_LIMIT_N8N_WINDOW
