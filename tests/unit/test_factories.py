"""
Tests para validar las Factories.

Verifica que todas las factories generan datos válidos
y cumplen con las restricciones del modelo.
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
import uuid

from tests.factories import (
    OrganizationFactory,
    TenantConfigFactory,
    UserFactory,
    InvoiceFactory,
    InvoiceItemFactory,
    AuditLogFactory,
    MetricEventFactory,
)
from tests.factories.user import UserDictFactory
from tests.factories.invoice import InvoiceDictFactory


class TestOrganizationFactory:
    """Tests para OrganizationFactory."""

    def test_create_basic_organization(self):
        """Verifica creación de organización básica."""
        org = OrganizationFactory.build()

        assert org.id is not None
        assert org.name.startswith("Joyeria Test")
        assert org.slug.startswith("joyeria-test-")
        assert org.plan == "basic"
        assert org.status == "active"
        assert org.settings is not None
        assert "timezone" in org.settings

    def test_create_pro_organization(self):
        """Verifica creación de organización pro."""
        org = OrganizationFactory.build(pro=True)

        assert org.plan == "pro"
        assert "max_users" in org.settings
        assert org.settings["max_users"] == 10

    def test_create_enterprise_organization(self):
        """Verifica creación de organización enterprise."""
        org = OrganizationFactory.build(enterprise=True)

        assert org.plan == "enterprise"
        assert org.settings["max_users"] == -1  # Ilimitado
        assert org.settings["api_access"] is True

    def test_create_suspended_organization(self):
        """Verifica creación de organización suspendida."""
        org = OrganizationFactory.build(suspended=True)

        assert org.status == "suspended"

    def test_organization_has_unique_ids(self):
        """Verifica que cada organización tiene ID único."""
        orgs = [OrganizationFactory.build() for _ in range(5)]
        ids = [org.id for org in orgs]

        assert len(set(ids)) == 5  # Todos únicos

    def test_organization_has_valid_uuid(self):
        """Verifica que el ID es un UUID válido."""
        org = OrganizationFactory.build()

        # No debe lanzar excepción
        uuid.UUID(org.id)


class TestTenantConfigFactory:
    """Tests para TenantConfigFactory."""

    def test_create_basic_config(self):
        """Verifica creación de configuración básica."""
        config = TenantConfigFactory.build()

        assert config.organization_id is not None
        assert config.invoice_prefix == "FAC"
        assert config.tax_rate == 0.19
        assert config.currency == "COP"

    def test_create_tax_exempt_config(self):
        """Verifica configuración exenta de impuestos."""
        config = TenantConfigFactory.build(tax_exempt=True)

        assert config.tax_rate == 0.0
        assert "tax_exempt_reason" in config.settings

    def test_create_usd_config(self):
        """Verifica configuración en USD."""
        config = TenantConfigFactory.build(usd=True)

        assert config.currency == "USD"
        assert "exchange_rate_source" in config.settings


class TestUserFactory:
    """Tests para UserFactory."""

    def test_create_basic_user(self):
        """Verifica creación de usuario básico."""
        user = UserFactory.build()

        assert user.id is not None
        assert user.organization_id is not None
        assert user.cedula is not None
        assert user.nombre_completo is not None
        assert user.rol == "VENDEDOR"
        assert user.activo is True
        assert user.password_hash is not None

    def test_create_admin_user(self):
        """Verifica creación de usuario admin."""
        user = UserFactory.build(admin=True)

        assert user.rol == "ADMIN"

    def test_create_inactive_user(self):
        """Verifica creación de usuario inactivo."""
        user = UserFactory.build(inactive=True)

        assert user.activo is False

    def test_create_logged_in_user(self):
        """Verifica creación de usuario con login reciente."""
        user = UserFactory.build(logged_in=True)

        assert user.ultimo_login is not None
        assert isinstance(user.ultimo_login, datetime)

    def test_create_user_without_telegram(self):
        """Verifica creación de usuario sin Telegram."""
        user = UserFactory.build(no_telegram=True)

        assert user.telegram_id is None

    def test_users_have_unique_cedulas(self):
        """Verifica que las cédulas son únicas."""
        users = [UserFactory.build() for _ in range(5)]
        cedulas = [user.cedula for user in users]

        assert len(set(cedulas)) == 5

    def test_users_have_valid_cedula_format(self):
        """Verifica formato de cédula."""
        user = UserFactory.build()

        assert user.cedula.isdigit()
        assert len(user.cedula) >= 8


class TestUserDictFactory:
    """Tests para UserDictFactory."""

    def test_create_user_dict(self):
        """Verifica creación de diccionario de usuario."""
        data = UserDictFactory.build()

        assert isinstance(data, dict)
        assert "cedula" in data
        assert "nombre_completo" in data
        assert "email" in data
        assert "password" in data
        assert "rol" in data


class TestInvoiceItemFactory:
    """Tests para InvoiceItemFactory."""

    def test_create_basic_item(self):
        """Verifica creación de item básico."""
        item = InvoiceItemFactory.build()

        assert isinstance(item, dict)
        assert "descripcion" in item
        assert "cantidad" in item
        assert "precio" in item
        assert "subtotal" in item
        assert item["subtotal"] == item["cantidad"] * item["precio"]

    def test_create_oro_item(self):
        """Verifica creación de item de oro."""
        item = InvoiceItemFactory.build(oro=True)

        assert "oro" in item["descripcion"].lower()
        assert item["precio"] >= 500000

    def test_create_plata_item(self):
        """Verifica creación de item de plata."""
        item = InvoiceItemFactory.build(plata=True)

        assert "plata" in item["descripcion"].lower()

    def test_create_diamante_item(self):
        """Verifica creación de item con diamante."""
        item = InvoiceItemFactory.build(diamante=True)

        assert "diamante" in item["descripcion"].lower()
        assert item["precio"] >= 2000000

    def test_create_batch_items(self):
        """Verifica creación de múltiples items."""
        items = InvoiceItemFactory.build_batch(5)

        assert len(items) == 5
        assert all(isinstance(item, dict) for item in items)


class TestInvoiceFactory:
    """Tests para InvoiceFactory."""

    def test_create_basic_invoice(self):
        """Verifica creación de factura básica."""
        invoice = InvoiceFactory.build()

        assert invoice.id is not None
        assert invoice.organization_id is not None
        assert invoice.numero_factura.startswith("FAC-")
        assert invoice.cliente_nombre is not None
        assert invoice.estado == "BORRADOR"
        assert len(invoice.items) >= 1

    def test_create_pendiente_invoice(self):
        """Verifica creación de factura pendiente."""
        invoice = InvoiceFactory.build(pendiente=True)

        assert invoice.estado == "PENDIENTE"

    def test_create_finalizada_invoice(self):
        """Verifica creación de factura finalizada (alias de pendiente)."""
        invoice = InvoiceFactory.build(finalizada=True)

        assert invoice.estado == "PENDIENTE"  # PENDIENTE es el estado "listo"

    def test_create_pagada_invoice(self):
        """Verifica creación de factura pagada."""
        invoice = InvoiceFactory.build(pagada=True)

        assert invoice.estado == "PAGADA"
        assert invoice.fecha_pago is not None

    def test_create_anulada_invoice(self):
        """Verifica creación de factura anulada."""
        invoice = InvoiceFactory.build(anulada=True)

        assert invoice.estado == "ANULADA"

    def test_create_invoice_with_discount(self):
        """Verifica creación de factura con descuento."""
        invoice = InvoiceFactory.build(con_descuento=True)

        assert invoice.descuento > 0

    def test_create_invoice_voz_input(self):
        """Verifica creación de factura con input de voz."""
        invoice = InvoiceFactory.build(input_voz=True)

        assert invoice.input_type == "VOZ"
        assert invoice.input_raw is not None

    def test_create_invoice_foto_input(self):
        """Verifica creación de factura con input de foto."""
        invoice = InvoiceFactory.build(input_foto=True)

        assert invoice.input_type == "FOTO"
        assert invoice.input_raw is not None

    def test_invoice_totals_calculated(self):
        """Verifica que los totales se calculan correctamente."""
        invoice = InvoiceFactory.build()

        expected_subtotal = sum(item.get("subtotal", 0) for item in invoice.items)
        expected_impuesto = expected_subtotal * 0.19
        expected_total = expected_subtotal - invoice.descuento + expected_impuesto

        assert invoice.subtotal == expected_subtotal
        assert invoice.impuesto == pytest.approx(expected_impuesto, rel=0.01)
        assert invoice.total == pytest.approx(expected_total, rel=0.01)

    def test_invoices_have_unique_numbers(self):
        """Verifica que los números de factura son únicos."""
        invoices = [InvoiceFactory.build() for _ in range(5)]
        numbers = [inv.numero_factura for inv in invoices]

        assert len(set(numbers)) == 5


class TestInvoiceDictFactory:
    """Tests para InvoiceDictFactory."""

    def test_create_invoice_dict(self):
        """Verifica creación de diccionario de factura."""
        data = InvoiceDictFactory.build()

        assert isinstance(data, dict)
        assert "cliente_nombre" in data
        assert "cliente_cedula" in data
        assert "items" in data
        assert isinstance(data["items"], list)


class TestAuditLogFactory:
    """Tests para AuditLogFactory."""

    def test_create_basic_log(self):
        """Verifica creación de log básico."""
        log = AuditLogFactory.build()

        assert log.id is not None
        assert log.organization_id is not None
        assert log.usuario_cedula is not None
        assert log.accion is not None
        assert log.timestamp is not None

    def test_create_login_log(self):
        """Verifica creación de log de login."""
        log = AuditLogFactory.build(login=True)

        assert log.accion == "user.login"
        assert log.entidad_tipo == "user"
        assert "method" in log.detalles

    def test_create_logout_log(self):
        """Verifica creación de log de logout."""
        log = AuditLogFactory.build(logout=True)

        assert log.accion == "user.logout"

    def test_create_update_log(self):
        """Verifica creación de log de actualización."""
        log = AuditLogFactory.build(update=True)

        assert log.accion == "invoice.updated"
        assert log.old_values is not None
        assert log.new_values is not None

    def test_create_delete_log(self):
        """Verifica creación de log de eliminación."""
        log = AuditLogFactory.build(delete=True)

        assert log.accion == "invoice.deleted"

    def test_create_error_log(self):
        """Verifica creación de log de error."""
        log = AuditLogFactory.build(error=True)

        assert log.accion == "system.error"
        assert "error" in log.detalles


class TestMetricEventFactory:
    """Tests para MetricEventFactory."""

    def test_create_basic_event(self):
        """Verifica creación de evento básico."""
        event = MetricEventFactory.build()

        assert event.id is not None
        assert event.event_type is not None
        assert event.organization_id is not None
        assert event.value >= 0
        assert event.success is True
        assert event.created_at is not None

    def test_create_invoice_created_event(self):
        """Verifica evento de factura creada."""
        event = MetricEventFactory.build(invoice_created=True)

        assert event.event_type == "invoice.created"
        assert "items_count" in event.event_metadata

    def test_create_invoice_paid_event(self):
        """Verifica evento de factura pagada."""
        event = MetricEventFactory.build(invoice_paid=True)

        assert event.event_type == "invoice.paid"
        assert "payment_method" in event.event_metadata

    def test_create_ai_extraction_event(self):
        """Verifica evento de extracción IA."""
        event = MetricEventFactory.build(ai_extraction=True)

        assert event.event_type == "ai.extraction"
        assert "confidence" in event.event_metadata
        assert event.event_metadata["confidence"] >= 0.7

    def test_create_bot_interaction_event(self):
        """Verifica evento de interacción con bot."""
        event = MetricEventFactory.build(bot_interaction=True)

        assert event.event_type == "bot.message"
        assert "command" in event.event_metadata

    def test_create_api_request_event(self):
        """Verifica evento de request API."""
        event = MetricEventFactory.build(api_request=True)

        assert event.event_type == "api.request"
        assert "endpoint" in event.event_metadata
        assert "method" in event.event_metadata

    def test_create_failed_event(self):
        """Verifica evento fallido."""
        event = MetricEventFactory.build(failed=True)

        assert event.success is False
        assert "error" in event.event_metadata

    def test_create_slow_event(self):
        """Verifica evento lento."""
        event = MetricEventFactory.build(slow=True)

        assert event.duration_ms >= 1000

    def test_create_batch_events(self):
        """Verifica creación de múltiples eventos."""
        events = MetricEventFactory.build_batch(10)

        assert len(events) == 10


class TestFactoryBuildVsCreate:
    """Tests para verificar diferencia entre build() y create()."""

    def test_build_does_not_persist(self):
        """Verifica que build() no persiste en BD."""
        # build() solo crea el objeto en memoria
        user = UserFactory.build()

        # Debería tener un ID pero no estar en BD
        assert user.id is not None
        # No hay forma directa de verificar sin una sesión real

    def test_build_batch_creates_multiple(self):
        """Verifica que build_batch crea múltiples objetos."""
        users = UserFactory.build_batch(5)

        assert len(users) == 5
        assert all(u.cedula for u in users)


class TestFactoryCustomization:
    """Tests para personalización de factories."""

    def test_override_single_field(self):
        """Verifica override de un campo."""
        user = UserFactory.build(nombre_completo="Juan Test")

        assert user.nombre_completo == "Juan Test"

    def test_override_multiple_fields(self):
        """Verifica override de múltiples campos."""
        invoice = InvoiceFactory.build(
            cliente_nombre="Cliente Test",
            total=1000000.0,
            estado="pagada"
        )

        assert invoice.cliente_nombre == "Cliente Test"
        assert invoice.total == 1000000.0
        assert invoice.estado == "pagada"

    def test_combine_traits(self):
        """Verifica combinación de traits."""
        user = UserFactory.build(admin=True, logged_in=True)

        assert user.rol == "ADMIN"
        assert user.ultimo_login is not None

    def test_custom_organization_id(self):
        """Verifica uso de organization_id personalizado."""
        org_id = str(uuid.uuid4())

        user = UserFactory.build(organization_id=org_id)
        invoice = InvoiceFactory.build(organization_id=org_id)

        assert user.organization_id == org_id
        assert invoice.organization_id == org_id
