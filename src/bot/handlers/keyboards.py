"""
Teclados del Bot

Define todos los teclados (ReplyKeyboard e InlineKeyboard) utilizados en el bot.
Separado de shared.py para seguir el principio de responsabilidad única.
"""

from telegram import ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from config.constants import UserRole
from .constants import MAX_ITEMS_PER_INVOICE, MAX_ITEM_NAME_LENGTH


# ============================================================================
# REPLY KEYBOARDS (teclados estándar)
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
# INLINE KEYBOARDS (teclados con callbacks)
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
        nombre = item.get('nombre', item.get('descripcion', f'Item {i+1}'))[:MAX_ITEM_NAME_LENGTH]
        precio = item.get('precio', 0)
        keyboard.append([
            InlineKeyboardButton(
                f"{i+1}. {nombre} - ${precio:,.0f}",
                callback_data=f"edit_item_{i}"
            ),
            InlineKeyboardButton("X", callback_data=f"delete_item_{i}")
        ])
    if len(items) < MAX_ITEMS_PER_INVOICE:
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