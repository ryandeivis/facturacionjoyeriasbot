# ==============================================================================
# Admin User for Load Testing
# ==============================================================================
"""
Usuario virtual que simula un administrador.

Comportamiento típico:
- Gestión de organizaciones
- Consulta de métricas
- Supervisión de vendedores
"""

import logging
from typing import List, Optional

from locust import task, tag

from tests.load.users.base import BaseAPIUser
from tests.load.config import (
    ADMIN_CREDENTIALS,
    ENDPOINTS,
    ADMIN_WEIGHTS,
)


logger = logging.getLogger(__name__)


class AdminUser(BaseAPIUser):
    """
    Simula un administrador interactuando con el sistema.

    Tareas ponderadas:
    - list_organizations (3): Frecuente - dashboard principal
    - get_organization (2): Moderado - detalles de org
    - view_metrics (2): Moderado - análisis de negocio
    - list_invoices (1): Ocasional - supervisión
    """

    # Configuración del usuario
    weight = 1  # Menos admins que vendedores

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.credentials = ADMIN_CREDENTIALS
        self._organization_ids: List[str] = []

    # ==========================================================================
    # HEALTH CHECKS
    # ==========================================================================

    @task(1)
    @tag("health", "smoke")
    def check_health_ready(self) -> None:
        """Verifica el health check completo."""
        self.client.get(
            ENDPOINTS.health_ready,
            name="health_ready",
        )

    # ==========================================================================
    # ORGANIZATION TASKS
    # ==========================================================================

    @task(ADMIN_WEIGHTS["list_organizations"])
    @tag("organizations", "read", "admin")
    def list_organizations(self) -> None:
        """
        Lista todas las organizaciones.

        Simula ver el dashboard de organizaciones.
        """
        response = self.api_get(
            ENDPOINTS.organizations_list,
            name="organizations_list",
        )

        if response.status_code == 200:
            try:
                orgs = response.json()
                if isinstance(orgs, list):
                    self._organization_ids = [
                        org.get("id") for org in orgs[:10]
                        if org.get("id")
                    ]
            except Exception as e:
                logger.debug(f"Error parseando organizaciones: {e}")

    @task(ADMIN_WEIGHTS["get_organization"])
    @tag("organizations", "read", "admin")
    def get_organization(self) -> None:
        """
        Obtiene detalles de una organización.

        Simula entrar al detalle de una organización.
        """
        if not self._organization_ids:
            self.list_organizations()
            return

        import random
        org_id = random.choice(self._organization_ids)

        self.api_get(
            ENDPOINTS.organizations_get.format(id=org_id),
            name="organizations_get",
        )

    @task(ADMIN_WEIGHTS.get("get_organization_stats", 1))
    @tag("organizations", "stats", "admin")
    def get_organization_stats(self) -> None:
        """
        Obtiene estadísticas de una organización.

        Simula ver métricas de facturación por organización.
        """
        if not self._organization_ids:
            self.list_organizations()
            return

        import random
        org_id = random.choice(self._organization_ids)

        self.api_get(
            ENDPOINTS.organizations_stats.format(id=org_id),
            name="organizations_stats",
        )

    # ==========================================================================
    # METRICS TASKS
    # ==========================================================================

    @task(ADMIN_WEIGHTS["view_metrics"])
    @tag("metrics", "read", "admin")
    def view_metrics(self) -> None:
        """
        Consulta métricas del sistema.

        Simula revisar el dashboard de métricas de negocio.
        """
        self.api_get(
            ENDPOINTS.metrics_summary,
            name="metrics_summary",
        )

    # ==========================================================================
    # SUPERVISION TASKS
    # ==========================================================================

    @task(ADMIN_WEIGHTS["list_invoices"])
    @tag("invoices", "read", "admin")
    def list_all_invoices(self) -> None:
        """
        Lista facturas de todas las organizaciones.

        Simula supervisión general de facturación.
        """
        # Admin puede ver facturas de cualquier organización
        response = self.api_get(
            f"{ENDPOINTS.invoices_list}?limit=50",
            name="invoices_list_admin",
        )
