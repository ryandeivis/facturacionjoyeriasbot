"""
API Module

Endpoints HTTP para health checks, métricas y administración.
Incluye:
- Health: /health, /health/live, /health/ready
- Metrics: /metrics, /metrics/prometheus
- Organizations: /api/v1/organizations
- Invoices: /api/v1/invoices
"""

# Health
from src.api.health import health_router, get_health_checker, HealthChecker

# Metrics
from src.api.metrics import metrics_router

# Organizations
from src.api.organizations import organizations_router, org_service, OrganizationService

# Invoices
from src.api.invoices import invoices_router, invoice_api_service, InvoiceAPIService

# App
from src.api.app import app, create_app, run_api

__all__ = [
    # Health
    "health_router",
    "get_health_checker",
    "HealthChecker",
    # Metrics
    "metrics_router",
    # Organizations
    "organizations_router",
    "org_service",
    "OrganizationService",
    # Invoices
    "invoices_router",
    "invoice_api_service",
    "InvoiceAPIService",
    # App
    "app",
    "create_app",
    "run_api",
]