"""
Tests para los middlewares del bot.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock

from src.bot.middleware.plan_limits import (
    PlanTier,
    PlanLimits,
    PLAN_CONFIGS,
    PlanBasedRateLimitMiddleware,
    FeatureGateMiddleware,
)
from src.bot.middleware.tenant import (
    TenantCache,
    CachedTenant,
    TenantMiddleware,
)


class TestPlanTier:
    """Tests para PlanTier enum."""

    def test_plan_tiers_exist(self):
        """Verifica que existen los tres planes."""
        assert PlanTier.BASIC.value == "basic"
        assert PlanTier.PRO.value == "pro"
        assert PlanTier.ENTERPRISE.value == "enterprise"

    def test_plan_configs_exist(self):
        """Verifica que hay configuración para cada plan."""
        assert PlanTier.BASIC in PLAN_CONFIGS
        assert PlanTier.PRO in PLAN_CONFIGS
        assert PlanTier.ENTERPRISE in PLAN_CONFIGS


class TestPlanLimits:
    """Tests para límites de planes."""

    def test_basic_limits(self):
        """Verifica límites del plan básico."""
        limits = PLAN_CONFIGS[PlanTier.BASIC]

        assert limits.requests_per_minute == 30
        assert limits.invoices_per_month == 100
        assert limits.max_items_per_invoice == 6
        assert limits.voice_input is False
        assert limits.photo_input is False

    def test_pro_limits(self):
        """Verifica límites del plan Pro."""
        limits = PLAN_CONFIGS[PlanTier.PRO]

        assert limits.requests_per_minute == 60
        assert limits.invoices_per_month == 500
        assert limits.max_items_per_invoice == 12
        assert limits.voice_input is True
        assert limits.photo_input is True

    def test_enterprise_limits(self):
        """Verifica límites del plan Enterprise."""
        limits = PLAN_CONFIGS[PlanTier.ENTERPRISE]

        assert limits.requests_per_minute == 120
        assert limits.invoices_per_month == -1  # Unlimited
        assert limits.api_access is True
        assert limits.priority_support is True

    def test_plan_limits_immutable(self):
        """Verifica que PlanLimits es inmutable (frozen)."""
        limits = PLAN_CONFIGS[PlanTier.BASIC]
        with pytest.raises(Exception):  # FrozenInstanceError
            limits.requests_per_minute = 999


class TestPlanBasedRateLimitMiddleware:
    """Tests para rate limiting basado en plan."""

    @pytest.fixture
    def middleware(self):
        """Crea middleware de rate limit."""
        return PlanBasedRateLimitMiddleware()

    @pytest.fixture
    def mock_update(self):
        """Crea mock de Update."""
        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        return update

    @pytest.fixture
    def mock_context(self):
        """Crea mock de Context."""
        context = MagicMock()
        context.user_data = {
            'organization_id': 'org-123',
            'organization_plan': 'basic'
        }
        return context

    @pytest.mark.asyncio
    async def test_before_allows_within_limit(self, middleware, mock_update, mock_context):
        """Verifica que permite requests dentro del límite."""
        result = await middleware.before(mock_update, mock_context)
        assert result is True

    @pytest.mark.asyncio
    async def test_before_blocks_over_limit(self, middleware, mock_update, mock_context):
        """Verifica que bloquea requests sobre el límite."""
        # Simular que ya se alcanzó el límite por minuto (30 para basic)
        now = datetime.utcnow()
        windows = middleware._get_window_keys(now)
        middleware._counters['org-123'] = {
            f"m_{windows['minute']}": 30  # Límite alcanzado
        }

        result = await middleware.before(mock_update, mock_context)
        assert result is False
        mock_update.message.reply_text.assert_called_once()

    def test_get_plan_limits_valid(self, middleware):
        """Verifica obtención de límites para plan válido."""
        limits = middleware._get_plan_limits("pro")
        assert limits == PLAN_CONFIGS[PlanTier.PRO]

    def test_get_plan_limits_invalid(self, middleware):
        """Verifica fallback a basic para plan inválido."""
        limits = middleware._get_plan_limits("invalid_plan")
        assert limits == PLAN_CONFIGS[PlanTier.BASIC]

    def test_get_usage_stats(self, middleware):
        """Verifica obtención de estadísticas de uso."""
        now = datetime.utcnow()
        windows = middleware._get_window_keys(now)
        middleware._counters['org-123'] = {
            f"m_{windows['minute']}": 5,
            f"h_{windows['hour']}": 50,
            f"d_{windows['day']}": 100,
        }

        stats = middleware.get_usage_stats('org-123')

        assert stats['requests_this_minute'] == 5
        assert stats['requests_this_hour'] == 50
        assert stats['requests_today'] == 100


class TestFeatureGateMiddleware:
    """Tests para control de features por plan."""

    @pytest.fixture
    def middleware(self):
        """Crea middleware de feature gate."""
        return FeatureGateMiddleware()

    @pytest.fixture
    def mock_update(self):
        """Crea mock de Update."""
        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        return update

    @pytest.fixture
    def mock_context_basic(self):
        """Contexto con plan básico."""
        context = MagicMock()
        context.user_data = {'organization_plan': 'basic'}
        return context

    @pytest.fixture
    def mock_context_pro(self):
        """Contexto con plan Pro."""
        context = MagicMock()
        context.user_data = {'organization_plan': 'pro'}
        return context

    @pytest.mark.asyncio
    async def test_before_always_allows(self, middleware, mock_update, mock_context_basic):
        """Verifica que before() siempre permite pasar."""
        result = await middleware.before(mock_update, mock_context_basic)
        assert result is True

    @pytest.mark.asyncio
    async def test_check_feature_basic_no_voice(
        self, middleware, mock_update, mock_context_basic
    ):
        """Verifica que plan básico no tiene voice_input."""
        result = await middleware.check_feature(
            mock_update, mock_context_basic, "voice_input"
        )
        assert result is False
        mock_update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_feature_pro_has_voice(
        self, middleware, mock_update, mock_context_pro
    ):
        """Verifica que plan Pro tiene voice_input."""
        result = await middleware.check_feature(
            mock_update, mock_context_pro, "voice_input"
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_check_feature_basic_has_ai(
        self, middleware, mock_update, mock_context_basic
    ):
        """Verifica que plan básico tiene ai_extraction."""
        result = await middleware.check_feature(
            mock_update, mock_context_basic, "ai_extraction"
        )
        assert result is True


class TestTenantCache:
    """Tests para caché de tenant."""

    @pytest.fixture
    def cache(self):
        """Crea caché con TTL corto para tests."""
        return TenantCache(ttl_seconds=60, max_size=10)

    def test_set_and_get(self, cache):
        """Verifica set y get básico."""
        cache.set(123456, "org-123", "pro")
        cached = cache.get(123456)

        assert cached is not None
        assert cached.org_id == "org-123"
        assert cached.org_plan == "pro"

    def test_get_nonexistent(self, cache):
        """Verifica get de entrada inexistente."""
        cached = cache.get(999999)
        assert cached is None

    def test_get_expired(self, cache):
        """Verifica que entradas expiradas no se retornan."""
        # Crear caché con TTL de 0 segundos
        cache = TenantCache(ttl_seconds=0, max_size=10)
        cache.set(123456, "org-123")

        cached = cache.get(123456)
        assert cached is None

    def test_invalidate(self, cache):
        """Verifica invalidación de entrada."""
        cache.set(123456, "org-123")
        cache.invalidate(123456)

        cached = cache.get(123456)
        assert cached is None

    def test_clear(self, cache):
        """Verifica limpieza completa."""
        cache.set(1, "org-1")
        cache.set(2, "org-2")
        cache.set(3, "org-3")
        cache.clear()

        assert cache.get(1) is None
        assert cache.get(2) is None
        assert cache.get(3) is None


class TestCachedTenant:
    """Tests para CachedTenant dataclass."""

    def test_is_expired_false(self):
        """Verifica que entrada reciente no está expirada."""
        cached = CachedTenant(
            org_id="org-123",
            org_plan="basic",
            cached_at=datetime.utcnow()
        )
        assert cached.is_expired(ttl_seconds=300) is False

    def test_is_expired_true(self):
        """Verifica que entrada antigua está expirada."""
        cached = CachedTenant(
            org_id="org-123",
            org_plan="basic",
            cached_at=datetime.utcnow() - timedelta(seconds=600)
        )
        assert cached.is_expired(ttl_seconds=300) is True


class TestTenantMiddleware:
    """Tests para TenantMiddleware."""

    @pytest.fixture
    def middleware(self):
        """Crea middleware con org_id default."""
        return TenantMiddleware(default_org_id="default-org")

    @pytest.fixture
    def mock_update(self):
        """Crea mock de Update."""
        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 123456789
        return update

    @pytest.fixture
    def mock_context(self):
        """Crea mock de Context."""
        context = MagicMock()
        context.user_data = {}
        return context

    @pytest.mark.asyncio
    async def test_before_with_existing_org_id(
        self, middleware, mock_update, mock_context
    ):
        """Verifica que usa org_id existente en user_data."""
        mock_context.user_data = {'organization_id': 'existing-org'}

        result = await middleware.before(mock_update, mock_context)

        assert result is True
        assert mock_context.user_data['_current_org_id'] == 'existing-org'

    @pytest.mark.asyncio
    async def test_before_uses_default_org(
        self, middleware, mock_update, mock_context
    ):
        """Verifica que usa org_id default cuando no hay otro."""
        # Simular que no hay usuario en DB (cache vacío)
        result = await middleware.before(mock_update, mock_context)

        assert result is True
        assert mock_context.user_data.get('_current_org_id') == 'default-org'

    def test_invalidate_cache(self, middleware):
        """Verifica invalidación de caché."""
        # Agregar algo al caché
        middleware._cache.set(123456, "org-123")

        # Invalidar
        middleware.invalidate_cache(123456)

        # Verificar que se eliminó
        assert middleware._cache.get(123456) is None