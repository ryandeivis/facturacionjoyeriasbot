"""
Teclados del Bot

Define todos los teclados (ReplyKeyboard e InlineKeyboard) utilizados en el bot.
Separado de shared.py para seguir el principio de responsabilidad única.
"""

from telegram import ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from config.constants import UserRole
from .constants import MAX_ITEMS_PER_INVOICE, MAX_ITEM_NAME_LENGTH, BANCOS_COLOMBIA


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
        ['🧾 Nueva Factura'],
        ['📋 Mis Facturas'],
        ['🔍 Buscar Factura']
    ]

    if rol == UserRole.ADMIN.value:
        teclado.append(['👤 Crear Usuario'])

    teclado.append(['🚪 Cerrar Sesión'])

    return ReplyKeyboardMarkup(teclado, resize_keyboard=True)


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """
    Retorna un teclado con solo la opción de cancelar.

    Returns:
        ReplyKeyboardMarkup con botón de cancelar
    """
    return ReplyKeyboardMarkup([['✖ Cancelar']], resize_keyboard=True)


def get_confirm_keyboard() -> ReplyKeyboardMarkup:
    """
    Retorna un teclado de confirmación estándar.

    Returns:
        ReplyKeyboardMarkup con opciones Si/No/Cancelar
    """
    return ReplyKeyboardMarkup([
        ['✓ Sí, continuar'],
        ['✏️ Editar manualmente'],
        ['✖ Cancelar']
    ], resize_keyboard=True)


def get_input_type_keyboard() -> ReplyKeyboardMarkup:
    """
    Retorna el teclado para seleccionar tipo de input de factura.

    Returns:
        ReplyKeyboardMarkup con opciones de input
    """
    return ReplyKeyboardMarkup([
        ['⌨️ Texto'],
        ['🎙️ Voz'],
        ['📸 Foto'],
        ['🧪 Test PDF'],
        ['✖ Cancelar']
    ], resize_keyboard=True)


def get_generate_keyboard() -> ReplyKeyboardMarkup:
    """
    Retorna el teclado para confirmar generación de factura.

    Returns:
        ReplyKeyboardMarkup con opciones de confirmar/cancelar
    """
    return ReplyKeyboardMarkup([
        ['✅ CONFIRMAR Y GENERAR'],
        ['✖ Cancelar']
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
        [InlineKeyboardButton("✓ Sí, continuar", callback_data="confirm_yes")],
        [InlineKeyboardButton("✏️ Editar Productos", callback_data="edit_items_menu")],
    ]
    if has_cliente:
        keyboard.append([InlineKeyboardButton("👤 Editar Cliente", callback_data="edit_cliente")])
    keyboard.append([InlineKeyboardButton("✖ Cancelar", callback_data="confirm_cancel")])
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
        nombre = item.get('nombre', item.get('descripcion', f'Producto {i+1}'))[:MAX_ITEM_NAME_LENGTH]
        precio = item.get('precio', 0)
        keyboard.append([
            InlineKeyboardButton(
                f"{i+1}. {nombre} · ${precio:,.0f}",
                callback_data=f"edit_item_{i}"
            ),
            InlineKeyboardButton("🗑", callback_data=f"delete_item_{i}")
        ])
    if len(items) < MAX_ITEMS_PER_INVOICE:
        keyboard.append([InlineKeyboardButton("➕ Agregar", callback_data="add_item")])
    keyboard.append([InlineKeyboardButton("← Volver", callback_data="back_to_confirm")])
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
        [InlineKeyboardButton("📦 Nombre", callback_data=f"field_{item_index}_nombre")],
        [InlineKeyboardButton("📝 Descripción", callback_data=f"field_{item_index}_descripcion")],
        [InlineKeyboardButton("🔢 Cantidad", callback_data=f"field_{item_index}_cantidad")],
        [InlineKeyboardButton("💵 Precio", callback_data=f"field_{item_index}_precio")],
        [InlineKeyboardButton("← Volver", callback_data="edit_items_menu")]
    ])


def get_cliente_edit_keyboard() -> InlineKeyboardMarkup:
    """
    Teclado para editar campos del cliente detectado.

    Returns:
        InlineKeyboardMarkup con campos del cliente
    """
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Nombre", callback_data="edit_cliente_nombre")],
        [InlineKeyboardButton("🪪 Cédula", callback_data="edit_cliente_cedula")],
        [InlineKeyboardButton("📱 Teléfono", callback_data="edit_cliente_telefono")],
        [InlineKeyboardButton("📍 Dirección", callback_data="edit_cliente_direccion")],
        [InlineKeyboardButton("🏙️ Ciudad", callback_data="edit_cliente_ciudad")],
        [InlineKeyboardButton("📧 Email", callback_data="edit_cliente_email")],
        [InlineKeyboardButton("← Volver", callback_data="back_to_confirm")]
    ])


# ============================================================================
# TECLADOS DE MÉTODO DE PAGO
# ============================================================================

def get_metodo_pago_keyboard() -> ReplyKeyboardMarkup:
    """
    Teclado para seleccionar método de pago.

    Returns:
        ReplyKeyboardMarkup con opciones de pago
    """
    return ReplyKeyboardMarkup([
        ['💵 Efectivo'],
        ['💳 Tarjeta'],
        ['🏦 Transferencia'],
        ['⏭️ Omitir']
    ], resize_keyboard=True)


def get_bancos_keyboard() -> ReplyKeyboardMarkup:
    """
    Teclado para seleccionar banco.

    Returns:
        ReplyKeyboardMarkup con lista de bancos
    """
    # Crear filas de 2 bancos cada una
    keyboard = []
    for i in range(0, len(BANCOS_COLOMBIA), 2):
        row = BANCOS_COLOMBIA[i:i+2]
        keyboard.append(row)
    keyboard.append(['⏭️ Omitir'])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


# ============================================================================
# TECLADOS DE IVA Y DESCUENTO
# ============================================================================

def get_aplicar_iva_keyboard() -> ReplyKeyboardMarkup:
    """
    Teclado para preguntar si aplicar IVA.

    Returns:
        ReplyKeyboardMarkup con opciones Sí/No
    """
    return ReplyKeyboardMarkup([
        ['✅ Sí, aplicar IVA (19%)'],
        ['❌ No, sin IVA']
    ], resize_keyboard=True)


def get_aplicar_descuento_keyboard() -> ReplyKeyboardMarkup:
    """
    Teclado para preguntar si aplicar descuento.

    Returns:
        ReplyKeyboardMarkup con opciones Sí/No
    """
    return ReplyKeyboardMarkup([
        ['✅ Sí, aplicar descuento'],
        ['❌ No, sin descuento']
    ], resize_keyboard=True)