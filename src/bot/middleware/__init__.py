"""
Bot Middleware

Middlewares para el bot de Telegram:
- AuthMiddleware: Verificación de autenticación
- RateLimitMiddleware: Límite de requests por usuario
- AuditMiddleware: Registro de acciones
- ErrorMiddleware: Manejo de errores
- TenantMiddleware: Contexto de tenant con caché
- PlanBasedRateLimitMiddleware: Rate limiting por plan SaaS
- FeatureGateMiddleware: Control de features por plan

Base:
- BaseMiddleware: Clase base para middlewares
- MiddlewareManager: Gestor de pipeline de middlewares
- apply_middleware: Decorador para aplicar middlewares
"""

# Base
from src.bot.middleware.base import (
    BaseMiddleware,
    MiddlewareManager,
    middleware_manager,
    apply_middleware,
)

# Auth
from src.bot.middleware.auth import AuthMiddleware

# Rate limiting
from src.bot.middleware.rate_limit import RateLimitMiddleware

# Plan-based rate limiting (SaaS)
from src.bot.middleware.plan_limits import (
    PlanTier,
    PlanLimits,
    PLAN_CONFIGS,
    PlanBasedRateLimitMiddleware,
    FeatureGateMiddleware,
    plan_rate_limit,
    feature_gate,
)

# Audit
from src.bot.middleware.audit import AuditMiddleware

# Error handling
from src.bot.middleware.error_handler import ErrorMiddleware

# Tenant / Multi-tenancy
from src.bot.middleware.tenant import (
    TenantMiddleware,
    TenantIsolationMiddleware,
    TenantContextManager,
    TenantCache,
    CachedTenant,
)

__all__ = [
    # Base
    "BaseMiddleware",
    "MiddlewareManager",
    "middleware_manager",
    "apply_middleware",
    # Auth
    "AuthMiddleware",
    # Rate limiting
    "RateLimitMiddleware",
    # Plan-based (SaaS)
    "PlanTier",
    "PlanLimits",
    "PLAN_CONFIGS",
    "PlanBasedRateLimitMiddleware",
    "FeatureGateMiddleware",
    "plan_rate_limit",
    "feature_gate",
    # Audit
    "AuditMiddleware",
    # Error
    "ErrorMiddleware",
    # Tenant
    "TenantMiddleware",
    "TenantIsolationMiddleware",
    "TenantContextManager",
    "TenantCache",
    "CachedTenant",
]