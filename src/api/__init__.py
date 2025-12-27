"""
API Module

Endpoints HTTP para health checks, métricas y administración.

Endpoints:
- Health: /health, /health/live, /health/ready
- Metrics: /metrics, /metrics/prometheus
- Organizations: /api/v1/organizations
- Invoices: /api/v1/invoices

Documentación:
- Swagger UI: /docs
- ReDoc: /redoc
- OpenAPI JSON: /openapi.json
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

# Schemas (documentados)
from src.api.schemas import (
    # Enums
    InvoiceStatus,
    PlanType,
    UserRole,
    # Base
    BaseSchema,
    PaginationParams,
    # Errors
    ErrorResponse,
    # Invoice
    InvoiceCreate,
    InvoiceUpdate,
    InvoiceStatusUpdate,
    InvoiceResponse,
    InvoiceListResponse,
    # Organization
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationResponse,
    OrganizationStats,
    # Health
    HealthResponse,
)

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
    # Schemas
    "InvoiceStatus",
    "PlanType",
    "UserRole",
    "BaseSchema",
    "PaginationParams",
    "ErrorResponse",
    "InvoiceCreate",
    "InvoiceUpdate",
    "InvoiceStatusUpdate",
    "InvoiceResponse",
    "InvoiceListResponse",
    "OrganizationCreate",
    "OrganizationUpdate",
    "OrganizationResponse",
    "OrganizationStats",
    "HealthResponse",
]