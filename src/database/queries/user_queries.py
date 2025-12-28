"""
Queries de Usuario

Funciones para consultar y modificar usuarios en la base de datos.
Soporta operaciones sync y async con filtrado por tenant.
"""

from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import Optional, List
from datetime import datetime

from src.database.models import User
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# QUERIES SINCRÓNICAS (compatibilidad)
# ============================================================================

def get_user_by_cedula(db: Session, cedula: str, org_id: Optional[str] = None) -> Optional[User]:
    """
    Busca un usuario por su cédula.

    Args:
        db: Sesión de base de datos
        cedula: Número de cédula
        org_id: ID de organización (opcional para multi-tenant)

    Returns:
        Usuario encontrado o None
    """
    query = db.query(User).filter(
        User.cedula == cedula,
        User.is_deleted == False
    )
    if org_id:
        query = query.filter(User.organization_id == org_id)
    return query.first()


def get_user_by_telegram_id(db: Session, telegram_id: int, org_id: Optional[str] = None) -> Optional[User]:
    """
    Busca un usuario por su ID de Telegram.

    Args:
        db: Sesión de base de datos
        telegram_id: ID de Telegram del usuario
        org_id: ID de organización (opcional)

    Returns:
        Usuario encontrado o None
    """
    query = db.query(User).filter(
        User.telegram_id == telegram_id,
        User.is_deleted == False
    )
    if org_id:
        query = query.filter(User.organization_id == org_id)
    return query.first()


def update_last_login(db: Session, cedula: str, org_id: Optional[str] = None) -> bool:
    """
    Actualiza la fecha de último login de un usuario.

    Args:
        db: Sesión de base de datos
        cedula: Cédula del usuario
        org_id: ID de organización (opcional)

    Returns:
        True si se actualizó correctamente
    """
    try:
        user = get_user_by_cedula(db, cedula, org_id)
        if user:
            user.ultimo_login = datetime.utcnow()  # type: ignore[assignment]
            db.commit()
            return True
        return False
    except Exception as e:
        logger.error(f"Error actualizando último login: {e}")
        db.rollback()
        return False


def create_user(db: Session, user_data: dict) -> Optional[User]:
    """
    Crea un nuevo usuario en la base de datos.

    Args:
        db: Sesión de base de datos
        user_data: Diccionario con datos del usuario

    Returns:
        Usuario creado o None si hubo error
    """
    try:
        user = User(**user_data)
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"Usuario creado: {user.cedula}")
        return user
    except Exception as e:
        logger.error(f"Error creando usuario: {e}")
        db.rollback()
        return None


# ============================================================================
# QUERIES ASINCRÓNICAS
# ============================================================================

async def get_user_by_cedula_async(
    db: AsyncSession,
    cedula: str,
    org_id: str
) -> Optional[User]:
    """
    Busca un usuario por su cédula (async).

    Args:
        db: AsyncSession de base de datos
        cedula: Número de cédula
        org_id: ID de organización (requerido para multi-tenant)

    Returns:
        Usuario encontrado o None
    """
    result = await db.execute(
        select(User).where(
            and_(
                User.cedula == cedula,
                User.organization_id == org_id,
                User.is_deleted == False
            )
        )
    )
    return result.scalar_one_or_none()


async def get_user_by_telegram_id_async(
    db: AsyncSession,
    telegram_id: int,
    org_id: Optional[str] = None
) -> Optional[User]:
    """
    Busca un usuario por su ID de Telegram (async).

    Args:
        db: AsyncSession de base de datos
        telegram_id: ID de Telegram del usuario
        org_id: ID de organización (opcional - busca en todas si None)

    Returns:
        Usuario encontrado o None
    """
    conditions = [
        User.telegram_id == telegram_id,
        User.is_deleted == False
    ]
    if org_id:
        conditions.append(User.organization_id == org_id)

    result = await db.execute(
        select(User).where(and_(*conditions))
    )
    return result.scalar_one_or_none()


async def get_user_by_id_async(
    db: AsyncSession,
    user_id: int,
    org_id: str
) -> Optional[User]:
    """
    Busca un usuario por su ID (async).

    Args:
        db: AsyncSession de base de datos
        user_id: ID del usuario
        org_id: ID de organización

    Returns:
        Usuario encontrado o None
    """
    result = await db.execute(
        select(User).where(
            and_(
                User.id == user_id,
                User.organization_id == org_id,
                User.is_deleted == False
            )
        )
    )
    return result.scalar_one_or_none()


async def update_last_login_async(
    db: AsyncSession,
    cedula: str,
    org_id: str
) -> bool:
    """
    Actualiza la fecha de último login de un usuario (async).

    Args:
        db: AsyncSession de base de datos
        cedula: Cédula del usuario
        org_id: ID de organización

    Returns:
        True si se actualizó correctamente
    """
    try:
        user = await get_user_by_cedula_async(db, cedula, org_id)
        if user:
            user.ultimo_login = datetime.utcnow()  # type: ignore[assignment]
            await db.commit()
            return True
        return False
    except Exception as e:
        logger.error(f"Error actualizando último login: {e}")
        await db.rollback()
        return False


async def create_user_async(
    db: AsyncSession,
    user_data: dict
) -> Optional[User]:
    """
    Crea un nuevo usuario en la base de datos (async).

    Args:
        db: AsyncSession de base de datos
        user_data: Diccionario con datos del usuario (debe incluir organization_id)

    Returns:
        Usuario creado o None si hubo error
    """
    try:
        if 'organization_id' not in user_data:
            raise ValueError("organization_id es requerido para crear usuario")

        user = User(**user_data)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info(f"Usuario creado: {user.cedula} en org: {user.organization_id}")
        return user
    except Exception as e:
        logger.error(f"Error creando usuario: {e}")
        await db.rollback()
        return None


async def get_users_by_org_async(
    db: AsyncSession,
    org_id: str,
    include_deleted: bool = False,
    limit: int = 100,
    offset: int = 0
) -> List[User]:
    """
    Obtiene todos los usuarios de una organización (async).

    Args:
        db: AsyncSession de base de datos
        org_id: ID de organización
        include_deleted: Si incluir usuarios eliminados
        limit: Límite de resultados
        offset: Offset para paginación

    Returns:
        Lista de usuarios
    """
    conditions = [User.organization_id == org_id]
    if not include_deleted:
        conditions.append(User.is_deleted == False)

    result = await db.execute(
        select(User)
        .where(and_(*conditions))
        .order_by(User.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def soft_delete_user_async(
    db: AsyncSession,
    user_id: int,
    org_id: str
) -> bool:
    """
    Elimina lógicamente un usuario (async).

    Args:
        db: AsyncSession de base de datos
        user_id: ID del usuario
        org_id: ID de organización

    Returns:
        True si se eliminó correctamente
    """
    try:
        user = await get_user_by_id_async(db, user_id, org_id)
        if user:
            user.soft_delete()
            await db.commit()
            logger.info(f"Usuario eliminado (soft): {user.cedula}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error eliminando usuario: {e}")
        await db.rollback()
        return False