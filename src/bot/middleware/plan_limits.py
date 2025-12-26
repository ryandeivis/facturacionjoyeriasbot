"""
Plan-Based Rate Limiting

Rate limiting basado en planes SaaS (basic, pro, enterprise).
Cada plan tiene diferentes límites de uso.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from telegram import Update
from telegram.ext import ContextTypes

from src.bot.middleware.base import BaseMiddleware
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PlanTier(str, Enum):
    """Niveles de plan disponibles."""
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


@dataclass(frozen=True)
class PlanLimits:
    """Límites por plan."""
    # Rate limiting
    requests_per_minute: int
    requests_per_hour: int
    requests_per_day: int

    # Límites de uso
    invoices_per_month: int
    users_per_org: int
    max_items_per_invoice: int

    # Features
    ai_extraction: bool
    voice_input: bool
    photo_input: bool
    custom_templates: bool
    api_access: bool
    priority_support: bool


# Configuración de límites por plan
PLAN_CONFIGS: Dict[PlanTier, PlanLimits] = {
    PlanTier.BASIC: PlanLimits(
        requests_per_minute=30,
        requests_per_hour=200,
        requests_per_day=1000,
        invoices_per_month=100,
        users_per_org=3,
        max_items_per_invoice=6,
        ai_extraction=True,
        voice_input=False,
        photo_input=False,
        custom_templates=False,
        api_access=False,
        priority_support=False
    ),
    PlanTier.PRO: PlanLimits(
        requests_per_minute=60,
        requests_per_hour=500,
        requests_per_day=5000,
        invoices_per_month=500,
        users_per_org=10,
        max_items_per_invoice=12,
        ai_extraction=True,
        voice_input=True,
        photo_input=True,
        custom_templates=True,
        api_access=False,
        priority_support=False
    ),
    PlanTier.ENTERPRISE: PlanLimits(
        requests_per_minute=120,
        requests_per_hour=2000,
        requests_per_day=20000,
        invoices_per_month=-1,  # Unlimited
        users_per_org=-1,  # Unlimited
        max_items_per_invoice=20,
        ai_extraction=True,
        voice_input=True,
        photo_input=True,
        custom_templates=True,
        api_access=True,
        priority_support=True
    )
}


class PlanBasedRateLimitMiddleware(BaseMiddleware):
    """
    Rate limiting basado en el plan de la organización.

    Aplica límites diferentes según el plan SaaS del tenant.
    """

    def __init__(self):
        super().__init__("plan_rate_limit")
        # Contadores: {org_id: {window_key: count}}
        self._counters: Dict[str, Dict[str, int]] = {}
        self._last_cleanup = datetime.utcnow()

    def _get_plan_limits(self, plan: str) -> PlanLimits:
        """Obtiene los límites del plan."""
        try:
            tier = PlanTier(plan.lower())
            return PLAN_CONFIGS[tier]
        except (ValueError, KeyError):
            return PLAN_CONFIGS[PlanTier.BASIC]

    def _get_window_keys(self, now: datetime) -> Dict[str, str]:
        """Genera claves de ventana para los diferentes períodos."""
        return {
            "minute": now.strftime("%Y%m%d%H%M"),
            "hour": now.strftime("%Y%m%d%H"),
            "day": now.strftime("%Y%m%d")
        }

    def _cleanup_old_counters(self, now: datetime) -> None:
        """Limpia contadores antiguos (cada hora)."""
        if (now - self._last_cleanup).total_seconds() < 3600:
            return

        current_day = now.strftime("%Y%m%d")
        for org_id in list(self._counters.keys()):
            counters = self._counters[org_id]
            # Eliminar contadores de días anteriores
            self._counters[org_id] = {
                k: v for k, v in counters.items()
                if current_day in k or now.strftime("%Y%m%d%H") in k
            }

        self._last_cleanup = now

    def _check_limits(
        self,
        org_id: str,
        plan_limits: PlanLimits,
        now: datetime
    ) -> tuple[bool, Optional[str]]:
        """
        Verifica si se exceden los límites.

        Returns:
            Tuple (dentro_limite, mensaje_error)
        """
        windows = self._get_window_keys(now)

        if org_id not in self._counters:
            self._counters[org_id] = {}

        counters = self._counters[org_id]

        # Verificar límite por minuto
        minute_key = f"m_{windows['minute']}"
        minute_count = counters.get(minute_key, 0)
        if minute_count >= plan_limits.requests_per_minute:
            return False, "Límite por minuto excedido. Espera un momento."

        # Verificar límite por hora
        hour_key = f"h_{windows['hour']}"
        hour_count = counters.get(hour_key, 0)
        if hour_count >= plan_limits.requests_per_hour:
            return False, "Límite por hora excedido. Intenta más tarde."

        # Verificar límite por día
        day_key = f"d_{windows['day']}"
        day_count = counters.get(day_key, 0)
        if day_count >= plan_limits.requests_per_day:
            return False, "Límite diario excedido. Intenta mañana o actualiza tu plan."

        return True, None

    def _increment_counters(self, org_id: str, now: datetime) -> None:
        """Incrementa los contadores."""
        windows = self._get_window_keys(now)

        if org_id not in self._counters:
            self._counters[org_id] = {}

        counters = self._counters[org_id]

        for prefix, window_key in [
            ("m", windows["minute"]),
            ("h", windows["hour"]),
            ("d", windows["day"])
        ]:
            key = f"{prefix}_{window_key}"
            counters[key] = counters.get(key, 0) + 1

    async def before(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        """Verifica rate limit basado en plan."""
        user_data = context.user_data or {}

        # Si no está autenticado, usar límites básicos
        org_id = user_data.get('organization_id', 'anonymous')
        plan = user_data.get('organization_plan', 'basic')

        now = datetime.utcnow()
        self._cleanup_old_counters(now)

        plan_limits = self._get_plan_limits(plan)
        within_limit, error_msg = self._check_limits(org_id, plan_limits, now)

        if not within_limit:
            self.logger.warning(
                f"Plan rate limit excedido para org {org_id} (plan: {plan})"
            )
            if update.message and error_msg:
                await update.message.reply_text(error_msg)
            return False

        self._increment_counters(org_id, now)
        return True

    def get_usage_stats(self, org_id: str) -> Dict[str, Any]:
        """Obtiene estadísticas de uso para una organización."""
        now = datetime.utcnow()
        windows = self._get_window_keys(now)
        counters = self._counters.get(org_id, {})

        return {
            "requests_this_minute": counters.get(f"m_{windows['minute']}", 0),
            "requests_this_hour": counters.get(f"h_{windows['hour']}", 0),
            "requests_today": counters.get(f"d_{windows['day']}", 0),
            "timestamp": now.isoformat()
        }


class FeatureGateMiddleware(BaseMiddleware):
    """
    Middleware de control de features por plan.

    Bloquea acceso a features que no están incluidas en el plan del usuario.
    """

    # Mapeo de comandos/acciones a features
    FEATURE_REQUIREMENTS: Dict[str, str] = {
        "voice_input": "voice_input",
        "photo_input": "photo_input",
        "custom_template": "custom_templates",
        "api_access": "api_access",
    }

    def __init__(self):
        super().__init__("feature_gate")

    async def before(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        """
        Middleware before - siempre permite pasar.

        El control de features se hace explícitamente con check_feature()
        en los handlers que lo requieran.
        """
        return True

    def _check_feature_access(
        self,
        feature: str,
        plan: str
    ) -> bool:
        """Verifica si el plan tiene acceso a la feature."""
        try:
            tier = PlanTier(plan.lower())
            limits = PLAN_CONFIGS[tier]
            return getattr(limits, feature, False)
        except (ValueError, KeyError, AttributeError):
            return False

    async def check_feature(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        feature: str
    ) -> bool:
        """
        Verifica acceso a una feature específica.

        Args:
            update: Update de Telegram
            context: Contexto
            feature: Nombre de la feature a verificar

        Returns:
            True si tiene acceso
        """
        user_data = context.user_data or {}
        plan = user_data.get('organization_plan', 'basic')

        if not self._check_feature_access(feature, plan):
            self.logger.info(
                f"Feature '{feature}' bloqueada para plan '{plan}'"
            )
            if update.message:
                await update.message.reply_text(
                    f"Esta función requiere un plan superior.\n"
                    f"Tu plan actual: {plan.upper()}\n"
                    f"Contacta al administrador para actualizar."
                )
            return False

        return True


# Instancias singleton
plan_rate_limit = PlanBasedRateLimitMiddleware()
feature_gate = FeatureGateMiddleware()