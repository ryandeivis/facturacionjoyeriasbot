"""
Queries de Factura

Funciones para consultar y modificar facturas en la base de datos.
Soporta operaciones sync y async con filtrado por tenant.
"""

from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from typing import Optional, List
from datetime import datetime

from src.database.models import Invoice, TenantConfig
from src.utils.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)


# ============================================================================
# QUERIES SINCRÓNICAS (compatibilidad)
# ============================================================================

def generate_invoice_number(db: Session, org_id: Optional[str] = None) -> str:
    """
    Genera un número de factura único.
    Formato: PREFIX-YYYYMM-XXXX

    Args:
        db: Sesión de base de datos
        org_id: ID de organización (opcional)

    Returns:
        Número de factura generado
    """
    now = datetime.utcnow()

    # Obtener prefijo del tenant o usar el default
    prefix = settings.INVOICE_PREFIX
    if org_id:
        config = db.query(TenantConfig).filter(
            TenantConfig.organization_id == org_id
        ).first()
        if config:
            prefix = config.invoice_prefix  # type: ignore[assignment]

    prefix_pattern = f"{prefix}-{now.strftime('%Y%m')}-"

    # Buscar última factura del mes
    query = db.query(Invoice).filter(
        Invoice.numero_factura.like(f"{prefix_pattern}%"),
        Invoice.is_deleted == False
    )
    if org_id:
        query = query.filter(Invoice.organization_id == org_id)

    last_invoice = query.order_by(Invoice.numero_factura.desc()).first()

    if last_invoice:
        last_num = int(last_invoice.numero_factura.split("-")[-1])
        new_num = last_num + 1
    else:
        new_num = 1

    return f"{prefix_pattern}{new_num:04d}"


def create_invoice(db: Session, invoice_data: dict) -> Optional[Invoice]:
    """
    Crea una nueva factura en la base de datos.

    Args:
        db: Sesión de base de datos
        invoice_data: Diccionario con datos de la factura

    Returns:
        Factura creada o None si hubo error
    """
    try:
        org_id = invoice_data.get("organization_id")

        # Generar número de factura si no viene
        if "numero_factura" not in invoice_data:
            invoice_data["numero_factura"] = generate_invoice_number(db, org_id)

        invoice = Invoice(**invoice_data)
        db.add(invoice)
        db.commit()
        db.refresh(invoice)

        logger.info(f"Factura creada: {invoice.numero_factura}")
        return invoice

    except Exception as e:
        logger.error(f"Error al crear factura: {e}")
        db.rollback()
        return None


def get_invoices_by_vendedor(
    db: Session,
    vendedor_id: int,
    org_id: Optional[str] = None,
    limit: int = 20
) -> List[Invoice]:
    """
    Obtiene las facturas de un vendedor.

    Args:
        db: Sesión de base de datos
        vendedor_id: ID del vendedor
        org_id: ID de organización (opcional)
        limit: Número máximo de facturas a retornar

    Returns:
        Lista de facturas
    """
    query = db.query(Invoice).filter(
        Invoice.vendedor_id == vendedor_id,
        Invoice.is_deleted == False
    )
    if org_id:
        query = query.filter(Invoice.organization_id == org_id)

    return query.order_by(Invoice.created_at.desc()).limit(limit).all()


def get_invoice_by_id(
    db: Session,
    invoice_id: str,
    org_id: Optional[str] = None
) -> Optional[Invoice]:
    """
    Obtiene una factura por su ID.

    Args:
        db: Sesión de base de datos
        invoice_id: ID de la factura
        org_id: ID de organización (opcional)

    Returns:
        Factura encontrada o None
    """
    query = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.is_deleted == False
    )
    if org_id:
        query = query.filter(Invoice.organization_id == org_id)
    return query.first()


def get_invoice_by_number(
    db: Session,
    numero_factura: str,
    org_id: Optional[str] = None
) -> Optional[Invoice]:
    """
    Obtiene una factura por su número.

    Args:
        db: Sesión de base de datos
        numero_factura: Número de factura
        org_id: ID de organización (opcional)

    Returns:
        Factura encontrada o None
    """
    query = db.query(Invoice).filter(
        Invoice.numero_factura == numero_factura,
        Invoice.is_deleted == False
    )
    if org_id:
        query = query.filter(Invoice.organization_id == org_id)
    return query.first()


def update_invoice_status(
    db: Session,
    invoice_id: str,
    status: str,
    org_id: Optional[str] = None
) -> bool:
    """
    Actualiza el estado de una factura.

    Args:
        db: Sesión de base de datos
        invoice_id: ID de la factura
        status: Nuevo estado
        org_id: ID de organización (opcional)

    Returns:
        True si se actualizó correctamente
    """
    try:
        invoice = get_invoice_by_id(db, invoice_id, org_id)
        if invoice:
            invoice.estado = status  # type: ignore[assignment]
            if status == "PAGADA":
                invoice.fecha_pago = datetime.utcnow()  # type: ignore[assignment]
            db.commit()
            logger.info(f"Factura {invoice.numero_factura} actualizada a {status}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error al actualizar estado: {e}")
        db.rollback()
        return False


# ============================================================================
# QUERIES ASINCRÓNICAS
# ============================================================================

async def generate_invoice_number_async(
    db: AsyncSession,
    org_id: str
) -> str:
    """
    Genera un número de factura único (async).

    Args:
        db: AsyncSession de base de datos
        org_id: ID de organización

    Returns:
        Número de factura generado
    """
    now = datetime.utcnow()

    # Obtener prefijo del tenant
    config_result = await db.execute(
        select(TenantConfig).where(TenantConfig.organization_id == org_id)
    )
    config = config_result.scalar_one_or_none()
    prefix = config.invoice_prefix if config else settings.INVOICE_PREFIX

    prefix_pattern = f"{prefix}-{now.strftime('%Y%m')}-"

    # Buscar última factura del mes
    invoice_result = await db.execute(
        select(Invoice)
        .where(
            and_(
                Invoice.organization_id == org_id,
                Invoice.numero_factura.like(f"{prefix_pattern}%"),
                Invoice.is_deleted == False
            )
        )
        .order_by(Invoice.numero_factura.desc())
        .limit(1)
    )
    last_invoice = invoice_result.scalar_one_or_none()

    if last_invoice:
        # SQLAlchemy Column[str] es str en runtime
        numero = str(last_invoice.numero_factura)
        last_num = int(numero.split("-")[-1])
        new_num = last_num + 1
    else:
        new_num = 1

    return f"{prefix_pattern}{new_num:04d}"


async def create_invoice_async(
    db: AsyncSession,
    invoice_data: dict
) -> Optional[Invoice]:
    """
    Crea una nueva factura en la base de datos (async).

    Args:
        db: AsyncSession de base de datos
        invoice_data: Diccionario con datos de la factura (debe incluir organization_id)

    Returns:
        Factura creada o None si hubo error
    """
    try:
        if 'organization_id' not in invoice_data:
            raise ValueError("organization_id es requerido para crear factura")

        org_id = invoice_data["organization_id"]

        # Generar número de factura si no viene
        if "numero_factura" not in invoice_data:
            invoice_data["numero_factura"] = await generate_invoice_number_async(db, org_id)

        invoice = Invoice(**invoice_data)
        db.add(invoice)
        await db.commit()
        await db.refresh(invoice)

        logger.info(f"Factura creada: {invoice.numero_factura} en org: {org_id}")
        return invoice

    except Exception as e:
        logger.error(f"Error al crear factura: {e}")
        await db.rollback()
        return None


async def get_invoice_by_id_async(
    db: AsyncSession,
    invoice_id: str,
    org_id: str
) -> Optional[Invoice]:
    """
    Obtiene una factura por su ID (async).

    Args:
        db: AsyncSession de base de datos
        invoice_id: ID de la factura
        org_id: ID de organización

    Returns:
        Factura encontrada o None
    """
    result = await db.execute(
        select(Invoice).where(
            and_(
                Invoice.id == invoice_id,
                Invoice.organization_id == org_id,
                Invoice.is_deleted == False
            )
        )
    )
    return result.scalar_one_or_none()


async def get_invoice_by_number_async(
    db: AsyncSession,
    numero_factura: str,
    org_id: str
) -> Optional[Invoice]:
    """
    Obtiene una factura por su número (async).

    Args:
        db: AsyncSession de base de datos
        numero_factura: Número de factura
        org_id: ID de organización

    Returns:
        Factura encontrada o None
    """
    result = await db.execute(
        select(Invoice).where(
            and_(
                Invoice.numero_factura == numero_factura,
                Invoice.organization_id == org_id,
                Invoice.is_deleted == False
            )
        )
    )
    return result.scalar_one_or_none()


async def get_invoices_by_vendedor_async(
    db: AsyncSession,
    vendedor_id: int,
    org_id: str,
    limit: int = 20,
    offset: int = 0
) -> List[Invoice]:
    """
    Obtiene las facturas de un vendedor (async).

    Args:
        db: AsyncSession de base de datos
        vendedor_id: ID del vendedor
        org_id: ID de organización
        limit: Límite de resultados
        offset: Offset para paginación

    Returns:
        Lista de facturas
    """
    result = await db.execute(
        select(Invoice)
        .where(
            and_(
                Invoice.vendedor_id == vendedor_id,
                Invoice.organization_id == org_id,
                Invoice.is_deleted == False
            )
        )
        .order_by(Invoice.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def get_invoices_by_org_async(
    db: AsyncSession,
    org_id: str,
    estado: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[Invoice]:
    """
    Obtiene todas las facturas de una organización (async).

    Args:
        db: AsyncSession de base de datos
        org_id: ID de organización
        estado: Filtrar por estado (opcional)
        limit: Límite de resultados
        offset: Offset para paginación

    Returns:
        Lista de facturas
    """
    conditions = [
        Invoice.organization_id == org_id,
        Invoice.is_deleted == False
    ]
    if estado:
        conditions.append(Invoice.estado == estado)

    result = await db.execute(
        select(Invoice)
        .where(and_(*conditions))
        .order_by(Invoice.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def update_invoice_status_async(
    db: AsyncSession,
    invoice_id: str,
    status: str,
    org_id: str
) -> bool:
    """
    Actualiza el estado de una factura (async).

    Args:
        db: AsyncSession de base de datos
        invoice_id: ID de la factura
        status: Nuevo estado
        org_id: ID de organización

    Returns:
        True si se actualizó correctamente
    """
    try:
        invoice = await get_invoice_by_id_async(db, invoice_id, org_id)
        if invoice:
            invoice.estado = status  # type: ignore[assignment]
            if status == "PAGADA":
                invoice.fecha_pago = datetime.utcnow()  # type: ignore[assignment]
            await db.commit()
            logger.info(f"Factura {invoice.numero_factura} actualizada a {status}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error al actualizar estado: {e}")
        await db.rollback()
        return False


async def soft_delete_invoice_async(
    db: AsyncSession,
    invoice_id: str,
    org_id: str
) -> bool:
    """
    Elimina lógicamente una factura (async).

    Args:
        db: AsyncSession de base de datos
        invoice_id: ID de la factura
        org_id: ID de organización

    Returns:
        True si se eliminó correctamente
    """
    try:
        invoice = await get_invoice_by_id_async(db, invoice_id, org_id)
        if invoice:
            invoice.soft_delete()
            await db.commit()
            logger.info(f"Factura eliminada (soft): {invoice.numero_factura}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error eliminando factura: {e}")
        await db.rollback()
        return False


async def get_invoice_stats_async(
    db: AsyncSession,
    org_id: str
) -> dict:
    """
    Obtiene estadísticas de facturas por organización (async).

    Args:
        db: AsyncSession de base de datos
        org_id: ID de organización

    Returns:
        Diccionario con estadísticas
    """
    # Total de facturas
    total_result = await db.execute(
        select(func.count(Invoice.id)).where(
            and_(
                Invoice.organization_id == org_id,
                Invoice.is_deleted == False
            )
        )
    )
    total = total_result.scalar()

    # Total por estado
    stats = {"total": total}
    for estado in ["BORRADOR", "PENDIENTE", "PAGADA", "ANULADA"]:
        result = await db.execute(
            select(func.count(Invoice.id)).where(
                and_(
                    Invoice.organization_id == org_id,
                    Invoice.estado == estado,
                    Invoice.is_deleted == False
                )
            )
        )
        stats[estado.lower()] = result.scalar()

    # Total ventas (facturas pagadas)
    ventas_result = await db.execute(
        select(func.sum(Invoice.total)).where(
            and_(
                Invoice.organization_id == org_id,
                Invoice.estado == "PAGADA",
                Invoice.is_deleted == False
            )
        )
    )
    stats["total_ventas"] = ventas_result.scalar() or 0.0  # type: ignore[assignment]

    return stats