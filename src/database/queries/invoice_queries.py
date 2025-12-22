"""
Queries de Factura

Funciones para consultar y modificar facturas en la base de datos.
"""

from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime

from src.database.models import Invoice
from src.utils.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)


def generate_invoice_number(db: Session) -> str:
    """
    Genera un número de factura único.
    Formato: JOY-YYYYMM-XXXX

    Args:
        db: Sesión de base de datos

    Returns:
        Número de factura generado
    """
    now = datetime.utcnow()
    prefix = f"{settings.INVOICE_PREFIX}-{now.strftime('%Y%m')}-"

    # Buscar última factura del mes
    last_invoice = db.query(Invoice)\
        .filter(Invoice.numero_factura.like(f"{prefix}%"))\
        .order_by(Invoice.numero_factura.desc())\
        .first()

    if last_invoice:
        last_num = int(last_invoice.numero_factura.split("-")[-1])
        new_num = last_num + 1
    else:
        new_num = 1

    return f"{prefix}{new_num:04d}"


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
        # Generar número de factura si no viene
        if "numero_factura" not in invoice_data:
            invoice_data["numero_factura"] = generate_invoice_number(db)

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


def get_invoices_by_vendedor(db: Session, vendedor_id: int, limit: int = 20) -> List[Invoice]:
    """
    Obtiene las facturas de un vendedor.

    Args:
        db: Sesión de base de datos
        vendedor_id: ID del vendedor
        limit: Número máximo de facturas a retornar

    Returns:
        Lista de facturas
    """
    return db.query(Invoice)\
        .filter(Invoice.vendedor_id == vendedor_id)\
        .order_by(Invoice.fecha_creacion.desc())\
        .limit(limit)\
        .all()


def get_invoice_by_id(db: Session, invoice_id: str) -> Optional[Invoice]:
    """
    Obtiene una factura por su ID.

    Args:
        db: Sesión de base de datos
        invoice_id: ID de la factura

    Returns:
        Factura encontrada o None
    """
    return db.query(Invoice).filter(Invoice.id == invoice_id).first()


def get_invoice_by_number(db: Session, numero_factura: str) -> Optional[Invoice]:
    """
    Obtiene una factura por su número.

    Args:
        db: Sesión de base de datos
        numero_factura: Número de factura

    Returns:
        Factura encontrada o None
    """
    return db.query(Invoice).filter(Invoice.numero_factura == numero_factura).first()


def update_invoice_status(db: Session, invoice_id: str, status: str) -> bool:
    """
    Actualiza el estado de una factura.

    Args:
        db: Sesión de base de datos
        invoice_id: ID de la factura
        status: Nuevo estado

    Returns:
        True si se actualizó correctamente
    """
    try:
        invoice = get_invoice_by_id(db, invoice_id)
        if invoice:
            invoice.estado = status
            if status == "PAGADA":
                invoice.fecha_pago = datetime.utcnow()
            db.commit()
            logger.info(f"Factura {invoice.numero_factura} actualizada a {status}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error al actualizar estado: {e}")
        db.rollback()
        return False