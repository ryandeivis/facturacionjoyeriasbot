"""
Queries de Factura

Funciones para consultar y modificar facturas en la base de datos.
Soporta operaciones sync y async con filtrado por tenant.
"""

from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, text
from sqlalchemy.exc import IntegrityError
from typing import Optional, List
from datetime import datetime

from src.database.models import Invoice, InvoiceItem, Customer, TenantConfig
from src.database.queries.customer_queries import (
    find_or_create_customer_async,
    find_or_create_customer,
)
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


def create_invoice_items_batch(
    db: Session,
    invoice_id: str,
    items: list
) -> None:
    """
    Crea items normalizados para una factura (sync).

    Args:
        db: Sesión de base de datos
        invoice_id: ID de la factura
        items: Lista de diccionarios con datos de cada item
    """
    for idx, item in enumerate(items, 1):
        cantidad = item.get('cantidad', 1)
        precio = item.get('precio', item.get('precio_unitario', 0))

        invoice_item = InvoiceItem(
            invoice_id=invoice_id,
            numero=idx,
            descripcion=item.get('nombre', item.get('descripcion', 'Item')),
            cantidad=cantidad,
            precio_unitario=precio,
            subtotal=cantidad * precio,
            material=item.get('material'),
            peso_gramos=item.get('peso_gramos'),
            tipo_prenda=item.get('tipo_prenda'),
        )
        db.add(invoice_item)

    db.flush()
    logger.info(f"Creados {len(items)} items para factura {invoice_id}")


def create_invoice(db: Session, invoice_data: dict) -> Optional[Invoice]:
    """
    Crea una nueva factura en la base de datos con datos normalizados.

    Además de crear la factura, también:
    1. Crea o reutiliza el cliente en la tabla `customers`
    2. Crea los items normalizados en `invoice_items`

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

        # Extraer items antes de crear factura (para normalización)
        items_list = invoice_data.get("items", [])

        invoice = Invoice(**invoice_data)
        db.add(invoice)
        db.flush()  # Para obtener invoice.id

        # Normalizar: Crear customer si hay datos de cliente
        is_new_customer = False
        if org_id:
            customer_data = {
                'nombre': invoice_data.get('cliente_nombre'),
                'cedula': invoice_data.get('cliente_cedula'),
                'telefono': invoice_data.get('cliente_telefono'),
                'email': invoice_data.get('cliente_email'),
                'direccion': invoice_data.get('cliente_direccion'),
                'ciudad': invoice_data.get('cliente_ciudad'),
            }
            # Solo crear customer si tiene al menos nombre
            if customer_data.get('nombre'):
                customer, is_new_customer = find_or_create_customer(db, org_id, customer_data)
                if customer:
                    invoice.customer_id = customer.id
                    # Guardar flag para métricas (se usará en el caller)
                    invoice._is_new_customer = is_new_customer

        # Normalizar: Crear invoice_items
        if items_list and org_id:
            create_invoice_items_batch(db, invoice.id, items_list)

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
    org_id: str,
    limit: int = 20
) -> List[Invoice]:
    """
    Obtiene las facturas de un vendedor.

    Args:
        db: Sesión de base de datos
        vendedor_id: ID del vendedor
        org_id: ID de organización (OBLIGATORIO para seguridad multi-tenant)
        limit: Número máximo de facturas a retornar

    Returns:
        Lista de facturas

    Raises:
        ValueError: Si org_id no se proporciona
    """
    if not org_id:
        raise ValueError("org_id es requerido para garantizar aislamiento multi-tenant")

    return db.query(Invoice).filter(
        Invoice.vendedor_id == vendedor_id,
        Invoice.organization_id == org_id,
        Invoice.is_deleted == False
    ).order_by(Invoice.created_at.desc()).limit(limit).all()


def get_invoice_by_id(
    db: Session,
    invoice_id: str,
    org_id: str
) -> Optional[Invoice]:
    """
    Obtiene una factura por su ID.

    Args:
        db: Sesión de base de datos
        invoice_id: ID de la factura
        org_id: ID de organización (OBLIGATORIO para seguridad multi-tenant)

    Returns:
        Factura encontrada o None

    Raises:
        ValueError: Si org_id no se proporciona
    """
    if not org_id:
        raise ValueError("org_id es requerido para garantizar aislamiento multi-tenant")

    return db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.organization_id == org_id,
        Invoice.is_deleted == False
    ).first()


def get_invoice_by_number(
    db: Session,
    numero_factura: str,
    org_id: str
) -> Optional[Invoice]:
    """
    Obtiene una factura por su número.

    Args:
        db: Sesión de base de datos
        numero_factura: Número de factura
        org_id: ID de organización (OBLIGATORIO para seguridad multi-tenant)

    Returns:
        Factura encontrada o None

    Raises:
        ValueError: Si org_id no se proporciona
    """
    if not org_id:
        raise ValueError("org_id es requerido para garantizar aislamiento multi-tenant")

    return db.query(Invoice).filter(
        Invoice.numero_factura == numero_factura,
        Invoice.organization_id == org_id,
        Invoice.is_deleted == False
    ).first()


def update_invoice_status(
    db: Session,
    invoice_id: str,
    status: str,
    org_id: str
) -> bool:
    """
    Actualiza el estado de una factura.

    Args:
        db: Sesión de base de datos
        invoice_id: ID de la factura
        status: Nuevo estado
        org_id: ID de organización (OBLIGATORIO para seguridad multi-tenant)

    Returns:
        True si se actualizó correctamente

    Raises:
        ValueError: Si org_id no se proporciona
    """
    if not org_id:
        raise ValueError("org_id es requerido para garantizar aislamiento multi-tenant")

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


async def generate_invoice_number_safe_async(
    db: AsyncSession,
    org_id: str,
    max_retries: int = 3
) -> str:
    """
    Genera un número de factura único con protección contra race conditions.

    Usa SELECT FOR UPDATE para bloquear la fila durante la generación,
    evitando números duplicados bajo concurrencia.

    Args:
        db: AsyncSession de base de datos
        org_id: ID de organización
        max_retries: Número máximo de reintentos en caso de conflicto

    Returns:
        Número de factura generado único

    Raises:
        IntegrityError: Si después de max_retries sigue habiendo conflicto
    """
    for attempt in range(max_retries):
        try:
            now = datetime.utcnow()

            # Obtener prefijo del tenant
            config_result = await db.execute(
                select(TenantConfig).where(TenantConfig.organization_id == org_id)
            )
            config = config_result.scalar_one_or_none()
            prefix = config.invoice_prefix if config else settings.INVOICE_PREFIX

            prefix_pattern = f"{prefix}-{now.strftime('%Y%m')}-"

            # SELECT FOR UPDATE para bloquear y evitar race condition
            # Esto bloquea la última factura del mes hasta que se haga commit
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
                .with_for_update(skip_locked=False)
            )
            last_invoice = invoice_result.scalar_one_or_none()

            if last_invoice:
                numero = str(last_invoice.numero_factura)
                last_num = int(numero.split("-")[-1])
                new_num = last_num + 1
            else:
                new_num = 1

            numero_factura = f"{prefix_pattern}{new_num:04d}"

            # Verificar que no existe (por si acaso)
            exists_result = await db.execute(
                select(Invoice.id).where(
                    and_(
                        Invoice.organization_id == org_id,
                        Invoice.numero_factura == numero_factura
                    )
                )
            )
            if exists_result.scalar_one_or_none() is not None:
                logger.warning(
                    f"Número de factura {numero_factura} ya existe, reintentando... "
                    f"(intento {attempt + 1}/{max_retries})"
                )
                continue

            logger.debug(f"Número de factura generado: {numero_factura}")
            return numero_factura

        except IntegrityError as e:
            logger.warning(
                f"Conflicto generando número de factura (intento {attempt + 1}): {e}"
            )
            await db.rollback()
            if attempt == max_retries - 1:
                raise

    # Si llegamos aquí, algo salió muy mal
    raise IntegrityError(
        "No se pudo generar número de factura único después de múltiples intentos",
        params=None,
        orig=None
    )


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

        # Generar número de factura si no viene (usando versión segura)
        if "numero_factura" not in invoice_data:
            invoice_data["numero_factura"] = await generate_invoice_number_safe_async(db, org_id)

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


# ============================================================================
# FUNCIONES AVANZADAS CON ITEMS NORMALIZADOS
# ============================================================================

async def create_invoice_with_items_async(
    db: AsyncSession,
    invoice_data: dict,
    items: List[dict],
    customer_data: Optional[dict] = None
) -> Optional[Invoice]:
    """
    Crea una factura completa con items normalizados y opcionalmente vincula/crea cliente.

    Esta función realiza en una sola transacción:
    1. Busca o crea el cliente (si se proporcionan datos)
    2. Genera número de factura si no viene
    3. Crea la factura
    4. Crea los items normalizados en invoice_items
    5. Mantiene compatibilidad guardando items en JSON también

    Args:
        db: AsyncSession de base de datos
        invoice_data: Diccionario con datos de la factura (debe incluir organization_id)
            - organization_id: (requerido) ID de la organización
            - vendedor_id: ID del vendedor
            - cliente_nombre, cliente_cedula, etc.: Datos del cliente (legacy)
            - subtotal, descuento, impuesto, total: Totales
            - estado: Estado de la factura (default: PENDIENTE)
        items: Lista de diccionarios con datos de cada item:
            - descripcion o nombre: Descripción del item
            - cantidad: Cantidad (default: 1)
            - precio o precio_unitario: Precio unitario
            - material: (opcional) Material de la joya
            - peso_gramos: (opcional) Peso en gramos
            - tipo_prenda: (opcional) Tipo de prenda
        customer_data: Datos del cliente para buscar/crear (opcional)
            - nombre: Nombre del cliente
            - cedula: Cédula del cliente
            - telefono: Teléfono del cliente
            - email, direccion, ciudad: Datos adicionales

    Returns:
        Factura creada con items o None si hubo error

    Example:
        >>> invoice = await create_invoice_with_items_async(
        ...     db,
        ...     invoice_data={
        ...         "organization_id": "org-123",
        ...         "vendedor_id": 1,
        ...         "subtotal": 1500.0,
        ...         "total": 1500.0
        ...     },
        ...     items=[
        ...         {"descripcion": "Anillo oro 18k", "cantidad": 1, "precio": 800.0, "material": "oro"},
        ...         {"descripcion": "Cadena plata", "cantidad": 2, "precio": 350.0, "material": "plata"}
        ...     ],
        ...     customer_data={"nombre": "Juan Pérez", "cedula": "12345678"}
        ... )
    """
    try:
        if 'organization_id' not in invoice_data:
            raise ValueError("organization_id es requerido para crear factura")

        org_id = invoice_data["organization_id"]

        # 1. Find or create customer si hay datos
        customer_id = None
        if customer_data and customer_data.get('nombre'):
            try:
                customer = await find_or_create_customer_async(db, org_id, customer_data)
                customer_id = customer.id
                # Actualizar datos de cliente en invoice_data para compatibilidad
                invoice_data.setdefault('cliente_nombre', customer.nombre)
                invoice_data.setdefault('cliente_cedula', customer.cedula)
                invoice_data.setdefault('cliente_telefono', customer.telefono)
                invoice_data.setdefault('cliente_email', customer.email)
                invoice_data.setdefault('cliente_direccion', customer.direccion)
                invoice_data.setdefault('cliente_ciudad', customer.ciudad)
            except ValueError as e:
                logger.warning(f"No se pudo crear cliente: {e}")

        # 2. Generar número de factura si no viene (usando versión segura)
        if "numero_factura" not in invoice_data:
            invoice_data["numero_factura"] = await generate_invoice_number_safe_async(db, org_id)

        # 3. Preparar items para JSON (compatibilidad)
        items_json = []
        for item in items:
            cantidad = item.get('cantidad', 1)
            precio = item.get('precio', item.get('precio_unitario', 0))
            item_json = {
                "descripcion": item.get('descripcion', item.get('nombre', 'Item')),
                "cantidad": cantidad,
                "precio": precio,
                "subtotal": cantidad * precio
            }
            # Incluir campos opcionales de joyería si existen
            if item.get('material'):
                item_json['material'] = item['material']
            if item.get('peso_gramos'):
                item_json['peso_gramos'] = item['peso_gramos']
            if item.get('tipo_prenda'):
                item_json['tipo_prenda'] = item['tipo_prenda']
            items_json.append(item_json)

        # 4. Crear invoice
        invoice_data['customer_id'] = customer_id
        invoice_data['items'] = items_json  # JSON para compatibilidad
        invoice_data.setdefault('estado', 'PENDIENTE')
        invoice_data.setdefault('version', 1)

        invoice = Invoice(**invoice_data)
        db.add(invoice)
        await db.flush()  # Para obtener invoice.id

        # 5. Crear items normalizados
        for idx, item in enumerate(items, 1):
            cantidad = item.get('cantidad', 1)
            precio = item.get('precio', item.get('precio_unitario', 0))

            invoice_item = InvoiceItem(
                invoice_id=invoice.id,
                numero=idx,
                descripcion=item.get('descripcion', item.get('nombre', 'Item')),
                cantidad=cantidad,
                precio_unitario=precio,
                subtotal=cantidad * precio,
                material=item.get('material'),
                peso_gramos=item.get('peso_gramos'),
                tipo_prenda=item.get('tipo_prenda'),
            )
            db.add(invoice_item)

        await db.commit()
        await db.refresh(invoice)

        logger.info(
            f"Factura con items creada: {invoice.numero_factura} "
            f"({len(items)} items) en org: {org_id}"
        )
        return invoice

    except Exception as e:
        logger.error(f"Error al crear factura con items: {e}")
        await db.rollback()
        return None


async def get_invoice_with_items_async(
    db: AsyncSession,
    invoice_id: str,
    org_id: str
) -> Optional[dict]:
    """
    Obtiene una factura con sus items normalizados.

    Args:
        db: AsyncSession de base de datos
        invoice_id: ID de la factura
        org_id: ID de organización

    Returns:
        Diccionario con factura e items, o None si no existe
    """
    # Obtener factura
    invoice = await get_invoice_by_id_async(db, invoice_id, org_id)
    if not invoice:
        return None

    # Obtener items normalizados
    items_result = await db.execute(
        select(InvoiceItem)
        .where(InvoiceItem.invoice_id == invoice_id)
        .order_by(InvoiceItem.numero)
    )
    items = list(items_result.scalars().all())

    # Obtener cliente si existe
    customer = None
    if invoice.customer_id:
        customer_result = await db.execute(
            select(Customer).where(
                and_(
                    Customer.id == invoice.customer_id,
                    Customer.organization_id == org_id
                )
            )
        )
        customer = customer_result.scalar_one_or_none()

    return {
        "invoice": invoice,
        "items": [item.to_dict() for item in items] if items else invoice.items or [],
        "items_count": len(items) if items else len(invoice.items or []),
        "customer": customer.to_dict() if customer else None,
        "has_normalized_items": len(items) > 0
    }


async def update_invoice_with_items_async(
    db: AsyncSession,
    invoice_id: str,
    org_id: str,
    invoice_updates: Optional[dict] = None,
    items: Optional[List[dict]] = None,
    updated_by: Optional[str] = None
) -> Optional[Invoice]:
    """
    Actualiza una factura y opcionalmente reemplaza sus items.

    Args:
        db: AsyncSession de base de datos
        invoice_id: ID de la factura
        org_id: ID de organización
        invoice_updates: Campos a actualizar en la factura
        items: Nuevos items (reemplaza los existentes si se proporciona)
        updated_by: ID del usuario que actualiza

    Returns:
        Factura actualizada o None si no existe
    """
    try:
        invoice = await get_invoice_by_id_async(db, invoice_id, org_id)
        if not invoice:
            return None

        # Actualizar campos de la factura
        if invoice_updates:
            allowed_fields = [
                'cliente_nombre', 'cliente_cedula', 'cliente_telefono',
                'cliente_email', 'cliente_direccion', 'cliente_ciudad',
                'subtotal', 'descuento', 'impuesto', 'total',
                'estado', 'notas', 'metodo_pago'
            ]
            for key, value in invoice_updates.items():
                if key in allowed_fields and hasattr(invoice, key):
                    setattr(invoice, key, value)

            # Incrementar versión
            invoice.version = (invoice.version or 1) + 1
            if updated_by:
                invoice.updated_by = updated_by

        # Reemplazar items si se proporcionan
        if items is not None:
            # Eliminar items existentes
            await db.execute(
                InvoiceItem.__table__.delete().where(
                    InvoiceItem.invoice_id == invoice_id
                )
            )

            # Crear nuevos items
            items_json = []
            for idx, item in enumerate(items, 1):
                cantidad = item.get('cantidad', 1)
                precio = item.get('precio', item.get('precio_unitario', 0))

                invoice_item = InvoiceItem(
                    invoice_id=invoice.id,
                    numero=idx,
                    descripcion=item.get('descripcion', item.get('nombre', 'Item')),
                    cantidad=cantidad,
                    precio_unitario=precio,
                    subtotal=cantidad * precio,
                    material=item.get('material'),
                    peso_gramos=item.get('peso_gramos'),
                    tipo_prenda=item.get('tipo_prenda'),
                )
                db.add(invoice_item)

                items_json.append({
                    "descripcion": invoice_item.descripcion,
                    "cantidad": cantidad,
                    "precio": precio,
                    "subtotal": cantidad * precio
                })

            # Actualizar JSON para compatibilidad
            invoice.items = items_json

        await db.commit()
        await db.refresh(invoice)

        logger.info(f"Factura actualizada: {invoice.numero_factura}")
        return invoice

    except Exception as e:
        logger.error(f"Error actualizando factura con items: {e}")
        await db.rollback()
        return None


async def get_invoices_by_customer_async(
    db: AsyncSession,
    customer_id: str,
    org_id: str,
    limit: int = 20,
    offset: int = 0
) -> List[Invoice]:
    """
    Obtiene las facturas de un cliente específico.

    Args:
        db: AsyncSession de base de datos
        customer_id: ID del cliente
        org_id: ID de organización
        limit: Límite de resultados
        offset: Offset para paginación

    Returns:
        Lista de facturas del cliente
    """
    result = await db.execute(
        select(Invoice)
        .where(
            and_(
                Invoice.customer_id == customer_id,
                Invoice.organization_id == org_id,
                Invoice.is_deleted == False
            )
        )
        .order_by(Invoice.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())