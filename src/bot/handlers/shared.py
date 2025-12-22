"""
Handlers Compartidos

Código compartido entre handlers para evitar dependencias circulares.
Incluye teclados, estados de conversación y utilidades comunes.
"""

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ConversationHandler
from config.constants import UserRole


# ============================================================================
# ESTADOS DE CONVERSACIÓN
# ============================================================================

class AuthStates:
    """Estados para el flujo de autenticación"""
    CEDULA = 0
    PASSWORD = 1
    MENU_PRINCIPAL = 2


class InvoiceStates:
    """Estados para el flujo de facturación"""
    SELECCIONAR_INPUT = 100
    RECIBIR_INPUT = 101
    CONFIRMAR_DATOS = 102
    EDITAR_ITEMS = 103
    DATOS_CLIENTE = 104
    CLIENTE_TELEFONO = 105
    CLIENTE_CEDULA = 106
    GENERAR_FACTURA = 107


# ============================================================================
# TECLADOS COMPARTIDOS
# ============================================================================

def get_menu_keyboard(rol: str) -> ReplyKeyboardMarkup:
    """
    Retorna el teclado del menú principal según el rol del usuario.

    Args:
        rol: Rol del usuario (ADMIN o VENDEDOR)

    Returns:
        ReplyKeyboardMarkup con las opciones del menú
    """
    teclado = [
        ['1. Nueva Factura'],
        ['2. Mis Facturas'],
        ['3. Buscar Factura']
    ]

    if rol == UserRole.ADMIN.value:
        teclado.append(['4. Crear Usuario'])

    teclado.append(['Cerrar Sesion'])

    return ReplyKeyboardMarkup(teclado, resize_keyboard=True)


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """
    Retorna un teclado con solo la opción de cancelar.

    Returns:
        ReplyKeyboardMarkup con botón de cancelar
    """
    return ReplyKeyboardMarkup([['Cancelar']], resize_keyboard=True)


def get_confirm_keyboard() -> ReplyKeyboardMarkup:
    """
    Retorna un teclado de confirmación estándar.

    Returns:
        ReplyKeyboardMarkup con opciones Si/No/Cancelar
    """
    return ReplyKeyboardMarkup([
        ['Si, continuar'],
        ['Editar manualmente'],
        ['Cancelar']
    ], resize_keyboard=True)


def get_input_type_keyboard() -> ReplyKeyboardMarkup:
    """
    Retorna el teclado para seleccionar tipo de input de factura.

    Returns:
        ReplyKeyboardMarkup con opciones de input
    """
    return ReplyKeyboardMarkup([
        ['Texto - Escribir items'],
        ['Voz - Dictar items'],
        ['Foto - Capturar lista'],
        ['Cancelar']
    ], resize_keyboard=True)


def get_generate_keyboard() -> ReplyKeyboardMarkup:
    """
    Retorna el teclado para confirmar generación de factura.

    Returns:
        ReplyKeyboardMarkup con opciones de confirmar/cancelar
    """
    return ReplyKeyboardMarkup([
        ['CONFIRMAR Y GENERAR'],
        ['Cancelar']
    ], resize_keyboard=True)


# ============================================================================
# UTILIDADES COMPARTIDAS
# ============================================================================

def limpiar_datos_factura(context) -> None:
    """
    Limpia los datos temporales de factura del contexto.

    Args:
        context: Contexto de Telegram
    """
    keys_to_remove = [
        'items', 'cliente_nombre', 'cliente_telefono', 'cliente_cedula',
        'subtotal', 'total', 'input_type', 'input_raw', 'transcripcion',
        'manual_mode'
    ]
    for key in keys_to_remove:
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


def format_invoice_status(estado: str) -> str:
    """
    Retorna emoji y texto para un estado de factura.

    Args:
        estado: Estado de la factura

    Returns:
        String con emoji y estado
    """
    estados = {
        "BORRADOR": "📝 Borrador",
        "PENDIENTE": "⏳ Pendiente",
        "PAGADA": "✅ Pagada",
        "ANULADA": "❌ Anulada"
    }
    return estados.get(estado, f"📋 {estado}")


# ============================================================================
# MENSAJES COMUNES
# ============================================================================

MENSAJES = {
    'bienvenida': (
        "JOYERIA - SISTEMA DE FACTURACION\n"
        "================================\n\n"
        "Bienvenido al sistema de facturación\n"
        "para joyerías.\n\n"
        "Para comenzar, ingresa tu número de cédula:"
    ),
    'no_autenticado': (
        "Debes iniciar sesión primero.\n"
        "Usa /start para comenzar."
    ),
    'operacion_cancelada': (
        "Operación cancelada.\n\n"
        "¿Qué deseas hacer?"
    ),
    'error_conexion': (
        "Error al conectar con la base de datos.\n\n"
        "Intenta más tarde."
    ),
    'sesion_cerrada': (
        "Hasta pronto!\n\n"
        "Sesión cerrada."
    ),
    'usuario_no_encontrado': (
        "Usuario no encontrado.\n\n"
        "Contacta al administrador para registrarte."
    ),
    'usuario_inactivo': (
        "Usuario inactivo.\n\n"
        "Contacta al administrador."
    ),
    'password_incorrecta': (
        "Contraseña incorrecta.\n\n"
        "Intenta nuevamente con /start"
    )
}