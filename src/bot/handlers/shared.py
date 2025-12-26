"""
Handlers Compartidos

Código compartido entre handlers para evitar dependencias circulares.
Incluye teclados, estados de conversación y utilidades comunes.
"""

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
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
    # Estados para datos completos del cliente
    CLIENTE_DIRECCION = 108
    CLIENTE_CIUDAD = 109
    CLIENTE_EMAIL = 110
    # Estados para edición granular de items
    EDITAR_SELECCIONAR_ITEM = 111
    EDITAR_ITEM_CAMPO = 112
    EDITAR_ITEM_NOMBRE = 113
    EDITAR_ITEM_CANTIDAD = 114
    EDITAR_ITEM_PRECIO = 115
    AGREGAR_ITEM = 116
    AGREGAR_ITEM_CANTIDAD = 117
    AGREGAR_ITEM_PRECIO = 118
    # Estado para edición de cliente (desde pantalla confirmación)
    EDITAR_CLIENTE_CAMPO = 119


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
        ['Test PDF - Datos de prueba'],
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
# TECLADOS INLINE PARA EDICIÓN GRANULAR
# ============================================================================

def get_confirm_inline_keyboard(has_cliente: bool = False) -> InlineKeyboardMarkup:
    """
    Teclado de confirmación con opciones de edición granular.

    Args:
        has_cliente: True si se detectó información del cliente

    Returns:
        InlineKeyboardMarkup con botones de confirmación y edición
    """
    keyboard = [
        [InlineKeyboardButton("Sí, continuar", callback_data="confirm_yes")],
        [InlineKeyboardButton("Editar Items", callback_data="edit_items_menu")],
    ]
    if has_cliente:
        keyboard.append([InlineKeyboardButton("Editar Cliente", callback_data="edit_cliente")])
    keyboard.append([InlineKeyboardButton("Cancelar", callback_data="confirm_cancel")])
    return InlineKeyboardMarkup(keyboard)


def get_items_edit_keyboard(items: list) -> InlineKeyboardMarkup:
    """
    Teclado con lista de items para editar individualmente.

    Args:
        items: Lista de items a mostrar

    Returns:
        InlineKeyboardMarkup con botones para cada item
    """
    keyboard = []
    for i, item in enumerate(items):
        nombre = item.get('nombre', item.get('descripcion', f'Item {i+1}'))[:20]
        precio = item.get('precio', 0)
        keyboard.append([
            InlineKeyboardButton(
                f"{i+1}. {nombre} - ${precio:,.0f}",
                callback_data=f"edit_item_{i}"
            ),
            InlineKeyboardButton("X", callback_data=f"delete_item_{i}")
        ])
    if len(items) < 6:
        keyboard.append([InlineKeyboardButton("+ Agregar Item", callback_data="add_item")])
    keyboard.append([InlineKeyboardButton("Volver", callback_data="back_to_confirm")])
    return InlineKeyboardMarkup(keyboard)


def get_item_field_keyboard(item_index: int) -> InlineKeyboardMarkup:
    """
    Teclado para seleccionar qué campo del item editar.

    Args:
        item_index: Índice del item a editar

    Returns:
        InlineKeyboardMarkup con opciones de campo
    """
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Editar Nombre", callback_data=f"field_{item_index}_nombre")],
        [InlineKeyboardButton("Editar Cantidad", callback_data=f"field_{item_index}_cantidad")],
        [InlineKeyboardButton("Editar Precio", callback_data=f"field_{item_index}_precio")],
        [InlineKeyboardButton("Volver", callback_data="edit_items_menu")]
    ])


def get_cliente_edit_keyboard() -> InlineKeyboardMarkup:
    """
    Teclado para editar campos del cliente detectado.

    Returns:
        InlineKeyboardMarkup con campos del cliente
    """
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Nombre", callback_data="edit_cliente_nombre")],
        [InlineKeyboardButton("Teléfono", callback_data="edit_cliente_telefono")],
        [InlineKeyboardButton("Dirección", callback_data="edit_cliente_direccion")],
        [InlineKeyboardButton("Ciudad", callback_data="edit_cliente_ciudad")],
        [InlineKeyboardButton("Email", callback_data="edit_cliente_email")],
        [InlineKeyboardButton("Volver", callback_data="back_to_confirm")]
    ])


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
        'cliente_direccion', 'cliente_ciudad', 'cliente_email',
        'subtotal', 'total', 'input_type', 'input_raw', 'transcripcion',
        'manual_mode',
        # Nuevas keys para edición granular
        'n8n_response', 'cliente_detectado', 'editing_item_index',
        'editing_field', 'new_item'
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

    # Convertir a minúsculas y luego capitalizar cada palabra
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
    ),
    'error_general': (
        "Ha ocurrido un error.\n\n"
        "Por favor intenta de nuevo."
    )
}


# ============================================================================
# MENSAJES DE GUÍA PARA FACTURACIÓN
# ============================================================================

GUIA_INPUT_BASE = """
INFORMACION REQUERIDA
=====================

Para generar tu factura necesito:

PRODUCTOS (obligatorio):
  - Nombre del producto
  - Descripcion breve
  - Cantidad
  - Precio unitario

CLIENTE (se pedira despues):
  - Nombre completo
  - Direccion
  - Ciudad
  - Email

Puedes incluir hasta 6 productos.
"""

GUIA_TEXTO = """
INGRESO POR TEXTO
=================

Escribe los productos a facturar.

EJEMPLO:
1. Anillo de compromiso oro 18k
   Anillo solitario con diamante 0.5ct
   Cantidad: 1 - Precio: $2.500.000

2. Cadena plata 925
   Cadena eslabones 50cm
   Cantidad: 1 - Precio: $180.000

3. Aretes perlas
   Aretes gota con perlas cultivadas
   Cantidad: 2 - Precio: $95.000

TIP: Incluye nombre, descripcion, cantidad y precio de cada item.
"""

GUIA_VOZ = """
INGRESO POR VOZ
===============

Envia un mensaje de voz dictando los productos.

EJEMPLO DE LO QUE DEBES DECIR:

"Primer producto: anillo de compromiso en oro 18 kilates,
es un solitario con diamante de medio quilate,
cantidad uno, precio dos millones quinientos mil pesos.

Segundo producto: cadena de plata 925,
eslabones de 50 centimetros,
cantidad uno, precio ciento ochenta mil pesos.

Tercer producto: aretes de perlas cultivadas,
tipo gota, cantidad dos,
precio noventa y cinco mil pesos cada uno."

TIP: Habla claro y menciona cantidad y precio de cada item.
"""

GUIA_FOTO = """
INGRESO POR FOTO
================

Envia una foto clara de:
- Lista de productos escrita
- Ticket o recibo
- Cotizacion previa
- Nota de pedido

ASEGURATE QUE LA IMAGEN TENGA:
- Buena iluminacion
- Texto legible
- Nombres de productos
- Cantidades
- Precios

TIP: Evita sombras y reflejos. Texto horizontal.
"""