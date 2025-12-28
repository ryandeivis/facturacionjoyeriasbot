"""
Factory para User

Proporciona factory para crear usuarios con datos realistas.
"""

import factory
from factory import Faker, LazyAttribute, Sequence, SubFactory
import uuid
from datetime import datetime

from src.database.models import User
from tests.factories.base import BaseFactory
from tests.factories.organization import OrganizationFactory


class UserFactory(BaseFactory):
    """
    Factory para crear usuarios.

    Ejemplos:
        # Usuario básico (vendedor)
        user = UserFactory()

        # Usuario admin
        admin = UserFactory(rol="ADMIN")

        # Usuario con organización específica
        user = UserFactory(organization_id="org-123")

        # Usuario inactivo
        user = UserFactory(activo=False)
    """

    class Meta:
        model = User

    id = Sequence(lambda n: n + 1)

    # Multi-tenancy - por defecto crea organización
    organization_id = LazyAttribute(lambda o: str(uuid.uuid4()))

    # Datos de usuario
    cedula = Sequence(lambda n: str(1000000000 + n))
    nombre_completo = Faker("name", locale="es_CO")
    email = Faker("email")
    telefono = LazyAttribute(lambda _: f"+5731{factory.Faker._get_faker().random_number(digits=8, fix_len=True)}")

    # Seguridad
    password_hash = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewYpR1IOhCfS1gu."  # "password123"

    # Rol y estado
    rol = "VENDEDOR"
    activo = True

    # Telegram
    telegram_id = Sequence(lambda n: 100000000 + n)

    # Login tracking
    ultimo_login = None

    class Params:
        """
        Parámetros para crear variantes comunes.

        Uso:
            admin = UserFactory(admin=True)
            inactive = UserFactory(inactive=True)
            with_login = UserFactory(logged_in=True)
        """
        admin = factory.Trait(rol="ADMIN")

        inactive = factory.Trait(activo=False)

        logged_in = factory.Trait(
            ultimo_login=LazyAttribute(lambda _: datetime.utcnow())
        )

        no_telegram = factory.Trait(telegram_id=None)

        no_email = factory.Trait(email=None)

    @classmethod
    def create_admin(cls, organization_id: str = None, **kwargs):
        """
        Crea un usuario administrador.

        Args:
            organization_id: ID de organización (opcional)
            **kwargs: Atributos adicionales

        Returns:
            Usuario admin creado
        """
        if organization_id:
            kwargs["organization_id"] = organization_id
        return cls.create(rol="ADMIN", **kwargs)

    @classmethod
    def create_vendedor(cls, organization_id: str = None, **kwargs):
        """
        Crea un usuario vendedor.

        Args:
            organization_id: ID de organización (opcional)
            **kwargs: Atributos adicionales

        Returns:
            Usuario vendedor creado
        """
        if organization_id:
            kwargs["organization_id"] = organization_id
        return cls.create(rol="VENDEDOR", **kwargs)

    @classmethod
    def create_with_organization(cls, **kwargs):
        """
        Crea un usuario junto con su organización.

        Returns:
            Tuple (user, organization)
        """
        org = OrganizationFactory.create()
        user = cls.create(organization_id=org.id, **kwargs)
        return user, org


class UserDictFactory(factory.Factory):
    """
    Factory para crear diccionarios de usuario (sin persistencia).

    Útil para tests de validación o APIs.

    Ejemplo:
        data = UserDictFactory()
        response = client.post("/users", json=data)
    """

    class Meta:
        model = dict

    cedula = Sequence(lambda n: str(1000000000 + n))
    nombre_completo = Faker("name", locale="es_CO")
    email = Faker("email")
    telefono = LazyAttribute(lambda _: f"+5731{factory.Faker._get_faker().random_number(digits=8, fix_len=True)}")
    password = "password123"
    rol = "VENDEDOR"

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        return dict(**kwargs)
