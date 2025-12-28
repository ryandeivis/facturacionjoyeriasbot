"""
Factories para Organization y TenantConfig

Proporciona factories para crear organizaciones (tenants) y su configuración.
"""

import factory
from factory import Faker, LazyAttribute, Sequence, SubFactory
import uuid

from src.database.models import Organization, TenantConfig
from tests.factories.base import BaseFactory


class OrganizationFactory(BaseFactory):
    """
    Factory para crear organizaciones (tenants).

    Ejemplos:
        # Organización básica
        org = OrganizationFactory()

        # Organización con plan específico
        org = OrganizationFactory(plan="enterprise")

        # Organización suspendida
        org = OrganizationFactory(status="suspended")
    """

    class Meta:
        model = Organization

    id = LazyAttribute(lambda _: str(uuid.uuid4()))
    name = Sequence(lambda n: f"Joyeria Test {n}")
    slug = Sequence(lambda n: f"joyeria-test-{n}")

    # Plan y estado
    plan = "basic"
    status = "active"

    # Configuración por defecto
    settings = factory.LazyFunction(lambda: {
        "timezone": "America/Bogota",
        "language": "es",
        "notifications_enabled": True,
    })

    # Contacto
    email = Faker("company_email")
    telefono = LazyAttribute(lambda _: f"+5731{factory.Faker._get_faker().random_number(digits=8, fix_len=True)}")
    direccion = Faker("address", locale="es_CO")

    class Params:
        """
        Parámetros para crear variantes comunes.

        Uso:
            org = OrganizationFactory(pro=True)  # Plan pro
            org = OrganizationFactory(suspended=True)  # Suspendida
        """
        pro = factory.Trait(
            plan="pro",
            settings=factory.LazyFunction(lambda: {
                "timezone": "America/Bogota",
                "language": "es",
                "notifications_enabled": True,
                "max_users": 10,
                "max_invoices_month": 500,
            })
        )

        enterprise = factory.Trait(
            plan="enterprise",
            settings=factory.LazyFunction(lambda: {
                "timezone": "America/Bogota",
                "language": "es",
                "notifications_enabled": True,
                "max_users": -1,  # Ilimitado
                "max_invoices_month": -1,
                "custom_branding": True,
                "api_access": True,
            })
        )

        suspended = factory.Trait(status="suspended")
        cancelled = factory.Trait(status="cancelled")


class TenantConfigFactory(BaseFactory):
    """
    Factory para crear configuración de tenant.

    Ejemplos:
        # Configuración por defecto
        config = TenantConfigFactory(organization_id="org-123")

        # Configuración con impuesto diferente
        config = TenantConfigFactory(tax_rate=0.16)
    """

    class Meta:
        model = TenantConfig

    organization_id = LazyAttribute(lambda o: str(uuid.uuid4()))

    # Configuración de facturas
    invoice_prefix = "FAC"
    tax_rate = 0.19
    currency = "COP"

    # Configuración adicional
    settings = factory.LazyFunction(lambda: {
        "decimal_places": 2,
        "show_tax_breakdown": True,
        "default_payment_terms": 30,
    })

    class Params:
        """Parámetros para variantes."""

        # Sin impuesto (para productos exentos)
        tax_exempt = factory.Trait(
            tax_rate=0.0,
            settings=factory.LazyFunction(lambda: {
                "decimal_places": 2,
                "show_tax_breakdown": False,
                "tax_exempt_reason": "Producto exento de IVA",
            })
        )

        # Configuración en USD
        usd = factory.Trait(
            currency="USD",
            settings=factory.LazyFunction(lambda: {
                "decimal_places": 2,
                "show_tax_breakdown": True,
                "exchange_rate_source": "trm",
            })
        )


class OrganizationWithConfigFactory(OrganizationFactory):
    """
    Factory que crea una organización con su configuración.

    Uso:
        org = OrganizationWithConfigFactory()
        # org.configs estará disponible
    """

    configs = factory.RelatedFactory(
        TenantConfigFactory,
        factory_related_name="organization_id",
    )
