# ==============================================================================
# Vendedor User for Load Testing
# ==============================================================================
"""
Usuario virtual que simula un vendedor de joyería.

Comportamiento típico:
- Consulta frecuente de facturas
- Creación de nuevas facturas
- Exportación ocasional a PDF
"""

import logging
from typing import Optional, List

from locust import task, tag

from tests.load.users.base import BaseAPIUser
from tests.load.config import (
    DEFAULT_CREDENTIALS,
    ENDPOINTS,
    VENDEDOR_WEIGHTS,
)
from tests.load.data.generators import (
    generate_invoice_data,
    generate_invoice_item,
)


logger = logging.getLogger(__name__)


class VendedorUser(BaseAPIUser):
    """
    Simula un vendedor interactuando con el sistema.

    Tareas ponderadas:
    - list_invoices (5): Más frecuente - ve el listado principal
    - get_invoice (3): Frecuente - consulta detalles
    - create_invoice (2): Moderado - crea nuevas facturas
    - update_invoice (1): Poco frecuente - edita facturas
    - export_pdf (1): Poco frecuente - exporta para cliente
    """

    # Configuración del usuario
    weight = 3  # 3x más vendedores que admins

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.credentials = DEFAULT_CREDENTIALS
        self._invoice_ids: List[str] = []
        self._last_created_id: Optional[str] = None

    # ==========================================================================
    # HEALTH CHECKS - Siempre disponibles
    # ==========================================================================

    @task(1)
    @tag("health", "smoke")
    def check_health(self) -> None:
        """Verifica que el sistema está disponible."""
        self.client.get(
            ENDPOINTS.health_live,
            name="health_live",
        )

    # ==========================================================================
    # INVOICE TASKS - Flujo principal del vendedor
    # ==========================================================================

    @task(VENDEDOR_WEIGHTS["list_invoices"])
    @tag("invoices", "read")
    def list_invoices(self) -> None:
        """
        Lista las facturas del vendedor.

        Simula ver el listado principal de facturas.
        Almacena IDs para usar en otras tareas.
        """
        response = self.api_get(
            ENDPOINTS.invoices_list,
            name="invoices_list",
        )

        if response.status_code == 200:
            try:
                invoices = response.json()
                if isinstance(invoices, list):
                    # Guardar IDs para otras tareas
                    self._invoice_ids = [
                        inv.get("id") for inv in invoices[:20]
                        if inv.get("id")
                    ]
            except Exception as e:
                logger.debug(f"Error parseando facturas: {e}")

    @task(VENDEDOR_WEIGHTS["get_invoice"])
    @tag("invoices", "read")
    def get_invoice(self) -> None:
        """
        Obtiene detalles de una factura.

        Simula hacer clic en una factura del listado.
        """
        if not self._invoice_ids:
            # Si no hay IDs, primero listar
            self.list_invoices()
            return

        # Seleccionar un ID aleatorio
        import random
        invoice_id = random.choice(self._invoice_ids)

        self.api_get(
            ENDPOINTS.invoices_get.format(id=invoice_id),
            name="invoices_get",
        )

    @task(VENDEDOR_WEIGHTS["create_invoice"])
    @tag("invoices", "write")
    def create_invoice(self) -> None:
        """
        Crea una nueva factura.

        Simula el flujo completo de crear factura para cliente.
        """
        # Generar datos de factura
        invoice_data = generate_invoice_data()

        # Agregar 1-5 items
        import random
        num_items = random.randint(1, 5)
        invoice_data["items"] = [
            generate_invoice_item() for _ in range(num_items)
        ]

        response = self.api_post(
            ENDPOINTS.invoices_create,
            json_data=invoice_data,
            name="invoices_create",
        )

        if response.status_code in (200, 201):
            try:
                data = response.json()
                new_id = data.get("id")
                if new_id:
                    self._last_created_id = new_id
                    self._invoice_ids.append(new_id)
            except Exception:
                pass

    @task(VENDEDOR_WEIGHTS["update_invoice"])
    @tag("invoices", "write")
    def update_invoice(self) -> None:
        """
        Actualiza el estado de una factura.

        Simula cambiar estado de BORRADOR a PENDIENTE.
        """
        if not self._invoice_ids:
            return

        import random
        invoice_id = random.choice(self._invoice_ids)

        # Actualizar estado
        update_data = {
            "estado": random.choice(["PENDIENTE", "PAGADA"]),
        }

        self.api_patch(
            ENDPOINTS.invoices_update.format(id=invoice_id),
            json_data=update_data,
            name="invoices_update",
        )

    @task(VENDEDOR_WEIGHTS["export_pdf"])
    @tag("invoices", "export", "slow")
    def export_pdf(self) -> None:
        """
        Exporta una factura a PDF.

        Operación más pesada - menor frecuencia.
        """
        # Preferir la última creada o una aleatoria
        invoice_id = self._last_created_id
        if not invoice_id and self._invoice_ids:
            import random
            invoice_id = random.choice(self._invoice_ids)

        if not invoice_id:
            return

        self.api_get(
            ENDPOINTS.invoices_export_pdf.format(id=invoice_id),
            name="invoices_export_pdf",
        )
