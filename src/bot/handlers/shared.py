"""
Handlers Compartidos

Módulo de compatibilidad que reexporta desde los módulos refactorizados.
Mantiene retrocompatibilidad con imports existentes.

Módulos refactorizados:
- constants.py: Estados de conversación y constantes
- keyboards.py: Teclados Reply e Inline
- messages.py: Mensajes del sistema
- utils.py: Funciones utilitarias
"""

# Reexports de telegram (para compatibilidad)
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ConversationHandler

# Reexports de constants.py
from .constants import (
    AuthStates,
    InvoiceStates,
    MAX_ITEMS_PER_INVOICE,
    MAX_ITEM_NAME_LENGTH,
    INVOICE_CONTEXT_KEYS,
)

# Reexports de keyboards.py
from .keyboards import (
    get_menu_keyboard,
    get_cancel_keyboard,
    get_confirm_keyboard,
    get_input_type_keyboard,
    get_generate_keyboard,
    get_confirm_inline_keyboard,
    get_items_edit_keyboard,
    get_item_field_keyboard,
    get_cliente_edit_keyboard,
)

# Reexports de messages.py
from .messages import (
    MENSAJES,
    GUIA_INPUT_BASE,
    GUIA_TEXTO,
    GUIA_VOZ,
    GUIA_FOTO,
    MSG_SELECCIONAR_INPUT,
    MSG_CONFIRMAR_DATOS,
    MSG_FACTURA_GENERADA,
    MSG_EDITAR_ITEM,
    MSG_INGRESA_NUEVO_VALOR,
    MSG_ITEM_ACTUALIZADO,
    MSG_DATOS_CLIENTE,
    MSG_CLIENTE_TELEFONO,
    MSG_CLIENTE_DIRECCION,
    MSG_CLIENTE_CIUDAD,
    MSG_CLIENTE_EMAIL,
)

# Reexports de utils.py
from .utils import (
    limpiar_datos_factura,
    limpiar_sesion,
    is_authenticated,
    get_user_info,
    format_currency,
    format_title_case,
    format_invoice_status,
    get_organization_id,
    get_user_id,
)

# Re-export de config.constants para compatibilidad
from config.constants import UserRole


__all__ = [
    # Estados
    'AuthStates',
    'InvoiceStates',
    # Constantes
    'MAX_ITEMS_PER_INVOICE',
    'MAX_ITEM_NAME_LENGTH',
    'INVOICE_CONTEXT_KEYS',
    # Teclados Reply
    'get_menu_keyboard',
    'get_cancel_keyboard',
    'get_confirm_keyboard',
    'get_input_type_keyboard',
    'get_generate_keyboard',
    # Teclados Inline
    'get_confirm_inline_keyboard',
    'get_items_edit_keyboard',
    'get_item_field_keyboard',
    'get_cliente_edit_keyboard',
    # Mensajes
    'MENSAJES',
    'GUIA_INPUT_BASE',
    'GUIA_TEXTO',
    'GUIA_VOZ',
    'GUIA_FOTO',
    'MSG_SELECCIONAR_INPUT',
    'MSG_CONFIRMAR_DATOS',
    'MSG_FACTURA_GENERADA',
    'MSG_EDITAR_ITEM',
    'MSG_INGRESA_NUEVO_VALOR',
    'MSG_ITEM_ACTUALIZADO',
    'MSG_DATOS_CLIENTE',
    'MSG_CLIENTE_TELEFONO',
    'MSG_CLIENTE_DIRECCION',
    'MSG_CLIENTE_CIUDAD',
    'MSG_CLIENTE_EMAIL',
    # Utilidades
    'limpiar_datos_factura',
    'limpiar_sesion',
    'is_authenticated',
    'get_user_info',
    'format_currency',
    'format_title_case',
    'format_invoice_status',
    'get_organization_id',
    'get_user_id',
    # Telegram
    'ReplyKeyboardMarkup',
    'ReplyKeyboardRemove',
    'InlineKeyboardButton',
    'InlineKeyboardMarkup',
    'ConversationHandler',
    # Config
    'UserRole',
]