"""
Queries de Cliente

Funciones para consultar y modificar clientes en la base de datos.
Soporta operaciones sync y async con filtrado por tenant.
"""

from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.exc import IntegrityError
from typing import Optional, List, Tuple

from src.database.models import Customer
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# QUERIES SINCRÓNICAS (compatibilidad)
# ============================================================================

def get_customer_by_cedula(
    db: Session,
    cedula: str,
    org_id: Optional[str] = None
) -> Optional[Customer]:
    """
    Busca un cliente por su cédula.

    Args:
        db: Sesión de base de datos
        cedula: Número de cédula
        org_id: ID de organización (opcional para multi-tenant)

    Returns:
        Cliente encontrado o None
    """
    query = db.query(Customer).filter(
        Customer.cedula == cedula,
        Customer.is_deleted == False
    )
    if org_id:
        query = query.filter(Customer.organization_id == org_id)
    return query.first()


def get_customer_by_id(
    db: Session,
    customer_id: str,
    org_id: Optional[str] = None
) -> Optional[Customer]:
    """
    Busca un cliente por su ID.

    Args:
        db: Sesión de base de datos
        customer_id: ID del cliente
        org_id: ID de organización (opcional)

    Returns:
        Cliente encontrado o None
    """
    query = db.query(Customer).filter(
        Customer.id == customer_id,
        Customer.is_deleted == False
    )
    if org_id:
        query = query.filter(Customer.organization_id == org_id)
    return query.first()


def get_customer_by_telefono(
    db: Session,
    telefono: str,
    org_id: Optional[str] = None
) -> Optional[Customer]:
    """
    Busca un cliente por su teléfono.

    Args:
        db: Sesión de base de datos
        telefono: Número de teléfono
        org_id: ID de organización (opcional)

    Returns:
        Cliente encontrado o None
    """
    query = db.query(Customer).filter(
        Customer.telefono == telefono,
        Customer.is_deleted == False
    )
    if org_id:
        query = query.filter(Customer.organization_id == org_id)
    return query.first()


def create_customer(db: Session, customer_data: dict) -> Optional[Customer]:
    """
    Crea un nuevo cliente en la base de datos.

    Args:
        db: Sesión de base de datos
        customer_data: Diccionario con datos del cliente

    Returns:
        Cliente creado o None si hubo error
    """
    try:
        customer = Customer(**customer_data)
        db.add(customer)
        db.commit()
        db.refresh(customer)
        logger.info(f"Cliente creado: {customer.nombre} ({customer.cedula})")
        return customer
    except Exception as e:
        logger.error(f"Error creando cliente: {e}")
        db.rollback()
        return None


def search_customers(
    db: Session,
    org_id: str,
    search_term: str,
    limit: int = 10
) -> List[Customer]:
    """
    Busca clientes por nombre, cédula o teléfono.

    Args:
        db: Sesión de base de datos
        org_id: ID de organización
        search_term: Término de búsqueda
        limit: Límite de resultados

    Returns:
        Lista de clientes que coinciden
    """
    search_pattern = f"%{search_term}%"
    query = db.query(Customer).filter(
        Customer.organization_id == org_id,
        Customer.is_deleted == False,
        (
            Customer.nombre.ilike(search_pattern) |
            Customer.cedula.ilike(search_pattern) |
            Customer.telefono.ilike(search_pattern)
        )
    ).limit(limit)
    return query.all()


# ============================================================================
# QUERIES ASINCRÓNICAS
# ============================================================================

async def get_customer_by_cedula_async(
    db: AsyncSession,
    cedula: str,
    org_id: str
) -> Optional[Customer]:
    """
    Busca un cliente por su cédula (async).

    Args:
        db: AsyncSession de base de datos
        cedula: Número de cédula
        org_id: ID de organización (requerido para multi-tenant)

    Returns:
        Cliente encontrado o None
    """
    result = await db.execute(
        select(Customer).where(
            and_(
                Customer.cedula == cedula,
                Customer.organization_id == org_id,
                Customer.is_deleted == False
            )
        )
    )
    return result.scalar_one_or_none()


async def get_customer_by_id_async(
    db: AsyncSession,
    customer_id: str,
    org_id: str
) -> Optional[Customer]:
    """
    Busca un cliente por su ID (async).

    Args:
        db: AsyncSession de base de datos
        customer_id: ID del cliente
        org_id: ID de organización

    Returns:
        Cliente encontrado o None
    """
    result = await db.execute(
        select(Customer).where(
            and_(
                Customer.id == customer_id,
                Customer.organization_id == org_id,
                Customer.is_deleted == False
            )
        )
    )
    return result.scalar_one_or_none()


async def get_customer_by_telefono_async(
    db: AsyncSession,
    telefono: str,
    org_id: str
) -> Optional[Customer]:
    """
    Busca un cliente por su teléfono (async).

    Args:
        db: AsyncSession de base de datos
        telefono: Número de teléfono
        org_id: ID de organización

    Returns:
        Cliente encontrado o None
    """
    result = await db.execute(
        select(Customer).where(
            and_(
                Customer.telefono == telefono,
                Customer.organization_id == org_id,
                Customer.is_deleted == False
            )
        )
    )
    return result.scalar_one_or_none()


async def create_customer_async(
    db: AsyncSession,
    customer_data: dict
) -> Optional[Customer]:
    """
    Crea un nuevo cliente en la base de datos (async).

    Args:
        db: AsyncSession de base de datos
        customer_data: Diccionario con datos del cliente (debe incluir organization_id)

    Returns:
        Cliente creado o None si hubo error
    """
    try:
        if 'organization_id' not in customer_data:
            raise ValueError("organization_id es requerido para crear cliente")

        customer = Customer(**customer_data)
        db.add(customer)
        await db.commit()
        await db.refresh(customer)
        logger.info(f"Cliente creado: {customer.nombre} en org: {customer.organization_id}")
        return customer
    except Exception as e:
        logger.error(f"Error creando cliente: {e}")
        await db.rollback()
        return None


async def find_or_create_customer_async(
    db: AsyncSession,
    org_id: str,
    customer_data: dict
) -> Customer:
    """
    Busca un cliente existente o crea uno nuevo.

    Busca por cédula primero, luego por teléfono si no tiene cédula.
    Si no encuentra, crea un nuevo cliente.

    Args:
        db: AsyncSession de base de datos
        org_id: ID de organización
        customer_data: Datos del cliente (nombre, cedula, telefono, etc.)

    Returns:
        Cliente existente o recién creado

    Raises:
        ValueError: Si no se puede crear el cliente
    """
    # Usar la versión segura que maneja race conditions
    customer, created = await find_or_create_customer_safe_async(db, org_id, customer_data)
    return customer


async def find_or_create_customer_safe_async(
    db: AsyncSession,
    org_id: str,
    customer_data: dict,
    max_retries: int = 3
) -> Tuple[Customer, bool]:
    """
    Busca un cliente existente o crea uno nuevo con protección contra race conditions.

    Usa un patrón de upsert atómico con manejo de IntegrityError para evitar
    duplicados cuando múltiples requests llegan simultáneamente.

    Args:
        db: AsyncSession de base de datos
        org_id: ID de organización
        customer_data: Datos del cliente (nombre, cedula, telefono, etc.)
        max_retries: Número máximo de reintentos en caso de conflicto

    Returns:
        Tuple de (Cliente, bool) donde bool indica si fue creado (True) o encontrado (False)

    Raises:
        ValueError: Si no se puede crear el cliente después de max_retries
    """
    cedula = customer_data.get('cedula')
    telefono = customer_data.get('telefono')

    for attempt in range(max_retries):
        # 1. Buscar cliente existente
        customer = None

        # Buscar por cédula si existe
        if cedula:
            customer = await get_customer_by_cedula_async(db, cedula, org_id)
            if customer:
                logger.info(f"Cliente encontrado por cédula: {cedula}")
                return customer, False

        # Buscar por teléfono si existe
        if telefono and not customer:
            customer = await get_customer_by_telefono_async(db, telefono, org_id)
            if customer:
                logger.info(f"Cliente encontrado por teléfono: {telefono}")
                return customer, False

        # 2. Intentar crear nuevo cliente
        try:
            customer_data_copy = customer_data.copy()
            customer_data_copy['organization_id'] = org_id

            customer = Customer(**customer_data_copy)
            db.add(customer)
            await db.flush()  # Flush para detectar IntegrityError antes del commit

            logger.info(f"Cliente nuevo creado: {customer.nombre}")
            return customer, True

        except IntegrityError as e:
            # Conflicto de unicidad - otro request ya creó este cliente
            await db.rollback()
            logger.warning(
                f"Conflicto creando cliente (intento {attempt + 1}/{max_retries}): {e}"
            )

            # Buscar el cliente que ya fue creado por otro request
            if cedula:
                customer = await get_customer_by_cedula_async(db, cedula, org_id)
                if customer:
                    logger.info(f"Cliente encontrado después de conflicto: {cedula}")
                    return customer, False

            if telefono:
                customer = await get_customer_by_telefono_async(db, telefono, org_id)
                if customer:
                    logger.info(f"Cliente encontrado después de conflicto: {telefono}")
                    return customer, False

            # Si no lo encontramos, reintentar
            if attempt == max_retries - 1:
                raise ValueError(
                    f"No se pudo crear cliente después de {max_retries} intentos"
                )

    raise ValueError("No se pudo crear el cliente")


async def update_customer_async(
    db: AsyncSession,
    customer_id: str,
    org_id: str,
    update_data: dict
) -> Optional[Customer]:
    """
    Actualiza los datos de un cliente (async).

    Args:
        db: AsyncSession de base de datos
        customer_id: ID del cliente
        org_id: ID de organización
        update_data: Campos a actualizar

    Returns:
        Cliente actualizado o None si no se encontró
    """
    try:
        customer = await get_customer_by_id_async(db, customer_id, org_id)
        if not customer:
            return None

        # Actualizar campos permitidos
        allowed_fields = ['nombre', 'cedula', 'telefono', 'email', 'direccion', 'ciudad', 'notas', 'updated_by']
        for key, value in update_data.items():
            if key in allowed_fields and hasattr(customer, key):
                setattr(customer, key, value)

        await db.commit()
        await db.refresh(customer)
        logger.info(f"Cliente actualizado: {customer_id}")
        return customer
    except Exception as e:
        logger.error(f"Error actualizando cliente: {e}")
        await db.rollback()
        return None


async def get_customers_by_org_async(
    db: AsyncSession,
    org_id: str,
    include_deleted: bool = False,
    limit: int = 50,
    offset: int = 0
) -> List[Customer]:
    """
    Obtiene todos los clientes de una organización (async).

    Args:
        db: AsyncSession de base de datos
        org_id: ID de organización
        include_deleted: Si incluir clientes eliminados
        limit: Límite de resultados
        offset: Offset para paginación

    Returns:
        Lista de clientes
    """
    conditions = [Customer.organization_id == org_id]
    if not include_deleted:
        conditions.append(Customer.is_deleted == False)

    result = await db.execute(
        select(Customer)
        .where(and_(*conditions))
        .order_by(Customer.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def search_customers_async(
    db: AsyncSession,
    org_id: str,
    search_term: str,
    limit: int = 10
) -> List[Customer]:
    """
    Busca clientes por nombre, cédula o teléfono (async).

    Args:
        db: AsyncSession de base de datos
        org_id: ID de organización
        search_term: Término de búsqueda
        limit: Límite de resultados

    Returns:
        Lista de clientes que coinciden
    """
    search_pattern = f"%{search_term}%"
    result = await db.execute(
        select(Customer)
        .where(
            and_(
                Customer.organization_id == org_id,
                Customer.is_deleted == False,
                (
                    Customer.nombre.ilike(search_pattern) |
                    Customer.cedula.ilike(search_pattern) |
                    Customer.telefono.ilike(search_pattern)
                )
            )
        )
        .order_by(Customer.nombre)
        .limit(limit)
    )
    return list(result.scalars().all())


async def soft_delete_customer_async(
    db: AsyncSession,
    customer_id: str,
    org_id: str
) -> bool:
    """
    Elimina lógicamente un cliente (async).

    Args:
        db: AsyncSession de base de datos
        customer_id: ID del cliente
        org_id: ID de organización

    Returns:
        True si se eliminó correctamente
    """
    try:
        customer = await get_customer_by_id_async(db, customer_id, org_id)
        if customer:
            customer.soft_delete()
            await db.commit()
            logger.info(f"Cliente eliminado (soft): {customer.nombre}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error eliminando cliente: {e}")
        await db.rollback()
        return False


async def count_customers_async(
    db: AsyncSession,
    org_id: str,
    include_deleted: bool = False
) -> int:
    """
    Cuenta el total de clientes de una organización (async).

    Args:
        db: AsyncSession de base de datos
        org_id: ID de organización
        include_deleted: Si incluir eliminados

    Returns:
        Número total de clientes
    """
    conditions = [Customer.organization_id == org_id]
    if not include_deleted:
        conditions.append(Customer.is_deleted == False)

    result = await db.execute(
        select(func.count(Customer.id)).where(and_(*conditions))
    )
    return result.scalar() or 0


async def get_recent_customers_async(
    db: AsyncSession,
    org_id: str,
    limit: int = 5
) -> List[Customer]:
    """
    Obtiene los clientes más recientes de una organización (async).

    Args:
        db: AsyncSession de base de datos
        org_id: ID de organización
        limit: Número de clientes a retornar

    Returns:
        Lista de clientes más recientes
    """
    result = await db.execute(
        select(Customer)
        .where(
            and_(
                Customer.organization_id == org_id,
                Customer.is_deleted == False
            )
        )
        .order_by(Customer.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
