"""
Factory para AuditLog

Proporciona factory para crear registros de auditoría.
"""

import factory
from factory import Faker, LazyAttribute, Sequence
import uuid
from datetime import datetime

from src.database.models import AuditLog
from tests.factories.base import BaseFactory


class AuditLogFactory(BaseFactory):
    """
    Factory para crear registros de auditoría.

    Ejemplos:
        # Log básico
        log = AuditLogFactory()

        # Log de creación de factura
        log = AuditLogFactory(accion="invoice.created", entidad_tipo="invoice")

        # Log con detalles
        log = AuditLogFactory(detalles={"field": "value"})
    """

    class Meta:
        model = AuditLog

    id = Sequence(lambda n: n + 1)

    # Multi-tenancy
    organization_id = LazyAttribute(lambda _: str(uuid.uuid4()))

    # Usuario
    usuario_id = Sequence(lambda n: n + 1)
    usuario_cedula = Sequence(lambda n: str(1000000000 + n))

    # Acción
    accion = "invoice.created"

    # Entidad
    entidad_tipo = "invoice"
    entidad_id = LazyAttribute(lambda _: str(uuid.uuid4()))

    # Detalles
    detalles = None
    old_values = None
    new_values = None

    # Metadata
    ip_address = "127.0.0.1"
    user_agent = "Mozilla/5.0 (Test Browser)"
    timestamp = LazyAttribute(lambda _: datetime.utcnow())

    # Factura relacionada
    invoice_id = None

    class Params:
        """
        Variantes comunes de logs de auditoría.
        """

        # Log de login
        login = factory.Trait(
            accion="user.login",
            entidad_tipo="user",
            detalles=factory.LazyFunction(lambda: {"method": "telegram"})
        )

        # Log de logout
        logout = factory.Trait(
            accion="user.logout",
            entidad_tipo="user"
        )

        # Log de actualización
        update = factory.Trait(
            accion="invoice.updated",
            entidad_tipo="invoice",
            old_values=factory.LazyFunction(lambda: {"estado": "borrador"}),
            new_values=factory.LazyFunction(lambda: {"estado": "finalizada"})
        )

        # Log de eliminación
        delete = factory.Trait(
            accion="invoice.deleted",
            entidad_tipo="invoice"
        )

        # Log de error
        error = factory.Trait(
            accion="system.error",
            entidad_tipo="system",
            detalles=factory.LazyFunction(lambda: {
                "error": "ValidationError",
                "message": "Invalid data provided"
            })
        )

    @classmethod
    def create_for_invoice(
        cls,
        invoice_id: str,
        organization_id: str,
        accion: str = "invoice.created",
        **kwargs
    ):
        """
        Crea un log de auditoría para una factura.

        Args:
            invoice_id: ID de la factura
            organization_id: ID de la organización
            accion: Tipo de acción
            **kwargs: Atributos adicionales

        Returns:
            Log de auditoría creado
        """
        return cls.create(
            invoice_id=invoice_id,
            organization_id=organization_id,
            entidad_tipo="invoice",
            entidad_id=invoice_id,
            accion=accion,
            **kwargs
        )

    @classmethod
    def create_user_action(
        cls,
        organization_id: str,
        usuario_id: int,
        usuario_cedula: str,
        accion: str,
        **kwargs
    ):
        """
        Crea un log de acción de usuario.

        Args:
            organization_id: ID de la organización
            usuario_id: ID del usuario
            usuario_cedula: Cédula del usuario
            accion: Tipo de acción
            **kwargs: Atributos adicionales

        Returns:
            Log de auditoría creado
        """
        return cls.create(
            organization_id=organization_id,
            usuario_id=usuario_id,
            usuario_cedula=usuario_cedula,
            entidad_tipo="user",
            entidad_id=str(usuario_id),
            accion=accion,
            **kwargs
        )
