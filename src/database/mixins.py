"""
Database Mixins

Mixins reutilizables para modelos de base de datos:
- SoftDeleteMixin: Eliminación lógica
- TimestampMixin: Timestamps automáticos
- TenantMixin: Multi-tenancy
"""

from sqlalchemy import Column, DateTime, Boolean, String, event
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import Query
from datetime import datetime
from typing import Optional
import uuid


class SoftDeleteMixin:
    """
    Mixin para eliminación lógica (soft delete).

    En lugar de eliminar registros, los marca como eliminados.
    """
    deleted_at: Optional[datetime] = Column(DateTime, nullable=True, index=True)
    is_deleted: bool = Column(Boolean, default=False, index=True, nullable=False)

    def soft_delete(self) -> None:
        """Marca el registro como eliminado"""
        self.deleted_at = datetime.utcnow()
        self.is_deleted = True

    def restore(self) -> None:
        """Restaura un registro eliminado"""
        self.deleted_at = None
        self.is_deleted = False

    @classmethod
    def not_deleted(cls) -> bool:
        """Filtro para obtener solo registros no eliminados"""
        return cls.is_deleted == False


class TimestampMixin:
    """
    Mixin para timestamps automáticos.

    Agrega created_at y updated_at a los modelos.
    """
    created_at: datetime = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )
    updated_at: datetime = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )


class TenantMixin:
    """
    Mixin para multi-tenancy.

    Agrega organization_id para aislamiento de datos entre tenants.
    """
    @declared_attr
    def organization_id(cls) -> Column:
        return Column(
            String(36),
            nullable=False,
            index=True
        )

    @classmethod
    def for_tenant(cls, org_id: str):
        """Filtro para obtener registros de un tenant específico"""
        return cls.organization_id == org_id


class AuditFieldsMixin:
    """
    Mixin para campos de auditoría.

    Agrega created_by y updated_by para tracking.
    """
    @declared_attr
    def created_by(cls) -> Column:
        return Column(String(36), nullable=True)

    @declared_attr
    def updated_by(cls) -> Column:
        return Column(String(36), nullable=True)


class UUIDMixin:
    """
    Mixin para IDs UUID.

    Usa UUID como primary key en lugar de auto-increment.
    """
    @declared_attr
    def id(cls) -> Column:
        return Column(
            String(36),
            primary_key=True,
            default=lambda: str(uuid.uuid4()),
            index=True
        )


def generate_uuid() -> str:
    """Genera un UUID como string"""
    return str(uuid.uuid4())


class TenantQueryMixin:
    """
    Mixin para queries con filtro de tenant automático.

    Uso:
        class MyModel(Base, TenantMixin, SoftDeleteMixin):
            ...

        # Query con filtros automáticos
        results = TenantQueryMixin.query_for_tenant(
            session, MyModel, org_id="tenant-123"
        )
    """

    @staticmethod
    async def query_for_tenant(
        session,
        model,
        org_id: str,
        include_deleted: bool = False
    ):
        """
        Ejecuta una query filtrada por tenant.

        Args:
            session: AsyncSession
            model: Modelo a consultar
            org_id: ID de la organización
            include_deleted: Si incluir registros eliminados

        Returns:
            Query filtrada
        """
        from sqlalchemy import select

        query = select(model).where(model.organization_id == org_id)

        if hasattr(model, 'is_deleted') and not include_deleted:
            query = query.where(model.is_deleted == False)

        result = await session.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_by_id_for_tenant(
        session,
        model,
        record_id: str,
        org_id: str,
        include_deleted: bool = False
    ):
        """
        Obtiene un registro por ID verificando el tenant.

        Args:
            session: AsyncSession
            model: Modelo a consultar
            record_id: ID del registro
            org_id: ID de la organización
            include_deleted: Si incluir registros eliminados

        Returns:
            Registro encontrado o None
        """
        from sqlalchemy import select

        query = select(model).where(
            model.id == record_id,
            model.organization_id == org_id
        )

        if hasattr(model, 'is_deleted') and not include_deleted:
            query = query.where(model.is_deleted == False)

        result = await session.execute(query)
        return result.scalar_one_or_none()