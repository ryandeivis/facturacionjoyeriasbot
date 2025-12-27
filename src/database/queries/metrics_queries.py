"""
Metrics Queries

Repositorio para operaciones de métricas de negocio.
Incluye queries de agregación optimizadas para analytics.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_, func, case, extract
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import MetricEvent
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# CRUD BÁSICO (Síncrono para compatibilidad con bot)
# ============================================================================

def create_metric_event(
    db: Session,
    event_type: str,
    organization_id: Optional[str] = None,
    user_id: Optional[int] = None,
    value: float = 0.0,
    success: bool = True,
    duration_ms: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[MetricEvent]:
    """
    Crea un evento de métrica.

    Args:
        db: Sesión de base de datos
        event_type: Tipo de evento (invoice.created, bot.photo, etc.)
        organization_id: ID de organización (opcional para métricas globales)
        user_id: ID del usuario
        value: Valor numérico
        success: Si la operación fue exitosa
        duration_ms: Duración en milisegundos
        metadata: Datos adicionales

    Returns:
        Evento creado o None si hubo error
    """
    try:
        event = MetricEvent(
            event_type=event_type,
            organization_id=organization_id,
            user_id=user_id,
            value=value,
            success=success,
            duration_ms=duration_ms,
            event_metadata=metadata or {},
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event
    except Exception as e:
        logger.error(f"Error creando metric event: {e}")
        db.rollback()
        return None


def get_recent_events(
    db: Session,
    organization_id: Optional[str] = None,
    event_type: Optional[str] = None,
    since: Optional[datetime] = None,
    limit: int = 100,
) -> List[MetricEvent]:
    """
    Obtiene eventos recientes.

    Args:
        db: Sesión de base de datos
        organization_id: Filtrar por organización
        event_type: Filtrar por tipo de evento
        since: Eventos desde esta fecha
        limit: Máximo de eventos

    Returns:
        Lista de eventos
    """
    query = select(MetricEvent)
    conditions = []

    if organization_id:
        conditions.append(MetricEvent.organization_id == organization_id)

    if event_type:
        conditions.append(MetricEvent.event_type == event_type)

    if since:
        conditions.append(MetricEvent.created_at >= since)

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(MetricEvent.created_at.desc()).limit(limit)

    result = db.execute(query)
    return list(result.scalars().all())


# ============================================================================
# AGREGACIONES
# ============================================================================

def get_event_counts(
    db: Session,
    organization_id: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Obtiene conteos agregados por tipo de evento.

    Args:
        db: Sesión de base de datos
        organization_id: Filtrar por organización
        since: Desde esta fecha
        until: Hasta esta fecha

    Returns:
        Diccionario con conteos por tipo de evento
    """
    conditions = []

    if organization_id:
        conditions.append(MetricEvent.organization_id == organization_id)

    if since:
        conditions.append(MetricEvent.created_at >= since)

    if until:
        conditions.append(MetricEvent.created_at <= until)

    query = select(
        MetricEvent.event_type,
        func.count(MetricEvent.id).label('count'),
        func.sum(MetricEvent.value).label('total_value'),
        func.sum(case((MetricEvent.success == True, 1), else_=0)).label('success_count'),
        func.sum(case((MetricEvent.success == False, 1), else_=0)).label('error_count'),
        func.avg(MetricEvent.duration_ms).label('avg_duration_ms'),
    ).group_by(MetricEvent.event_type)

    if conditions:
        query = query.where(and_(*conditions))

    result = db.execute(query)
    rows = result.all()

    return {
        row.event_type: {
            'count': row.count,
            'total_value': float(row.total_value or 0),
            'success_count': row.success_count,
            'error_count': row.error_count,
            'success_rate': row.success_count / row.count if row.count > 0 else 0,
            'avg_duration_ms': float(row.avg_duration_ms or 0),
        }
        for row in rows
    }


def get_daily_stats(
    db: Session,
    organization_id: Optional[str] = None,
    event_type: Optional[str] = None,
    days: int = 30,
) -> List[Dict[str, Any]]:
    """
    Obtiene estadísticas diarias para series temporales.

    Args:
        db: Sesión de base de datos
        organization_id: Filtrar por organización
        event_type: Filtrar por tipo de evento
        days: Número de días hacia atrás

    Returns:
        Lista de estadísticas por día
    """
    since = datetime.utcnow() - timedelta(days=days)
    conditions = [MetricEvent.created_at >= since]

    if organization_id:
        conditions.append(MetricEvent.organization_id == organization_id)

    if event_type:
        conditions.append(MetricEvent.event_type == event_type)

    # Extraer fecha (día) del timestamp
    date_trunc = func.date(MetricEvent.created_at)

    query = select(
        date_trunc.label('date'),
        func.count(MetricEvent.id).label('count'),
        func.sum(MetricEvent.value).label('total_value'),
        func.sum(case((MetricEvent.success == True, 1), else_=0)).label('success_count'),
    ).where(
        and_(*conditions)
    ).group_by(
        date_trunc
    ).order_by(
        date_trunc
    )

    result = db.execute(query)
    rows = result.all()

    return [
        {
            'date': str(row.date),
            'count': row.count,
            'total_value': float(row.total_value or 0),
            'success_count': row.success_count,
            'success_rate': row.success_count / row.count if row.count > 0 else 0,
        }
        for row in rows
    ]


def get_hourly_distribution(
    db: Session,
    organization_id: Optional[str] = None,
    days: int = 7,
) -> Dict[int, int]:
    """
    Obtiene distribución de eventos por hora del día.

    Args:
        db: Sesión de base de datos
        organization_id: Filtrar por organización
        days: Número de días a analizar

    Returns:
        Diccionario {hora: conteo}
    """
    since = datetime.utcnow() - timedelta(days=days)
    conditions = [MetricEvent.created_at >= since]

    if organization_id:
        conditions.append(MetricEvent.organization_id == organization_id)

    # SQLite usa strftime, PostgreSQL usa extract
    hour_extract = func.cast(func.strftime('%H', MetricEvent.created_at), Integer)

    query = select(
        hour_extract.label('hour'),
        func.count(MetricEvent.id).label('count'),
    ).where(
        and_(*conditions)
    ).group_by(
        hour_extract
    )

    result = db.execute(query)
    rows = result.all()

    # Inicializar todas las horas con 0
    distribution = {h: 0 for h in range(24)}
    for row in rows:
        if row.hour is not None:
            distribution[int(row.hour)] = row.count

    return distribution


def get_organization_summary(
    db: Session,
    organization_id: str,
    since: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Obtiene resumen completo de métricas para una organización.

    Args:
        db: Sesión de base de datos
        organization_id: ID de organización
        since: Desde esta fecha (default: últimos 30 días)

    Returns:
        Resumen de métricas
    """
    if since is None:
        since = datetime.utcnow() - timedelta(days=30)

    # Obtener conteos por tipo de evento
    event_counts = get_event_counts(db, organization_id=organization_id, since=since)

    # Calcular métricas específicas
    invoices_created = event_counts.get('invoice.created', {})
    invoices_paid = event_counts.get('invoice.paid', {})
    bot_photos = event_counts.get('bot.photo', {})
    bot_voice = event_counts.get('bot.voice', {})
    ai_extractions = event_counts.get('ai.extraction', {})

    # Última actividad
    last_event = db.execute(
        select(MetricEvent.created_at)
        .where(MetricEvent.organization_id == organization_id)
        .order_by(MetricEvent.created_at.desc())
        .limit(1)
    ).scalar()

    return {
        'organization_id': organization_id,
        'period_start': since.isoformat(),
        'period_end': datetime.utcnow().isoformat(),
        'invoices': {
            'created': invoices_created.get('count', 0),
            'total_amount': invoices_created.get('total_value', 0),
            'paid': invoices_paid.get('count', 0),
            'paid_amount': invoices_paid.get('total_value', 0),
        },
        'bot': {
            'photos': bot_photos.get('count', 0),
            'photos_success_rate': bot_photos.get('success_rate', 0),
            'voice': bot_voice.get('count', 0),
            'voice_success_rate': bot_voice.get('success_rate', 0),
        },
        'ai': {
            'extractions': ai_extractions.get('count', 0),
            'success_rate': ai_extractions.get('success_rate', 0),
            'avg_duration_ms': ai_extractions.get('avg_duration_ms', 0),
        },
        'last_activity': last_event.isoformat() if last_event else None,
        'event_counts': event_counts,
    }


def get_global_summary(
    db: Session,
    since: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Obtiene resumen global de métricas (todas las organizaciones).

    Args:
        db: Sesión de base de datos
        since: Desde esta fecha

    Returns:
        Resumen global
    """
    if since is None:
        since = datetime.utcnow() - timedelta(days=30)

    # Total de eventos
    total_events = db.execute(
        select(func.count(MetricEvent.id))
        .where(MetricEvent.created_at >= since)
    ).scalar() or 0

    # Organizaciones activas
    active_orgs = db.execute(
        select(func.count(func.distinct(MetricEvent.organization_id)))
        .where(MetricEvent.created_at >= since)
    ).scalar() or 0

    # Conteos por tipo
    event_counts = get_event_counts(db, since=since)

    return {
        'period_start': since.isoformat(),
        'period_end': datetime.utcnow().isoformat(),
        'total_events': total_events,
        'active_organizations': active_orgs,
        'event_counts': event_counts,
    }


# ============================================================================
# LIMPIEZA
# ============================================================================

def cleanup_old_events(
    db: Session,
    retention_days: int = 90,
) -> int:
    """
    Elimina eventos más antiguos que la retención.

    Args:
        db: Sesión de base de datos
        retention_days: Días de retención

    Returns:
        Número de eventos eliminados
    """
    cutoff = datetime.utcnow() - timedelta(days=retention_days)

    try:
        result = db.execute(
            MetricEvent.__table__.delete().where(
                MetricEvent.created_at < cutoff
            )
        )
        db.commit()
        deleted = result.rowcount
        logger.info(f"Limpiados {deleted} eventos de métricas antiguos")
        return deleted
    except Exception as e:
        logger.error(f"Error limpiando eventos: {e}")
        db.rollback()
        return 0


# ============================================================================
# ASYNC VERSIONS (para FastAPI)
# ============================================================================

async def async_create_metric_event(
    db: AsyncSession,
    event_type: str,
    organization_id: Optional[str] = None,
    user_id: Optional[int] = None,
    value: float = 0.0,
    success: bool = True,
    duration_ms: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[MetricEvent]:
    """Versión async de create_metric_event."""
    try:
        event = MetricEvent(
            event_type=event_type,
            organization_id=organization_id,
            user_id=user_id,
            value=value,
            success=success,
            duration_ms=duration_ms,
            event_metadata=metadata or {},
        )
        db.add(event)
        await db.commit()
        await db.refresh(event)
        return event
    except Exception as e:
        logger.error(f"Error creando metric event (async): {e}")
        await db.rollback()
        return None


async def async_get_event_counts(
    db: AsyncSession,
    organization_id: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> Dict[str, Dict[str, Any]]:
    """Versión async de get_event_counts."""
    conditions = []

    if organization_id:
        conditions.append(MetricEvent.organization_id == organization_id)

    if since:
        conditions.append(MetricEvent.created_at >= since)

    if until:
        conditions.append(MetricEvent.created_at <= until)

    query = select(
        MetricEvent.event_type,
        func.count(MetricEvent.id).label('count'),
        func.sum(MetricEvent.value).label('total_value'),
        func.sum(case((MetricEvent.success == True, 1), else_=0)).label('success_count'),
        func.sum(case((MetricEvent.success == False, 1), else_=0)).label('error_count'),
        func.avg(MetricEvent.duration_ms).label('avg_duration_ms'),
    ).group_by(MetricEvent.event_type)

    if conditions:
        query = query.where(and_(*conditions))

    result = await db.execute(query)
    rows = result.all()

    return {
        row.event_type: {
            'count': row.count,
            'total_value': float(row.total_value or 0),
            'success_count': row.success_count,
            'error_count': row.error_count,
            'success_rate': row.success_count / row.count if row.count > 0 else 0,
            'avg_duration_ms': float(row.avg_duration_ms or 0),
        }
        for row in rows
    }


# Import necesario para type hints
from sqlalchemy import Integer
