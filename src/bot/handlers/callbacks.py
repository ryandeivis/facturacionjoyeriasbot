"""
Handlers de Callback Query

Maneja interacciones con InlineKeyboard para edición granular de items
en el flujo de facturación.
"""

from telegram import Update
from telegram.ext import ContextTypes

from src.bot.handlers.shared import (
    AuthStates,
    InvoiceStates,
    get_confirm_inline_keyboard,
    get_items_edit_keyboard,
    get_item_field_keyboard,
    get_cliente_edit_keyboard,
    get_menu_keyboard,
    limpiar_datos_factura,
    format_currency
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# HANDLER PRINCIPAL DE CALLBACKS
# ============================================================================

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Router principal para CallbackQueries.

    Determina la acción basada en callback_data y delega al handler apropiado.
    """
    query = update.callback_query
    await query.answer()

    data = query.data

    # Confirmación principal
    if data == "confirm_yes":
        return await _confirm_yes(update, context)
    if data == "confirm_cancel":
        return await _confirm_cancel(update, context)

    # Menú de edición de items
    if data == "edit_items_menu":
        return await _show_items_menu(update, context)
    if data.startswith("edit_item_"):
        item_index = int(data.split("_")[2])
        return await _show_item_fields(update, context, item_index)
    if data.startswith("delete_item_"):
        item_index = int(data.split("_")[2])
        return await _delete_item(update, context, item_index)
    if data == "add_item":
        return await _start_add_item(update, context)

    # Edición de campos de item
    if data.startswith("field_"):
        parts = data.split("_")
        item_index = int(parts[1])
        field = parts[2]
        return await _start_field_edit(update, context, item_index, field)

    # Menú de edición de cliente
    if data == "edit_cliente":
        return await _show_cliente_menu(update, context)
    if data.startswith("edit_cliente_"):
        field = data.replace("edit_cliente_", "")
        return await _start_cliente_field_edit(update, context, field)

    # Navegación
    if data == "back_to_confirm":
        return await _show_confirm_screen(update, context)

    return InvoiceStates.CONFIRMAR_DATOS


# ============================================================================
# HANDLERS DE CONFIRMACIÓN
# ============================================================================

async def _confirm_yes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Usuario confirmó los datos, proceder a generar factura o pedir datos faltantes."""
    from src.bot.handlers.shared import get_generate_keyboard

    query = update.callback_query

    # Pre-llenar datos del cliente si fueron detectados
    cliente_detectado = context.user_data.get('cliente_detectado', {})

    if cliente_detectado:
        if cliente_detectado.get('nombre'):
            context.user_data['cliente_nombre'] = cliente_detectado.get('nombre')
        if cliente_detectado.get('telefono'):
            context.user_data['cliente_telefono'] = cliente_detectado.get('telefono')
        if cliente_detectado.get('direccion'):
            context.user_data['cliente_direccion'] = cliente_detectado.get('direccion')
        if cliente_detectado.get('ciudad'):
            context.user_data['cliente_ciudad'] = cliente_detectado.get('ciudad')
        if cliente_detectado.get('email'):
            context.user_data['cliente_email'] = cliente_detectado.get('email')

    # Verificar si tenemos al menos nombre del cliente (dato mínimo requerido)
    nombre_cliente = context.user_data.get('cliente_nombre', '')

    if nombre_cliente:
        # Ya tenemos nombre, ir directo a generar factura
        items = context.user_data.get('items', [])
        total = context.user_data.get('total', 0)

        resumen = "RESUMEN DE FACTURA\n"
        resumen += "=========================\n\n"
        resumen += f"Cliente: {nombre_cliente}\n"
        if context.user_data.get('cliente_telefono'):
            resumen += f"Teléfono: {context.user_data.get('cliente_telefono')}\n"
        if context.user_data.get('cliente_direccion'):
            resumen += f"Dirección: {context.user_data.get('cliente_direccion')}\n"
        if context.user_data.get('cliente_ciudad'):
            resumen += f"Ciudad: {context.user_data.get('cliente_ciudad')}\n"
        if context.user_data.get('cliente_email'):
            resumen += f"Email: {context.user_data.get('cliente_email')}\n"

        resumen += f"\nItems: {len(items)}\n"
        resumen += f"Total: {format_currency(total)}\n\n"
        resumen += "¿Generar factura?"

        await query.edit_message_text(resumen)

        # Enviar nuevo mensaje con teclado
        await query.message.reply_text(
            "Presiona CONFIRMAR para generar la factura:",
            reply_markup=get_generate_keyboard()
        )

        return InvoiceStates.GENERAR_FACTURA
    else:
        # No tenemos nombre, pedir datos del cliente
        await query.edit_message_text(
            "DATOS DEL CLIENTE\n"
            "=========================\n\n"
            "Ingresa el nombre del cliente:"
        )

        return InvoiceStates.DATOS_CLIENTE


async def _confirm_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Usuario canceló la operación."""
    query = update.callback_query
    rol = context.user_data.get('rol')

    await query.edit_message_text("Operación cancelada.")

    # Enviar mensaje con menú
    await query.message.reply_text(
        "¿Qué deseas hacer?",
        reply_markup=get_menu_keyboard(rol)
    )

    limpiar_datos_factura(context)
    return AuthStates.MENU_PRINCIPAL


# ============================================================================
# HANDLERS DE EDICIÓN DE ITEMS
# ============================================================================

async def _show_items_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muestra menú de edición de items."""
    query = update.callback_query
    items = context.user_data.get('items', [])

    if not items:
        await query.edit_message_text(
            "No hay items para editar.\n"
            "Usa 'Agregar Item' para comenzar.",
            reply_markup=get_items_edit_keyboard([])
        )
        return InvoiceStates.EDITAR_SELECCIONAR_ITEM

    # Construir resumen de items
    items_text = "EDITAR ITEMS\n=========================\n\n"
    total = 0
    for i, item in enumerate(items, 1):
        nombre = item.get('nombre', item.get('descripcion', f'Item {i}'))
        cantidad = item.get('cantidad', 1)
        precio = item.get('precio', 0)
        subtotal = cantidad * precio
        total += subtotal
        items_text += f"{i}. {nombre}\n"
        items_text += f"   {cantidad} x {format_currency(precio)} = {format_currency(subtotal)}\n\n"

    items_text += f"TOTAL: {format_currency(total)}\n\n"
    items_text += "Selecciona un item para editar:"

    await query.edit_message_text(
        items_text,
        reply_markup=get_items_edit_keyboard(items)
    )

    return InvoiceStates.EDITAR_SELECCIONAR_ITEM


async def _show_item_fields(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    item_index: int
) -> int:
    """Muestra opciones de edición para un item específico."""
    query = update.callback_query
    items = context.user_data.get('items', [])

    if item_index >= len(items):
        await query.answer("Item no encontrado")
        return await _show_items_menu(update, context)

    item = items[item_index]
    nombre = item.get('nombre', item.get('descripcion', 'Sin nombre'))
    cantidad = item.get('cantidad', 1)
    precio = item.get('precio', 0)

    context.user_data['editing_item_index'] = item_index

    await query.edit_message_text(
        f"EDITAR ITEM {item_index + 1}\n"
        f"=========================\n\n"
        f"Nombre: {nombre}\n"
        f"Cantidad: {cantidad}\n"
        f"Precio: {format_currency(precio)}\n"
        f"Total: {format_currency(cantidad * precio)}\n\n"
        f"¿Qué deseas editar?",
        reply_markup=get_item_field_keyboard(item_index)
    )

    return InvoiceStates.EDITAR_ITEM_CAMPO


async def _start_field_edit(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    item_index: int,
    field: str
) -> int:
    """Inicia la edición de un campo específico del item."""
    query = update.callback_query
    items = context.user_data.get('items', [])

    if item_index >= len(items):
        return await _show_items_menu(update, context)

    item = items[item_index]
    context.user_data['editing_item_index'] = item_index
    context.user_data['editing_field'] = field

    if field == 'nombre':
        current = item.get('nombre', item.get('descripcion', ''))
        await query.edit_message_text(
            f"Nombre actual: {current}\n\n"
            "Escribe el nuevo nombre:"
        )
        return InvoiceStates.EDITAR_ITEM_NOMBRE

    elif field == 'cantidad':
        current = item.get('cantidad', 1)
        await query.edit_message_text(
            f"Cantidad actual: {current}\n\n"
            "Escribe la nueva cantidad (número):"
        )
        return InvoiceStates.EDITAR_ITEM_CANTIDAD

    elif field == 'precio':
        current = item.get('precio', 0)
        await query.edit_message_text(
            f"Precio actual: {format_currency(current)}\n\n"
            "Escribe el nuevo precio (solo números):"
        )
        return InvoiceStates.EDITAR_ITEM_PRECIO

    return InvoiceStates.CONFIRMAR_DATOS


async def _delete_item(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    item_index: int
) -> int:
    """Elimina un item de la lista."""
    query = update.callback_query
    items = context.user_data.get('items', [])

    if item_index < len(items):
        deleted = items.pop(item_index)
        context.user_data['items'] = items

        # Recalcular totales
        total = sum(i.get('precio', 0) * i.get('cantidad', 1) for i in items)
        context.user_data['subtotal'] = total
        context.user_data['total'] = total

        nombre = deleted.get('nombre', deleted.get('descripcion', 'Item'))
        await query.answer(f"Item eliminado: {nombre}")

    return await _show_items_menu(update, context)


async def _start_add_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el proceso de agregar un nuevo item."""
    query = update.callback_query

    await query.edit_message_text(
        "AGREGAR ITEM\n"
        "=========================\n\n"
        "Escribe el nombre del producto:"
    )

    context.user_data['adding_new_item'] = True
    context.user_data['new_item'] = {}

    return InvoiceStates.AGREGAR_ITEM


# ============================================================================
# HANDLERS DE EDICIÓN DE CLIENTE
# ============================================================================

async def _show_cliente_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muestra menú de edición de datos del cliente."""
    query = update.callback_query
    cliente = context.user_data.get('cliente_detectado', {})

    mensaje = (
        "EDITAR CLIENTE\n"
        "=========================\n\n"
        f"Nombre: {cliente.get('nombre', 'No detectado')}\n"
        f"Teléfono: {cliente.get('telefono', 'No detectado')}\n"
        f"Dirección: {cliente.get('direccion', 'No detectado')}\n"
        f"Ciudad: {cliente.get('ciudad', 'No detectado')}\n"
        f"Email: {cliente.get('email', 'No detectado')}\n\n"
        "Selecciona el campo a editar:"
    )

    await query.edit_message_text(
        mensaje,
        reply_markup=get_cliente_edit_keyboard()
    )

    return InvoiceStates.CONFIRMAR_DATOS


async def _start_cliente_field_edit(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    field: str
) -> int:
    """Inicia edición de un campo del cliente."""
    query = update.callback_query
    cliente = context.user_data.get('cliente_detectado', {})

    current_value = cliente.get(field, 'No detectado')
    context.user_data['editing_cliente_field'] = field

    prompts = {
        'nombre': f"Nombre actual: {current_value}\n\nEscribe el nuevo nombre:",
        'telefono': f"Teléfono actual: {current_value}\n\nEscribe el nuevo teléfono:",
        'direccion': f"Dirección actual: {current_value}\n\nEscribe la nueva dirección:",
        'ciudad': f"Ciudad actual: {current_value}\n\nEscribe la nueva ciudad:",
        'email': f"Email actual: {current_value}\n\nEscribe el nuevo email:"
    }

    await query.edit_message_text(prompts.get(field, "Escribe el nuevo valor:"))

    # Retornar estado dedicado para recibir texto de edición de cliente
    return InvoiceStates.EDITAR_CLIENTE_CAMPO


# ============================================================================
# NAVEGACIÓN
# ============================================================================

async def _show_confirm_screen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Vuelve a mostrar la pantalla de confirmación."""
    query = update.callback_query
    items = context.user_data.get('items', [])
    cliente = context.user_data.get('cliente_detectado', {})

    # Reconstruir mensaje de confirmación
    items_text = ""
    total = 0
    for i, item in enumerate(items, 1):
        precio = item.get('precio', 0)
        cantidad = item.get('cantidad', 1)
        subtotal = precio * cantidad
        total += subtotal

        nombre = item.get('nombre', item.get('descripcion', 'Producto'))
        descripcion = item.get('descripcion', '')

        items_text += f"{i}. {nombre}\n"
        if descripcion and descripcion != nombre:
            items_text += f"   {descripcion}\n"
        items_text += f"   Cantidad: {cantidad} x {format_currency(precio)} = {format_currency(subtotal)}\n\n"

    context.user_data['subtotal'] = total
    context.user_data['total'] = total

    mensaje = (
        "ITEMS DETECTADOS\n"
        "=========================\n\n"
        f"{items_text}"
        f"SUBTOTAL: {format_currency(total)}\n"
    )

    # Mostrar cliente si existe
    if cliente and any([cliente.get('nombre'), cliente.get('telefono')]):
        mensaje += "\nCLIENTE DETECTADO\n"
        mensaje += "-------------------------\n"
        if cliente.get('nombre'):
            mensaje += f"Nombre: {cliente.get('nombre')}\n"
        if cliente.get('telefono'):
            mensaje += f"Teléfono: {cliente.get('telefono')}\n"
        if cliente.get('direccion'):
            mensaje += f"Dirección: {cliente.get('direccion')}\n"
        if cliente.get('ciudad'):
            mensaje += f"Ciudad: {cliente.get('ciudad')}\n"
        if cliente.get('email'):
            mensaje += f"Email: {cliente.get('email')}\n"

    mensaje += "\nSelecciona una opción:"

    has_cliente = bool(cliente and cliente.get('nombre'))

    await query.edit_message_text(
        mensaje,
        reply_markup=get_confirm_inline_keyboard(has_cliente)
    )

    return InvoiceStates.CONFIRMAR_DATOS