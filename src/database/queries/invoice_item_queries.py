"""
Queries de Items de Factura

Funciones para consultar y modificar items de factura en la base de datos.
Nota: InvoiceItem no tiene soft delete ni organization_id directo (hereda de Invoice).
Soporta operaciones sync y async.
"""

from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, delete
from typing import Optional, List, Dict, Any

from src.database.models import InvoiceItem, Invoice
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# QUERIES SINCRÓNICAS (compatibilidad)
# ============================================================================

def get_item_by_id(
    db: Session,
    item_id: int,
    org_id: Optional[str] = None
) -> Optional[InvoiceItem]:
    """
    Busca un item por su ID con validación multi-tenant.

    Args:
        db: Sesión de base de datos
        item_id: ID del item
        org_id: ID de organización para validación de seguridad (requerido en producción)

    Returns:
        Item encontrado o None si no existe o no pertenece a la organización
    """
    if org_id:
        # Validación multi-tenant: join con Invoice para verificar organización
        return db.query(InvoiceItem)\
            .join(Invoice, InvoiceItem.invoice_id == Invoice.id)\
            .filter(
                and_(
                    InvoiceItem.id == item_id,
                    Invoice.organization_id == org_id
                )
            ).first()
    else:
        # Sin validación de org (solo para compatibilidad, evitar en producción)
        logger.warning(f"get_item_by_id llamado sin org_id para item {item_id}")
        return db.query(InvoiceItem).filter(InvoiceItem.id == item_id).first()


def get_items_by_invoice(
    db: Session,
    invoice_id: str,
    org_id: Optional[str] = None
) -> List[InvoiceItem]:
    """
    Obtiene todos los items de una factura con validación multi-tenant.

    Args:
        db: Sesión de base de datos
        invoice_id: ID de la factura
        org_id: ID de organización para validación de seguridad

    Returns:
        Lista de items ordenados por número
    """
    if org_id:
        # Validación multi-tenant
        return db.query(InvoiceItem)\
            .join(Invoice, InvoiceItem.invoice_id == Invoice.id)\
            .filter(
                and_(
                    InvoiceItem.invoice_id == invoice_id,
                    Invoice.organization_id == org_id
                )
            ).order_by(InvoiceItem.numero).all()
    else:
        logger.warning(f"get_items_by_invoice llamado sin org_id para factura {invoice_id}")
        return db.query(InvoiceItem).filter(
            InvoiceItem.invoice_id == invoice_id
        ).order_by(InvoiceItem.numero).all()


def create_invoice_item(db: Session, item_data: dict) -> Optional[InvoiceItem]:
    """
    Crea un nuevo item de factura.

    Args:
        db: Sesión de base de datos
        item_data: Diccionario con datos del item

    Returns:
        Item creado o None si hubo error
    """
    try:
        # Calcular subtotal si no viene
        if 'subtotal' not in item_data:
            cantidad = item_data.get('cantidad', 1)
            precio = item_data.get('precio_unitario', 0)
            item_data['subtotal'] = cantidad * precio

        item = InvoiceItem(**item_data)
        db.add(item)
        db.commit()
        db.refresh(item)
        logger.info(f"Item creado: {item.descripcion} para factura {item.invoice_id}")
        return item
    except Exception as e:
        logger.error(f"Error creando item: {e}")
        db.rollback()
        return None


def create_invoice_items_batch(
    db: Session,
    invoice_id: str,
    items: List[dict]
) -> List[InvoiceItem]:
    """
    Crea múltiples items para una factura.

    Args:
        db: Sesión de base de datos
        invoice_id: ID de la factura
        items: Lista de diccionarios con datos de items

    Returns:
        Lista de items creados
    """
    created_items = []
    try:
        for idx, item_data in enumerate(items, 1):
            item_data['invoice_id'] = invoice_id
            item_data['numero'] = idx

            # Calcular subtotal
            cantidad = item_data.get('cantidad', 1)
            precio = item_data.get('precio_unitario', item_data.get('precio', 0))
            item_data['precio_unitario'] = precio
            item_data['subtotal'] = cantidad * precio

            # Limpiar campos no válidos
            item_data.pop('precio', None)

            item = InvoiceItem(**item_data)
            db.add(item)
            created_items.append(item)

        db.commit()
        for item in created_items:
            db.refresh(item)

        logger.info(f"Creados {len(created_items)} items para factura {invoice_id}")
        return created_items
    except Exception as e:
        logger.error(f"Error creando items en batch: {e}")
        db.rollback()
        return []


def delete_items_by_invoice(db: Session, invoice_id: str) -> int:
    """
    Elimina todos los items de una factura.

    Args:
        db: Sesión de base de datos
        invoice_id: ID de la factura

    Returns:
        Número de items eliminados
    """
    try:
        count = db.query(InvoiceItem).filter(
            InvoiceItem.invoice_id == invoice_id
        ).delete()
        db.commit()
        logger.info(f"Eliminados {count} items de factura {invoice_id}")
        return count
    except Exception as e:
        logger.error(f"Error eliminando items: {e}")
        db.rollback()
        return 0


# ============================================================================
# QUERIES ASINCRÓNICAS
# ============================================================================

async def get_item_by_id_async(
    db: AsyncSession,
    item_id: int,
    org_id: Optional[str] = None
) -> Optional[InvoiceItem]:
    """
    Busca un item por su ID con validación multi-tenant (async).

    Args:
        db: AsyncSession de base de datos
        item_id: ID del item
        org_id: ID de organización para validación de seguridad (requerido en producción)

    Returns:
        Item encontrado o None si no existe o no pertenece a la organización
    """
    if org_id:
        # Validación multi-tenant: join con Invoice para verificar organización
        result = await db.execute(
            select(InvoiceItem)
            .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
            .where(
                and_(
                    InvoiceItem.id == item_id,
                    Invoice.organization_id == org_id
                )
            )
        )
    else:
        logger.warning(f"get_item_by_id_async llamado sin org_id para item {item_id}")
        result = await db.execute(
            select(InvoiceItem).where(InvoiceItem.id == item_id)
        )
    return result.scalar_one_or_none()


async def get_items_by_invoice_async(
    db: AsyncSession,
    invoice_id: str,
    org_id: Optional[str] = None
) -> List[InvoiceItem]:
    """
    Obtiene todos los items de una factura con validación multi-tenant (async).

    Args:
        db: AsyncSession de base de datos
        invoice_id: ID de la factura
        org_id: ID de organización para validación de seguridad

    Returns:
        Lista de items ordenados por número
    """
    if org_id:
        # Validación multi-tenant
        result = await db.execute(
            select(InvoiceItem)
            .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
            .where(
                and_(
                    InvoiceItem.invoice_id == invoice_id,
                    Invoice.organization_id == org_id
                )
            )
            .order_by(InvoiceItem.numero)
        )
    else:
        logger.warning(f"get_items_by_invoice_async llamado sin org_id para factura {invoice_id}")
        result = await db.execute(
            select(InvoiceItem)
            .where(InvoiceItem.invoice_id == invoice_id)
            .order_by(InvoiceItem.numero)
        )
    return list(result.scalars().all())


async def create_invoice_item_async(
    db: AsyncSession,
    item_data: dict
) -> Optional[InvoiceItem]:
    """
    Crea un nuevo item de factura (async).

    Args:
        db: AsyncSession de base de datos
        item_data: Diccionario con datos del item (debe incluir invoice_id)

    Returns:
        Item creado o None si hubo error
    """
    try:
        if 'invoice_id' not in item_data:
            raise ValueError("invoice_id es requerido para crear item")

        # Calcular subtotal si no viene
        if 'subtotal' not in item_data:
            cantidad = item_data.get('cantidad', 1)
            precio = item_data.get('precio_unitario', item_data.get('precio', 0))
            item_data['precio_unitario'] = precio
            item_data['subtotal'] = cantidad * precio
            item_data.pop('precio', None)

        item = InvoiceItem(**item_data)
        db.add(item)
        await db.commit()
        await db.refresh(item)
        logger.info(f"Item creado: {item.descripcion} para factura {item.invoice_id}")
        return item
    except Exception as e:
        logger.error(f"Error creando item: {e}")
        await db.rollback()
        return None


async def create_invoice_items_async(
    db: AsyncSession,
    invoice_id: str,
    items: List[dict]
) -> List[InvoiceItem]:
    """
    Crea múltiples items para una factura (async).

    Args:
        db: AsyncSession de base de datos
        invoice_id: ID de la factura
        items: Lista de diccionarios con datos de items

    Returns:
        Lista de items creados
    """
    created_items = []
    try:
        for idx, item_data in enumerate(items, 1):
            # Preparar datos del item
            prepared_data = {
                'invoice_id': invoice_id,
                'numero': idx,
                'descripcion': item_data.get('descripcion', item_data.get('nombre', 'Item')),
                'cantidad': item_data.get('cantidad', 1),
                'precio_unitario': item_data.get('precio_unitario', item_data.get('precio', 0)),
                'material': item_data.get('material'),
                'peso_gramos': item_data.get('peso_gramos'),
                'tipo_prenda': item_data.get('tipo_prenda'),
            }

            # Calcular subtotal
            prepared_data['subtotal'] = prepared_data['cantidad'] * prepared_data['precio_unitario']

            item = InvoiceItem(**prepared_data)
            db.add(item)
            created_items.append(item)

        await db.flush()  # Para obtener IDs sin commit

        logger.info(f"Creados {len(created_items)} items para factura {invoice_id}")
        return created_items
    except Exception as e:
        logger.error(f"Error creando items en batch: {e}")
        await db.rollback()
        return []


async def update_item_async(
    db: AsyncSession,
    item_id: int,
    update_data: dict,
    org_id: Optional[str] = None
) -> Optional[InvoiceItem]:
    """
    Actualiza un item de factura con validación multi-tenant (async).

    Args:
        db: AsyncSession de base de datos
        item_id: ID del item
        update_data: Campos a actualizar
        org_id: ID de organización para validación de seguridad

    Returns:
        Item actualizado o None si no se encontró o no pertenece a la organización
    """
    try:
        item = await get_item_by_id_async(db, item_id, org_id)
        if not item:
            return None

        # Actualizar campos permitidos
        allowed_fields = [
            'descripcion', 'cantidad', 'precio_unitario', 'subtotal',
            'material', 'peso_gramos', 'tipo_prenda', 'numero'
        ]

        for key, value in update_data.items():
            if key in allowed_fields and hasattr(item, key):
                setattr(item, key, value)

        # Recalcular subtotal si cambió cantidad o precio
        if 'cantidad' in update_data or 'precio_unitario' in update_data:
            item.subtotal = item.cantidad * item.precio_unitario  # type: ignore[assignment]

        await db.commit()
        await db.refresh(item)
        logger.info(f"Item actualizado: {item_id}")
        return item
    except Exception as e:
        logger.error(f"Error actualizando item: {e}")
        await db.rollback()
        return None


async def delete_item_async(
    db: AsyncSession,
    item_id: int,
    org_id: Optional[str] = None
) -> bool:
    """
    Elimina un item de factura con validación multi-tenant (async).

    Args:
        db: AsyncSession de base de datos
        item_id: ID del item
        org_id: ID de organización para validación de seguridad

    Returns:
        True si se eliminó correctamente, False si no existe o no pertenece a la org
    """
    try:
        item = await get_item_by_id_async(db, item_id, org_id)
        if item:
            await db.delete(item)
            await db.commit()
            logger.info(f"Item eliminado: {item_id}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error eliminando item: {e}")
        await db.rollback()
        return False


async def delete_items_by_invoice_async(
    db: AsyncSession,
    invoice_id: str
) -> int:
    """
    Elimina todos los items de una factura (async).

    NOTA: Esta función NO hace commit. El caller debe hacer commit
    para confirmar la eliminación. Esto permite usar esta función
    dentro de transacciones más grandes.

    Args:
        db: AsyncSession de base de datos
        invoice_id: ID de la factura

    Returns:
        Número de items eliminados
    """
    try:
        result = await db.execute(
            delete(InvoiceItem).where(InvoiceItem.invoice_id == invoice_id)
        )
        # NO hacer commit aquí - el caller debe hacerlo
        deleted_count = result.rowcount  # type: ignore[attr-defined]
        logger.info(f"Marcados para eliminar {deleted_count} items de factura {invoice_id}")
        return deleted_count if deleted_count else 0
    except Exception as e:
        logger.error(f"Error eliminando items: {e}")
        raise  # Re-lanzar para que el caller maneje el rollback


async def replace_invoice_items_async(
    db: AsyncSession,
    invoice_id: str,
    new_items: List[dict]
) -> List[InvoiceItem]:
    """
    Reemplaza todos los items de una factura (async).

    Elimina los items existentes y crea los nuevos.

    Args:
        db: AsyncSession de base de datos
        invoice_id: ID de la factura
        new_items: Lista de nuevos items

    Returns:
        Lista de items creados
    """
    try:
        # Eliminar items existentes
        await delete_items_by_invoice_async(db, invoice_id)

        # Crear nuevos items
        created = await create_invoice_items_async(db, invoice_id, new_items)

        await db.commit()
        return created
    except Exception as e:
        logger.error(f"Error reemplazando items: {e}")
        await db.rollback()
        return []


async def count_items_by_invoice_async(
    db: AsyncSession,
    invoice_id: str
) -> int:
    """
    Cuenta los items de una factura (async).

    Args:
        db: AsyncSession de base de datos
        invoice_id: ID de la factura

    Returns:
        Número de items
    """
    result = await db.execute(
        select(func.count(InvoiceItem.id))
        .where(InvoiceItem.invoice_id == invoice_id)
    )
    return result.scalar() or 0


async def get_invoice_total_from_items_async(
    db: AsyncSession,
    invoice_id: str
) -> float:
    """
    Calcula el total de una factura sumando sus items (async).

    Args:
        db: AsyncSession de base de datos
        invoice_id: ID de la factura

    Returns:
        Suma de subtotales de los items
    """
    result = await db.execute(
        select(func.sum(InvoiceItem.subtotal))
        .where(InvoiceItem.invoice_id == invoice_id)
    )
    return float(result.scalar() or 0)


# ============================================================================
# QUERIES DE ANÁLISIS (para métricas de joyería)
# ============================================================================

async def get_items_by_material_async(
    db: AsyncSession,
    org_id: str,
    material: str,
    limit: int = 100
) -> List[InvoiceItem]:
    """
    Obtiene items filtrados por material (async).

    Requiere join con Invoice para filtrar por organización.

    Args:
        db: AsyncSession de base de datos
        org_id: ID de organización
        material: Tipo de material (oro_18k, plata_925, etc.)
        limit: Límite de resultados

    Returns:
        Lista de items del material especificado
    """
    result = await db.execute(
        select(InvoiceItem)
        .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
        .where(
            and_(
                Invoice.organization_id == org_id,
                Invoice.is_deleted == False,
                InvoiceItem.material == material
            )
        )
        .order_by(InvoiceItem.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_items_by_tipo_prenda_async(
    db: AsyncSession,
    org_id: str,
    tipo_prenda: str,
    limit: int = 100
) -> List[InvoiceItem]:
    """
    Obtiene items filtrados por tipo de prenda (async).

    Args:
        db: AsyncSession de base de datos
        org_id: ID de organización
        tipo_prenda: Tipo de prenda (anillo, cadena, arete, etc.)
        limit: Límite de resultados

    Returns:
        Lista de items del tipo especificado
    """
    result = await db.execute(
        select(InvoiceItem)
        .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
        .where(
            and_(
                Invoice.organization_id == org_id,
                Invoice.is_deleted == False,
                InvoiceItem.tipo_prenda == tipo_prenda
            )
        )
        .order_by(InvoiceItem.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_top_selling_items_async(
    db: AsyncSession,
    org_id: str,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Obtiene los items más vendidos por descripción (async).

    Args:
        db: AsyncSession de base de datos
        org_id: ID de organización
        limit: Número de items a retornar

    Returns:
        Lista de diccionarios con descripción, cantidad total y valor total
    """
    result = await db.execute(
        select(
            InvoiceItem.descripcion,
            func.sum(InvoiceItem.cantidad).label('cantidad_total'),
            func.sum(InvoiceItem.subtotal).label('valor_total'),
            func.count(InvoiceItem.id).label('veces_vendido')
        )
        .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
        .where(
            and_(
                Invoice.organization_id == org_id,
                Invoice.is_deleted == False
            )
        )
        .group_by(InvoiceItem.descripcion)
        .order_by(func.sum(InvoiceItem.cantidad).desc())
        .limit(limit)
    )

    rows = result.all()
    return [
        {
            'descripcion': row.descripcion,
            'cantidad_total': int(row.cantidad_total or 0),
            'valor_total': float(row.valor_total or 0),
            'veces_vendido': int(row.veces_vendido or 0)
        }
        for row in rows
    ]


async def get_sales_by_material_async(
    db: AsyncSession,
    org_id: str
) -> List[Dict[str, Any]]:
    """
    Obtiene estadísticas de ventas agrupadas por material (async).

    Args:
        db: AsyncSession de base de datos
        org_id: ID de organización

    Returns:
        Lista de diccionarios con material, cantidad y valor total
    """
    result = await db.execute(
        select(
            InvoiceItem.material,
            func.sum(InvoiceItem.cantidad).label('cantidad_total'),
            func.sum(InvoiceItem.subtotal).label('valor_total')
        )
        .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
        .where(
            and_(
                Invoice.organization_id == org_id,
                Invoice.is_deleted == False,
                InvoiceItem.material.isnot(None)
            )
        )
        .group_by(InvoiceItem.material)
        .order_by(func.sum(InvoiceItem.subtotal).desc())
    )

    rows = result.all()
    return [
        {
            'material': row.material,
            'cantidad_total': int(row.cantidad_total or 0),
            'valor_total': float(row.valor_total or 0)
        }
        for row in rows
    ]
