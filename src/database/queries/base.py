"""
Base Query Class

Proporciona métodos comunes para todas las queries.
Implementa el patrón Repository con soporte multi-tenant.
"""

from typing import TypeVar, Generic, Optional, List, Type, Any
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Type variable para el modelo
T = TypeVar('T')


class BaseQuery(Generic[T]):
    """
    Clase base para queries con operaciones CRUD comunes.

    Proporciona:
    - get_by_id: Buscar por ID
    - get_all: Listar con paginación
    - create: Crear nuevo registro
    - update: Actualizar registro
    - soft_delete: Eliminar lógicamente
    - count: Contar registros

    Uso:
        class UserQuery(BaseQuery[User]):
            model = User

        query = UserQuery()
        user = await query.get_by_id(db, "123", org_id="org-1")
    """

    model: Type[T] = None

    def __init__(self):
        if self.model is None:
            raise NotImplementedError("Subclass must define 'model' attribute")

    async def get_by_id(
        self,
        db: AsyncSession,
        record_id: Any,
        org_id: str,
        include_deleted: bool = False
    ) -> Optional[T]:
        """
        Busca un registro por su ID.

        Args:
            db: Sesión de base de datos
            record_id: ID del registro
            org_id: ID de organización
            include_deleted: Incluir registros eliminados

        Returns:
            Registro encontrado o None
        """
        conditions = [
            self.model.id == record_id,
            self.model.organization_id == org_id
        ]

        if not include_deleted and hasattr(self.model, 'is_deleted'):
            conditions.append(self.model.is_deleted == False)

        result = await db.execute(
            select(self.model).where(and_(*conditions))
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        db: AsyncSession,
        org_id: str,
        limit: int = 50,
        offset: int = 0,
        include_deleted: bool = False,
        order_by: str = "created_at",
        order_desc: bool = True
    ) -> List[T]:
        """
        Obtiene todos los registros con paginación.

        Args:
            db: Sesión de base de datos
            org_id: ID de organización
            limit: Límite de resultados
            offset: Offset para paginación
            include_deleted: Incluir registros eliminados
            order_by: Campo para ordenar
            order_desc: Orden descendente

        Returns:
            Lista de registros
        """
        conditions = [self.model.organization_id == org_id]

        if not include_deleted and hasattr(self.model, 'is_deleted'):
            conditions.append(self.model.is_deleted == False)

        order_field = getattr(self.model, order_by, self.model.id)
        if order_desc:
            order_field = order_field.desc()

        result = await db.execute(
            select(self.model)
            .where(and_(*conditions))
            .order_by(order_field)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def create(
        self,
        db: AsyncSession,
        data: dict
    ) -> Optional[T]:
        """
        Crea un nuevo registro.

        Args:
            db: Sesión de base de datos
            data: Diccionario con datos del registro

        Returns:
            Registro creado o None si hubo error
        """
        if 'organization_id' not in data:
            raise ValueError("organization_id es requerido")

        try:
            record = self.model(**data)
            db.add(record)
            await db.commit()
            await db.refresh(record)
            logger.info(f"{self.model.__name__} creado: {record.id}")
            return record
        except Exception as e:
            logger.error(f"Error creando {self.model.__name__}: {e}")
            await db.rollback()
            return None

    async def update(
        self,
        db: AsyncSession,
        record_id: Any,
        org_id: str,
        data: dict
    ) -> Optional[T]:
        """
        Actualiza un registro existente.

        Args:
            db: Sesión de base de datos
            record_id: ID del registro
            org_id: ID de organización
            data: Campos a actualizar

        Returns:
            Registro actualizado o None
        """
        try:
            record = await self.get_by_id(db, record_id, org_id)
            if not record:
                return None

            for key, value in data.items():
                if hasattr(record, key):
                    setattr(record, key, value)

            await db.commit()
            await db.refresh(record)
            logger.info(f"{self.model.__name__} actualizado: {record_id}")
            return record
        except Exception as e:
            logger.error(f"Error actualizando {self.model.__name__}: {e}")
            await db.rollback()
            return None

    async def soft_delete(
        self,
        db: AsyncSession,
        record_id: Any,
        org_id: str
    ) -> bool:
        """
        Elimina lógicamente un registro.

        Args:
            db: Sesión de base de datos
            record_id: ID del registro
            org_id: ID de organización

        Returns:
            True si se eliminó correctamente
        """
        try:
            record = await self.get_by_id(db, record_id, org_id)
            if not record:
                return False

            if hasattr(record, 'soft_delete'):
                record.soft_delete()
            elif hasattr(record, 'is_deleted'):
                record.is_deleted = True

            await db.commit()
            logger.info(f"{self.model.__name__} eliminado (soft): {record_id}")
            return True
        except Exception as e:
            logger.error(f"Error eliminando {self.model.__name__}: {e}")
            await db.rollback()
            return False

    async def count(
        self,
        db: AsyncSession,
        org_id: str,
        include_deleted: bool = False
    ) -> int:
        """
        Cuenta registros en la organización.

        Args:
            db: Sesión de base de datos
            org_id: ID de organización
            include_deleted: Incluir eliminados

        Returns:
            Número de registros
        """
        conditions = [self.model.organization_id == org_id]

        if not include_deleted and hasattr(self.model, 'is_deleted'):
            conditions.append(self.model.is_deleted == False)

        result = await db.execute(
            select(func.count(self.model.id)).where(and_(*conditions))
        )
        return result.scalar() or 0

    async def exists(
        self,
        db: AsyncSession,
        record_id: Any,
        org_id: str
    ) -> bool:
        """
        Verifica si existe un registro.

        Args:
            db: Sesión de base de datos
            record_id: ID del registro
            org_id: ID de organización

        Returns:
            True si existe
        """
        record = await self.get_by_id(db, record_id, org_id)
        return record is not None