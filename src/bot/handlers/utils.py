"""
Utilidades de Handlers

Funciones utilitarias compartidas entre handlers.
Separado de shared.py para seguir el principio de responsabilidad única.
"""

from typing import Optional
from .constants import INVOICE_CONTEXT_KEYS


def limpiar_datos_factura(context) -> None:
    """
    Limpia los datos temporales de factura del contexto.

    Args:
        context: Contexto de Telegram
    """
    for key in INVOICE_CONTEXT_KEYS:
        context.user_data.pop(key, None)


def limpiar_sesion(context) -> None:
    """
    Limpia todos los datos de sesión del usuario.

    Args:
        context: Contexto de Telegram
    """
    context.user_data.clear()


def is_authenticated(context) -> bool:
    """
    Verifica si el usuario está autenticado.

    Args:
        context: Contexto de Telegram

    Returns:
        True si está autenticado, False en caso contrario
    """
    return context.user_data.get('autenticado', False)


def get_user_info(context) -> dict:
    """
    Obtiene información del usuario actual.

    Args:
        context: Contexto de Telegram

    Returns:
        Diccionario con información del usuario
    """
    return {
        'user_id': context.user_data.get('user_id'),
        'cedula': context.user_data.get('cedula'),
        'nombre': context.user_data.get('nombre'),
        'rol': context.user_data.get('rol'),
        'organization_id': context.user_data.get('organization_id'),
        'autenticado': context.user_data.get('autenticado', False)
    }


def format_currency(amount: float) -> str:
    """
    Formatea un monto como moneda.

    Args:
        amount: Monto a formatear

    Returns:
        String formateado como moneda
    """
    return f"${amount:,.0f}"


def format_title_case(text: str) -> str:
    """
    Formatea texto a Title Case (primera letra mayúscula de cada palabra).

    Maneja casos especiales como "AreTes" -> "Aretes", "CADENA" -> "Cadena".

    Args:
        text: Texto a formatear

    Returns:
        Texto formateado en Title Case
    """
    if not text:
        return text
    return text.lower().title()


def format_invoice_status(estado: str) -> str:
    """
    Retorna emoji y texto para un estado de factura.

    Args:
        estado: Estado de la factura

    Returns:
        String con emoji y estado
    """
    estados = {
        "BORRADOR": "Borrador",
        "PENDIENTE": "Pendiente",
        "PAGADA": "Pagada",
        "ANULADA": "Anulada"
    }
    return estados.get(estado, estado)


def get_organization_id(context) -> Optional[int]:
    """
    Obtiene el organization_id del usuario actual.

    Args:
        context: Contexto de Telegram

    Returns:
        organization_id o None si no está autenticado
    """
    return context.user_data.get('organization_id')


def get_user_id(context) -> Optional[int]:
    """
    Obtiene el user_id del usuario actual.

    Args:
        context: Contexto de Telegram

    Returns:
        user_id o None si no está autenticado
    """
    return context.user_data.get('user_id')