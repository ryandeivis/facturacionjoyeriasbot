"""
Factories para Tests

Proporciona factories para crear objetos de prueba de forma limpia y reutilizable.
Sigue el patrón Factory de factory-boy para testing.

Uso:
    from tests.factories import UserFactory, InvoiceFactory, OrganizationFactory

    # Crear instancia con valores por defecto
    user = UserFactory()

    # Crear con valores personalizados
    invoice = InvoiceFactory(total=1500.0, estado="finalizada")

    # Crear múltiples instancias
    users = UserFactory.create_batch(5)
"""

from tests.factories.organization import OrganizationFactory, TenantConfigFactory
from tests.factories.user import UserFactory
from tests.factories.invoice import InvoiceFactory, InvoiceItemFactory
from tests.factories.audit import AuditLogFactory
from tests.factories.metrics import MetricEventFactory

__all__ = [
    # Organization factories
    "OrganizationFactory",
    "TenantConfigFactory",

    # User factories
    "UserFactory",

    # Invoice factories
    "InvoiceFactory",
    "InvoiceItemFactory",

    # Audit factories
    "AuditLogFactory",

    # Metrics factories
    "MetricEventFactory",
]
