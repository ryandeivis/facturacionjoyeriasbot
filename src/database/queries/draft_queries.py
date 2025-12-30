"""
Queries de Borradores de Factura (InvoiceDraft)

Funciones para gestionar borradores de factura con trazabilidad completa.
Soporta operaciones sync y async con filtrado por tenant.

Los borradores permiten:
- Tracking del estado del flujo de conversación
- Almacenamiento del input original (texto, voz, foto)
- Snapshot de la extracción de IA
- Historial de cambios del usuario
- Vinculación con la factura final
"""

from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, delete, update
from typing import Optional, List, Any
from datetime import datetime, timedelta

from src.database.models import InvoiceDraft
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Estados válidos para borradores
DRAFT_STATUS_ACTIVE = "active"
DRAFT_STATUS_COMPLETED = "completed"
DRAFT_STATUS_CANCELLED = "cancelled"
DRAFT_STATUS_EXPIRED = "expired"

# Tiempo de expiración por defecto (24 horas)
DEFAULT_EXPIRATION_HOURS = 24


# ============================================================================
# QUERIES SINCRÓNICAS (compatibilidad)
# ============================================================================

def get_draft_by_id(
    db: Session,
    draft_id: str,
    org_id: Optional[str] = None
) -> Optional[InvoiceDraft]:
    """
    Busca un borrador por su ID.

    Args:
        db: Sesión de base de datos
        draft_id: ID del borrador
        org_id: ID de organización (opcional para multi-tenant)

    Returns:
        Borrador encontrado o None
    """
    query = db.query(InvoiceDraft).filter(InvoiceDraft.id == draft_id)
    if org_id:
        query = query.filter(InvoiceDraft.organization_id == org_id)
    return query.first()


def get_active_draft_by_chat(
    db: Session,
    telegram_chat_id: int,
    org_id: Optional[str] = None
) -> Optional[InvoiceDraft]:
    """
    Busca un borrador activo por chat de Telegram.

    Args:
        db: Sesión de base de datos
        telegram_chat_id: ID del chat de Telegram
        org_id: ID de organización (opcional)

    Returns:
        Borrador activo encontrado o None
    """
    query = db.query(InvoiceDraft).filter(
        InvoiceDraft.telegram_chat_id == telegram_chat_id,
        InvoiceDraft.status == DRAFT_STATUS_ACTIVE
    )
    if org_id:
        query = query.filter(InvoiceDraft.organization_id == org_id)
    return query.first()


def create_draft(db: Session, draft_data: dict) -> Optional[InvoiceDraft]:
    """
    Crea un nuevo borrador de factura.

    Args:
        db: Sesión de base de datos
        draft_data: Diccionario con datos del borrador

    Returns:
        Borrador creado o None si hubo error
    """
    try:
        # Establecer expiración si no viene
        if 'expires_at' not in draft_data:
            draft_data['expires_at'] = datetime.utcnow() + timedelta(hours=DEFAULT_EXPIRATION_HOURS)

        draft = InvoiceDraft(**draft_data)
        db.add(draft)
        db.commit()
        db.refresh(draft)
        logger.info(f"Borrador creado: {draft.id[:8]} en chat: {draft.telegram_chat_id}")
        return draft
    except Exception as e:
        logger.error(f"Error creando borrador: {e}")
        db.rollback()
        return None


def cancel_draft(
    db: Session,
    draft_id: str,
    org_id: Optional[str] = None
) -> bool:
    """
    Cancela un borrador (soft cancel).

    Args:
        db: Sesión de base de datos
        draft_id: ID del borrador
        org_id: ID de organización (opcional)

    Returns:
        True si se canceló correctamente
    """
    try:
        draft = get_draft_by_id(db, draft_id, org_id)
        if draft and draft.status == DRAFT_STATUS_ACTIVE:
            draft.status = DRAFT_STATUS_CANCELLED
            db.commit()
            logger.info(f"Borrador cancelado: {draft_id[:8]}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error cancelando borrador: {e}")
        db.rollback()
        return False


# ============================================================================
# QUERIES ASINCRÓNICAS
# ============================================================================

async def get_draft_by_id_async(
    db: AsyncSession,
    draft_id: str,
    org_id: str
) -> Optional[InvoiceDraft]:
    """
    Busca un borrador por su ID (async).

    Args:
        db: AsyncSession de base de datos
        draft_id: ID del borrador
        org_id: ID de organización (requerido para multi-tenant)

    Returns:
        Borrador encontrado o None
    """
    result = await db.execute(
        select(InvoiceDraft).where(
            and_(
                InvoiceDraft.id == draft_id,
                InvoiceDraft.organization_id == org_id
            )
        )
    )
    return result.scalar_one_or_none()


async def get_active_draft_async(
    db: AsyncSession,
    telegram_chat_id: int,
    org_id: str
) -> Optional[InvoiceDraft]:
    """
    Obtiene el borrador activo para un chat de Telegram (async).

    Args:
        db: AsyncSession de base de datos
        telegram_chat_id: ID del chat de Telegram
        org_id: ID de organización

    Returns:
        Borrador activo encontrado o None
    """
    result = await db.execute(
        select(InvoiceDraft).where(
            and_(
                InvoiceDraft.telegram_chat_id == telegram_chat_id,
                InvoiceDraft.organization_id == org_id,
                InvoiceDraft.status == DRAFT_STATUS_ACTIVE
            )
        ).order_by(InvoiceDraft.created_at.desc())
    )
    return result.scalar_one_or_none()


async def create_draft_async(
    db: AsyncSession,
    org_id: str,
    user_id: int,
    telegram_chat_id: int,
    input_type: Optional[str] = None,
    current_step: str = "SELECCIONAR_INPUT"
) -> Optional[InvoiceDraft]:
    """
    Crea un nuevo borrador de factura (async).

    Antes de crear, cancela cualquier borrador activo existente para el chat.

    Args:
        db: AsyncSession de base de datos
        org_id: ID de organización
        user_id: ID del usuario que crea el borrador
        telegram_chat_id: ID del chat de Telegram
        input_type: Tipo de input inicial (TEXTO, VOZ, FOTO)
        current_step: Paso inicial del flujo

    Returns:
        Borrador creado o None si hubo error
    """
    try:
        # Cancelar borradores activos existentes para este chat
        existing = await get_active_draft_async(db, telegram_chat_id, org_id)
        if existing:
            existing.status = DRAFT_STATUS_CANCELLED
            existing.add_change("status", DRAFT_STATUS_ACTIVE, DRAFT_STATUS_CANCELLED, "system")
            logger.info(f"Borrador anterior cancelado: {existing.id[:8]}")

        # Crear nuevo borrador
        draft = InvoiceDraft(
            organization_id=org_id,
            user_id=user_id,
            telegram_chat_id=telegram_chat_id,
            input_type=input_type,
            current_step=current_step,
            status=DRAFT_STATUS_ACTIVE,
            items_data=[],
            customer_data={},
            totals_data={},
            change_history=[],
            expires_at=datetime.utcnow() + timedelta(hours=DEFAULT_EXPIRATION_HOURS)
        )
        db.add(draft)
        await db.commit()
        await db.refresh(draft)

        logger.info(f"Borrador creado: {draft.id[:8]} para user: {user_id} en org: {org_id}")
        return draft

    except Exception as e:
        logger.error(f"Error creando borrador: {e}")
        await db.rollback()
        return None


async def update_draft_step_async(
    db: AsyncSession,
    draft_id: str,
    org_id: str,
    new_step: str,
    data_changes: Optional[dict] = None
) -> Optional[InvoiceDraft]:
    """
    Actualiza el paso actual del borrador y opcionalmente otros datos.

    Args:
        db: AsyncSession de base de datos
        draft_id: ID del borrador
        org_id: ID de organización
        new_step: Nuevo paso del flujo
        data_changes: Diccionario con cambios adicionales (items_data, customer_data, totals_data)

    Returns:
        Borrador actualizado o None si no se encontró
    """
    try:
        draft = await get_draft_by_id_async(db, draft_id, org_id)
        if not draft or draft.status != DRAFT_STATUS_ACTIVE:
            return None

        old_step = draft.current_step
        draft.current_step = new_step
        draft.add_change("current_step", old_step, new_step, "system")

        # Aplicar cambios de datos si se proporcionan
        if data_changes:
            for field, value in data_changes.items():
                if field in ['items_data', 'customer_data', 'totals_data']:
                    old_value = getattr(draft, field)
                    setattr(draft, field, value)
                    draft.add_change(field, old_value, value, "system")

        await db.commit()
        await db.refresh(draft)

        logger.info(f"Borrador {draft_id[:8]} actualizado: {old_step} -> {new_step}")
        return draft

    except Exception as e:
        logger.error(f"Error actualizando paso de borrador: {e}")
        await db.rollback()
        return None


async def record_input_async(
    db: AsyncSession,
    draft_id: str,
    org_id: str,
    input_type: str,
    input_raw: str,
    input_file_path: Optional[str] = None
) -> Optional[InvoiceDraft]:
    """
    Registra el input original del usuario.

    Args:
        db: AsyncSession de base de datos
        draft_id: ID del borrador
        org_id: ID de organización
        input_type: Tipo de input (TEXTO, VOZ, FOTO)
        input_raw: Contenido raw del input (texto o transcripción)
        input_file_path: Ruta al archivo si aplica (voz, foto)

    Returns:
        Borrador actualizado o None si no se encontró
    """
    try:
        draft = await get_draft_by_id_async(db, draft_id, org_id)
        if not draft or draft.status != DRAFT_STATUS_ACTIVE:
            return None

        draft.input_type = input_type
        draft.input_raw = input_raw
        draft.input_file_path = input_file_path
        draft.add_change("input", None, {
            "type": input_type,
            "raw_length": len(input_raw) if input_raw else 0,
            "has_file": input_file_path is not None
        }, "user")

        await db.commit()
        await db.refresh(draft)

        logger.info(f"Input registrado en borrador {draft_id[:8]}: {input_type}")
        return draft

    except Exception as e:
        logger.error(f"Error registrando input: {e}")
        await db.rollback()
        return None


async def record_ai_extraction_async(
    db: AsyncSession,
    draft_id: str,
    org_id: str,
    ai_response: dict,
    items_data: Optional[List[dict]] = None,
    customer_data: Optional[dict] = None,
    totals_data: Optional[dict] = None
) -> Optional[InvoiceDraft]:
    """
    Registra la respuesta de extracción de IA con timestamp.

    Args:
        db: AsyncSession de base de datos
        draft_id: ID del borrador
        org_id: ID de organización
        ai_response: Respuesta raw de la IA
        items_data: Items extraídos
        customer_data: Datos del cliente extraídos
        totals_data: Totales extraídos

    Returns:
        Borrador actualizado o None si no se encontró
    """
    try:
        draft = await get_draft_by_id_async(db, draft_id, org_id)
        if not draft or draft.status != DRAFT_STATUS_ACTIVE:
            return None

        draft.ai_response_raw = ai_response
        draft.ai_extraction_timestamp = datetime.utcnow()

        # Actualizar datos extraídos si se proporcionan
        if items_data is not None:
            draft.items_data = items_data
        if customer_data is not None:
            draft.customer_data = customer_data
        if totals_data is not None:
            draft.totals_data = totals_data

        draft.add_change("ai_extraction", None, {
            "timestamp": draft.ai_extraction_timestamp.isoformat(),
            "items_count": len(items_data) if items_data else 0,
            "has_customer": bool(customer_data),
            "has_totals": bool(totals_data)
        }, "ai")

        await db.commit()
        await db.refresh(draft)

        logger.info(f"Extracción IA registrada en borrador {draft_id[:8]}")
        return draft

    except Exception as e:
        logger.error(f"Error registrando extracción IA: {e}")
        await db.rollback()
        return None


async def record_user_edit_async(
    db: AsyncSession,
    draft_id: str,
    org_id: str,
    field: str,
    old_value: Any,
    new_value: Any
) -> Optional[InvoiceDraft]:
    """
    Registra una edición del usuario en el historial.

    Args:
        db: AsyncSession de base de datos
        draft_id: ID del borrador
        org_id: ID de organización
        field: Nombre del campo editado (ej: "items[0].precio", "customer.nombre")
        old_value: Valor anterior
        new_value: Valor nuevo

    Returns:
        Borrador actualizado o None si no se encontró
    """
    try:
        draft = await get_draft_by_id_async(db, draft_id, org_id)
        if not draft or draft.status != DRAFT_STATUS_ACTIVE:
            return None

        draft.add_change(field, old_value, new_value, "user")

        await db.commit()
        await db.refresh(draft)

        logger.info(f"Edición de usuario registrada en {draft_id[:8]}: {field}")
        return draft

    except Exception as e:
        logger.error(f"Error registrando edición de usuario: {e}")
        await db.rollback()
        return None


async def update_draft_data_async(
    db: AsyncSession,
    draft_id: str,
    org_id: str,
    items_data: Optional[List[dict]] = None,
    customer_data: Optional[dict] = None,
    totals_data: Optional[dict] = None,
    source: str = "user"
) -> Optional[InvoiceDraft]:
    """
    Actualiza los datos del borrador (items, cliente, totales).

    Args:
        db: AsyncSession de base de datos
        draft_id: ID del borrador
        org_id: ID de organización
        items_data: Nuevos items (None para no modificar)
        customer_data: Nuevos datos de cliente (None para no modificar)
        totals_data: Nuevos totales (None para no modificar)
        source: Origen del cambio ("user", "ai", "system")

    Returns:
        Borrador actualizado o None si no se encontró
    """
    try:
        draft = await get_draft_by_id_async(db, draft_id, org_id)
        if not draft or draft.status != DRAFT_STATUS_ACTIVE:
            return None

        if items_data is not None:
            old_items = draft.items_data
            draft.items_data = items_data
            draft.add_change("items_data", old_items, items_data, source)

        if customer_data is not None:
            old_customer = draft.customer_data
            draft.customer_data = customer_data
            draft.add_change("customer_data", old_customer, customer_data, source)

        if totals_data is not None:
            old_totals = draft.totals_data
            draft.totals_data = totals_data
            draft.add_change("totals_data", old_totals, totals_data, source)

        await db.commit()
        await db.refresh(draft)

        logger.info(f"Datos actualizados en borrador {draft_id[:8]} por {source}")
        return draft

    except Exception as e:
        logger.error(f"Error actualizando datos de borrador: {e}")
        await db.rollback()
        return None


async def finalize_draft_async(
    db: AsyncSession,
    draft_id: str,
    org_id: str,
    invoice_id: str
) -> Optional[InvoiceDraft]:
    """
    Marca el borrador como completado y lo vincula a la factura final.

    Args:
        db: AsyncSession de base de datos
        draft_id: ID del borrador
        org_id: ID de organización
        invoice_id: ID de la factura creada

    Returns:
        Borrador finalizado o None si no se encontró
    """
    try:
        draft = await get_draft_by_id_async(db, draft_id, org_id)
        if not draft:
            return None

        old_status = draft.status
        draft.status = DRAFT_STATUS_COMPLETED
        draft.invoice_id = invoice_id
        draft.add_change("finalization", {
            "old_status": old_status
        }, {
            "new_status": DRAFT_STATUS_COMPLETED,
            "invoice_id": invoice_id
        }, "system")

        await db.commit()
        await db.refresh(draft)

        logger.info(f"Borrador {draft_id[:8]} finalizado -> Factura {invoice_id[:8]}")
        return draft

    except Exception as e:
        logger.error(f"Error finalizando borrador: {e}")
        await db.rollback()
        return None


async def cancel_draft_async(
    db: AsyncSession,
    draft_id: str,
    org_id: str,
    reason: Optional[str] = None
) -> bool:
    """
    Cancela un borrador activo (async).

    Args:
        db: AsyncSession de base de datos
        draft_id: ID del borrador
        org_id: ID de organización
        reason: Razón de la cancelación (opcional)

    Returns:
        True si se canceló correctamente
    """
    try:
        draft = await get_draft_by_id_async(db, draft_id, org_id)
        if draft and draft.status == DRAFT_STATUS_ACTIVE:
            draft.status = DRAFT_STATUS_CANCELLED
            draft.add_change("cancellation", DRAFT_STATUS_ACTIVE, {
                "status": DRAFT_STATUS_CANCELLED,
                "reason": reason
            }, "user")

            await db.commit()
            logger.info(f"Borrador cancelado: {draft_id[:8]}")
            return True
        return False

    except Exception as e:
        logger.error(f"Error cancelando borrador: {e}")
        await db.rollback()
        return False


async def cancel_draft_by_chat_async(
    db: AsyncSession,
    telegram_chat_id: int,
    org_id: str,
    reason: Optional[str] = None
) -> bool:
    """
    Cancela el borrador activo de un chat de Telegram.

    Args:
        db: AsyncSession de base de datos
        telegram_chat_id: ID del chat de Telegram
        org_id: ID de organización
        reason: Razón de la cancelación (opcional)

    Returns:
        True si se canceló un borrador
    """
    try:
        draft = await get_active_draft_async(db, telegram_chat_id, org_id)
        if draft:
            return await cancel_draft_async(db, draft.id, org_id, reason)
        return False

    except Exception as e:
        logger.error(f"Error cancelando borrador por chat: {e}")
        await db.rollback()
        return False


async def cleanup_expired_drafts_async(
    db: AsyncSession,
    org_id: Optional[str] = None
) -> int:
    """
    Marca como expirados los borradores que superaron su tiempo de vida.

    Args:
        db: AsyncSession de base de datos
        org_id: ID de organización (None para todas)

    Returns:
        Número de borradores expirados
    """
    try:
        now = datetime.utcnow()

        conditions = [
            InvoiceDraft.status == DRAFT_STATUS_ACTIVE,
            InvoiceDraft.expires_at < now
        ]
        if org_id:
            conditions.append(InvoiceDraft.organization_id == org_id)

        result = await db.execute(
            update(InvoiceDraft)
            .where(and_(*conditions))
            .values(status=DRAFT_STATUS_EXPIRED)
        )

        await db.commit()
        count = result.rowcount

        if count > 0:
            logger.info(f"Borradores expirados: {count}")

        return count

    except Exception as e:
        logger.error(f"Error limpiando borradores expirados: {e}")
        await db.rollback()
        return 0


async def get_drafts_by_user_async(
    db: AsyncSession,
    user_id: int,
    org_id: str,
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0
) -> List[InvoiceDraft]:
    """
    Obtiene los borradores de un usuario (async).

    Args:
        db: AsyncSession de base de datos
        user_id: ID del usuario
        org_id: ID de organización
        status: Filtrar por estado (None para todos)
        limit: Límite de resultados
        offset: Offset para paginación

    Returns:
        Lista de borradores
    """
    conditions = [
        InvoiceDraft.user_id == user_id,
        InvoiceDraft.organization_id == org_id
    ]
    if status:
        conditions.append(InvoiceDraft.status == status)

    result = await db.execute(
        select(InvoiceDraft)
        .where(and_(*conditions))
        .order_by(InvoiceDraft.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def get_drafts_by_org_async(
    db: AsyncSession,
    org_id: str,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[InvoiceDraft]:
    """
    Obtiene todos los borradores de una organización (async).

    Args:
        db: AsyncSession de base de datos
        org_id: ID de organización
        status: Filtrar por estado (None para todos)
        limit: Límite de resultados
        offset: Offset para paginación

    Returns:
        Lista de borradores
    """
    conditions = [InvoiceDraft.organization_id == org_id]
    if status:
        conditions.append(InvoiceDraft.status == status)

    result = await db.execute(
        select(InvoiceDraft)
        .where(and_(*conditions))
        .order_by(InvoiceDraft.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def count_drafts_async(
    db: AsyncSession,
    org_id: str,
    status: Optional[str] = None
) -> int:
    """
    Cuenta los borradores de una organización (async).

    Args:
        db: AsyncSession de base de datos
        org_id: ID de organización
        status: Filtrar por estado (None para todos)

    Returns:
        Número de borradores
    """
    from sqlalchemy import func

    conditions = [InvoiceDraft.organization_id == org_id]
    if status:
        conditions.append(InvoiceDraft.status == status)

    result = await db.execute(
        select(func.count(InvoiceDraft.id)).where(and_(*conditions))
    )
    return result.scalar() or 0


async def get_draft_with_history_async(
    db: AsyncSession,
    draft_id: str,
    org_id: str
) -> Optional[dict]:
    """
    Obtiene un borrador con su historial completo de cambios.

    Args:
        db: AsyncSession de base de datos
        draft_id: ID del borrador
        org_id: ID de organización

    Returns:
        Diccionario con borrador y historial formateado, o None
    """
    draft = await get_draft_by_id_async(db, draft_id, org_id)
    if not draft:
        return None

    return {
        "draft": draft.to_dict(),
        "history_count": len(draft.change_history) if draft.change_history else 0,
        "has_ai_extraction": draft.ai_extraction_timestamp is not None,
        "has_invoice": draft.invoice_id is not None,
        "duration_seconds": (
            (draft.updated_at - draft.created_at).total_seconds()
            if draft.updated_at and draft.created_at else 0
        )
    }
