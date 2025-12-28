"""
Base Factory Configuration

Proporciona la configuración base para todas las factories.
Incluye soporte para SQLAlchemy ORM y generación de datos.
"""

import factory
from factory import Faker, LazyAttribute, Sequence
from factory.alchemy import SQLAlchemyModelFactory
from typing import Optional, Any

from src.database.connection import SessionLocal, init_db


class BaseFactory(SQLAlchemyModelFactory):
    """
    Factory base para modelos SQLAlchemy.

    Proporciona:
    - Sesión de base de datos configurada
    - Estrategia de creación por defecto
    - Métodos helper para tests
    """

    class Meta:
        abstract = True
        sqlalchemy_session = None  # Se configura dinámicamente
        sqlalchemy_session_persistence = "commit"

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Override para manejar la sesión correctamente."""
        # Obtener o crear sesión
        if cls._meta.sqlalchemy_session is None:
            init_db()
            cls._meta.sqlalchemy_session = SessionLocal()

        return super()._create(model_class, *args, **kwargs)

    @classmethod
    def set_session(cls, session):
        """
        Configura la sesión para todas las factories.

        Args:
            session: Sesión de SQLAlchemy a usar

        Uso:
            with get_sync_db() as db:
                BaseFactory.set_session(db)
                user = UserFactory()
        """
        cls._meta.sqlalchemy_session = session

    @classmethod
    def create_batch_for_org(cls, size: int, organization_id: str, **kwargs):
        """
        Crea múltiples instancias para una organización específica.

        Args:
            size: Número de instancias a crear
            organization_id: ID de la organización
            **kwargs: Atributos adicionales

        Returns:
            Lista de instancias creadas
        """
        return cls.create_batch(size, organization_id=organization_id, **kwargs)


class DictFactory(factory.Factory):
    """
    Factory base para crear diccionarios.

    Útil para tests que no necesitan persistencia en BD.
    """

    class Meta:
        abstract = True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Retorna un diccionario en lugar de una instancia."""
        return dict(**kwargs)


# ============================================================================
# HELPER FUNCTIONS PARA DATOS COLOMBIANOS
# ============================================================================

def generate_colombian_cedula() -> str:
    """Genera una cédula colombiana válida."""
    import random
    return str(random.randint(10000000, 1999999999))


def generate_colombian_phone() -> str:
    """Genera un teléfono colombiano."""
    import random
    prefixes = ["300", "301", "302", "310", "311", "312", "313", "314", "315", "316", "317", "318", "319", "320", "321"]
    return f"+57{random.choice(prefixes)}{random.randint(1000000, 9999999)}"


def generate_colombian_city() -> str:
    """Retorna una ciudad colombiana aleatoria."""
    import random
    cities = [
        "Bogota", "Medellin", "Cali", "Barranquilla", "Cartagena",
        "Bucaramanga", "Cucuta", "Pereira", "Santa Marta", "Manizales",
        "Ibague", "Villavicencio", "Armenia", "Pasto", "Neiva"
    ]
    return random.choice(cities)
