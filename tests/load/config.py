# ==============================================================================
# Load Testing Configuration
# ==============================================================================
#
# Configuración centralizada para pruebas de carga.
# Sigue el patrón de configuración por entorno del proyecto.
#
# ==============================================================================
"""
Configuración de Load Testing.

Define escenarios, thresholds y credenciales de prueba.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, Any
from enum import Enum


# ==============================================================================
# ENVIRONMENT
# ==============================================================================

class Environment(Enum):
    """Entornos de prueba disponibles."""
    LOCAL = "local"
    STAGING = "staging"
    PRODUCTION = "production"


# Detectar entorno actual
CURRENT_ENV = Environment(os.getenv("LOAD_TEST_ENV", "local"))


# ==============================================================================
# CREDENTIALS - Credenciales de prueba
# ==============================================================================

@dataclass
class TestCredentials:
    """Credenciales para usuarios de prueba."""
    cedula: str
    password: str
    organization_id: str
    rol: str = "VENDEDOR"


# Credenciales por defecto para pruebas locales
# En staging/prod, usar variables de entorno
DEFAULT_CREDENTIALS = TestCredentials(
    cedula=os.getenv("LOAD_TEST_CEDULA", "123456789"),
    password=os.getenv("LOAD_TEST_PASSWORD", "test_password_123"),
    organization_id=os.getenv("LOAD_TEST_ORG_ID", "test-org-001"),
    rol=os.getenv("LOAD_TEST_ROL", "VENDEDOR"),
)

ADMIN_CREDENTIALS = TestCredentials(
    cedula=os.getenv("LOAD_TEST_ADMIN_CEDULA", "admin123456"),
    password=os.getenv("LOAD_TEST_ADMIN_PASSWORD", "admin_password_123"),
    organization_id=os.getenv("LOAD_TEST_ORG_ID", "test-org-001"),
    rol="ADMIN",
)


# ==============================================================================
# PERFORMANCE THRESHOLDS - Umbrales de rendimiento
# ==============================================================================

@dataclass
class PerformanceThreshold:
    """Umbral de rendimiento para un endpoint."""
    p50_ms: int      # Percentil 50 (mediana)
    p95_ms: int      # Percentil 95
    p99_ms: int      # Percentil 99
    max_ms: int      # Máximo absoluto
    error_rate: float = 1.0  # % máximo de errores permitido


# Thresholds por endpoint (en milisegundos)
THRESHOLDS: Dict[str, PerformanceThreshold] = {
    # Health checks - Deben ser muy rápidos
    "health_live": PerformanceThreshold(p50_ms=20, p95_ms=50, p99_ms=100, max_ms=200),
    "health_ready": PerformanceThreshold(p50_ms=50, p95_ms=100, p99_ms=200, max_ms=500),

    # Autenticación
    "auth_login": PerformanceThreshold(p50_ms=100, p95_ms=300, p99_ms=500, max_ms=1000),

    # Facturas - Operaciones CRUD
    "invoices_list": PerformanceThreshold(p50_ms=100, p95_ms=300, p99_ms=500, max_ms=1000),
    "invoices_get": PerformanceThreshold(p50_ms=50, p95_ms=150, p99_ms=300, max_ms=500),
    "invoices_create": PerformanceThreshold(p50_ms=200, p95_ms=500, p99_ms=1000, max_ms=2000),
    "invoices_update": PerformanceThreshold(p50_ms=150, p95_ms=400, p99_ms=800, max_ms=1500),

    # Exportación - Operación pesada
    "invoices_export_pdf": PerformanceThreshold(p50_ms=500, p95_ms=2000, p99_ms=5000, max_ms=10000),

    # Organizaciones (Admin)
    "organizations_list": PerformanceThreshold(p50_ms=100, p95_ms=300, p99_ms=500, max_ms=1000),
    "organizations_get": PerformanceThreshold(p50_ms=50, p95_ms=150, p99_ms=300, max_ms=500),

    # Métricas (Admin)
    "metrics_get": PerformanceThreshold(p50_ms=200, p95_ms=500, p99_ms=1000, max_ms=2000),
}


# ==============================================================================
# LOAD SCENARIOS - Escenarios de carga
# ==============================================================================

@dataclass
class LoadScenario:
    """Configuración de un escenario de carga."""
    name: str
    description: str
    users: int           # Número de usuarios virtuales
    spawn_rate: float    # Usuarios por segundo al iniciar
    duration_seconds: int
    tags: list = field(default_factory=list)


# Escenarios predefinidos
SCENARIOS: Dict[str, LoadScenario] = {
    "smoke": LoadScenario(
        name="Smoke Test",
        description="Verificación básica de que todo funciona",
        users=3,
        spawn_rate=1,
        duration_seconds=60,
        tags=["smoke", "quick"],
    ),
    "load": LoadScenario(
        name="Load Test",
        description="Carga normal esperada en producción",
        users=50,
        spawn_rate=5,
        duration_seconds=600,  # 10 minutos
        tags=["load", "normal"],
    ),
    "stress": LoadScenario(
        name="Stress Test",
        description="Encontrar límites del sistema",
        users=200,
        spawn_rate=10,
        duration_seconds=900,  # 15 minutos
        tags=["stress", "limits"],
    ),
    "spike": LoadScenario(
        name="Spike Test",
        description="Simular picos súbitos de tráfico",
        users=100,
        spawn_rate=50,  # Rápido
        duration_seconds=300,  # 5 minutos
        tags=["spike", "burst"],
    ),
    "soak": LoadScenario(
        name="Soak Test",
        description="Prueba prolongada para detectar memory leaks",
        users=30,
        spawn_rate=2,
        duration_seconds=3600,  # 1 hora
        tags=["soak", "endurance"],
    ),
}


# ==============================================================================
# API ENDPOINTS
# ==============================================================================

@dataclass
class APIEndpoints:
    """Endpoints de la API para pruebas."""
    # Health
    health_live: str = "/health/live"
    health_ready: str = "/health/ready"

    # Auth
    auth_login: str = "/api/auth/login"
    auth_logout: str = "/api/auth/logout"

    # Invoices
    invoices_list: str = "/api/invoices"
    invoices_create: str = "/api/invoices"
    invoices_get: str = "/api/invoices/{id}"
    invoices_update: str = "/api/invoices/{id}"
    invoices_delete: str = "/api/invoices/{id}"
    invoices_export_pdf: str = "/api/invoices/{id}/pdf"

    # Organizations
    organizations_list: str = "/api/organizations"
    organizations_get: str = "/api/organizations/{id}"
    organizations_stats: str = "/api/organizations/{id}/stats"

    # Metrics
    metrics_summary: str = "/api/metrics/summary"


ENDPOINTS = APIEndpoints()


# ==============================================================================
# TASK WEIGHTS - Pesos de tareas (frecuencia relativa)
# ==============================================================================

# Pesos para VendedorUser
VENDEDOR_WEIGHTS = {
    "list_invoices": 5,      # Muy frecuente
    "get_invoice": 3,        # Frecuente
    "create_invoice": 2,     # Moderado
    "update_invoice": 1,     # Poco frecuente
    "export_pdf": 1,         # Poco frecuente
}

# Pesos para AdminUser
ADMIN_WEIGHTS = {
    "list_organizations": 3,
    "get_organization": 2,
    "view_metrics": 2,
    "list_invoices": 1,
}


# ==============================================================================
# TIMING - Tiempos de espera
# ==============================================================================

# Tiempo de espera entre tareas (simula "pensar" del usuario)
WAIT_TIME_MIN = 1  # segundos
WAIT_TIME_MAX = 5  # segundos

# Timeout para requests
REQUEST_TIMEOUT = 30  # segundos


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def get_scenario(name: str) -> LoadScenario:
    """Obtiene un escenario por nombre."""
    if name not in SCENARIOS:
        raise ValueError(f"Escenario '{name}' no encontrado. Disponibles: {list(SCENARIOS.keys())}")
    return SCENARIOS[name]


def get_threshold(endpoint: str) -> PerformanceThreshold:
    """Obtiene threshold para un endpoint."""
    return THRESHOLDS.get(endpoint, PerformanceThreshold(
        p50_ms=500, p95_ms=1000, p99_ms=2000, max_ms=5000
    ))
