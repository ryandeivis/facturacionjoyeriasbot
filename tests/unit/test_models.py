"""
Tests para los modelos de base de datos.
"""

import pytest
from datetime import datetime
from sqlalchemy import select

from src.database.models import Organization, User, Invoice, TenantConfig, AuditLog
from src.database.mixins import SoftDeleteMixin


class TestOrganizationModel:
    """Tests para el modelo Organization."""

    def test_create_organization(self, db_session, sample_organization):
        """Verifica creación de organización."""
        org = Organization(**sample_organization)
        db_session.add(org)
        db_session.commit()

        assert org.id == sample_organization["id"]
        assert org.name == sample_organization["name"]
        assert org.slug == sample_organization["slug"]
        assert org.is_deleted is False

    def test_organization_soft_delete(self, db_session, sample_organization):
        """Verifica soft delete de organización."""
        org = Organization(**sample_organization)
        db_session.add(org)
        db_session.commit()

        org.soft_delete()
        db_session.commit()

        assert org.is_deleted is True
        assert org.deleted_at is not None

    def test_organization_restore(self, db_session, sample_organization):
        """Verifica restauración de organización."""
        org = Organization(**sample_organization)
        db_session.add(org)
        db_session.commit()

        org.soft_delete()
        db_session.commit()
        org.restore()
        db_session.commit()

        assert org.is_deleted is False
        assert org.deleted_at is None

    def test_organization_timestamps(self, db_session, sample_organization):
        """Verifica timestamps automáticos."""
        org = Organization(**sample_organization)
        db_session.add(org)
        db_session.commit()

        assert org.created_at is not None
        assert org.updated_at is not None


class TestUserModel:
    """Tests para el modelo User."""

    def test_create_user(self, db_with_sample_data, sample_user):
        """Verifica creación de usuario."""
        user = db_with_sample_data.query(User).filter_by(
            cedula=sample_user["cedula"]
        ).first()

        assert user is not None
        assert user.nombre_completo == sample_user["nombre_completo"]
        assert user.rol == sample_user["rol"]
        assert user.activo is True

    def test_user_belongs_to_organization(self, db_with_sample_data, sample_user, sample_organization):
        """Verifica relación usuario-organización."""
        user = db_with_sample_data.query(User).filter_by(
            cedula=sample_user["cedula"]
        ).first()

        assert user.organization_id == sample_organization["id"]

    def test_user_soft_delete(self, db_with_sample_data, sample_user):
        """Verifica soft delete de usuario."""
        user = db_with_sample_data.query(User).filter_by(
            cedula=sample_user["cedula"]
        ).first()

        user.soft_delete()
        db_with_sample_data.commit()

        assert user.is_deleted is True


class TestInvoiceModel:
    """Tests para el modelo Invoice."""

    def test_create_invoice(self, db_with_sample_data, sample_invoice):
        """Verifica creación de factura."""
        invoice = Invoice(**sample_invoice)
        db_with_sample_data.add(invoice)
        db_with_sample_data.commit()

        assert invoice.id == sample_invoice["id"]
        assert invoice.numero_factura == sample_invoice["numero_factura"]
        assert invoice.estado == "BORRADOR"

    def test_invoice_total_calculation(self, db_with_sample_data, sample_invoice):
        """Verifica cálculo de total."""
        invoice = Invoice(**sample_invoice)
        db_with_sample_data.add(invoice)
        db_with_sample_data.commit()

        assert invoice.subtotal == 500000.0
        assert invoice.impuesto == 95000.0
        assert invoice.total == 595000.0

    def test_invoice_belongs_to_organization(self, db_with_sample_data, sample_invoice, sample_organization):
        """Verifica relación factura-organización."""
        invoice = Invoice(**sample_invoice)
        db_with_sample_data.add(invoice)
        db_with_sample_data.commit()

        assert invoice.organization_id == sample_organization["id"]

    def test_invoice_soft_delete(self, db_with_sample_data, sample_invoice):
        """Verifica soft delete de factura."""
        invoice = Invoice(**sample_invoice)
        db_with_sample_data.add(invoice)
        db_with_sample_data.commit()

        invoice.soft_delete()
        db_with_sample_data.commit()

        assert invoice.is_deleted is True


class TestTenantConfigModel:
    """Tests para el modelo TenantConfig."""

    def test_tenant_config_defaults(self, db_with_sample_data, sample_organization):
        """Verifica valores por defecto de configuración."""
        config = db_with_sample_data.query(TenantConfig).filter_by(
            organization_id=sample_organization["id"]
        ).first()

        assert config is not None
        assert config.invoice_prefix == "FAC"
        assert config.tax_rate == 0.19
        assert config.currency == "COP"


class TestAuditLogModel:
    """Tests para el modelo AuditLog."""

    def test_create_audit_log(self, db_with_sample_data, sample_organization):
        """Verifica creación de log de auditoría."""
        audit = AuditLog(
            organization_id=sample_organization["id"],
            usuario_cedula="123456789",
            accion="login",
            entidad_tipo="user",
            entidad_id="1",
            detalles="Login exitoso",
        )
        db_with_sample_data.add(audit)
        db_with_sample_data.commit()

        assert audit.id is not None
        assert audit.timestamp is not None
        assert audit.accion == "login"


class TestSoftDeleteMixin:
    """Tests para el mixin de soft delete."""

    def test_not_deleted_filter(self, db_with_sample_data, sample_organization):
        """Verifica filtro de no eliminados."""
        # Crear segunda organización y eliminarla
        org2_data = sample_organization.copy()
        org2_data["id"] = "org-test-456"
        org2_data["slug"] = "joyeria-test-2"

        org2 = Organization(**org2_data)
        db_with_sample_data.add(org2)
        db_with_sample_data.commit()

        org2.soft_delete()
        db_with_sample_data.commit()

        # Filtrar solo no eliminados
        active_orgs = db_with_sample_data.query(Organization).filter(
            Organization.not_deleted()
        ).all()

        assert len(active_orgs) == 1
        assert active_orgs[0].id == sample_organization["id"]