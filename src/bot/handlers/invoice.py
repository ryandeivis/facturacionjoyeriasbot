"""
Handlers de Facturación

Maneja el flujo de creación de facturas con input de texto, voz o foto.
Integra con n8n para extracción de datos con IA y generación de PDF.

Flujo:
1. Usuario selecciona tipo de input (texto/voz/foto)
2. Bot envía input a n8n para extracción con IA
3. n8n retorna items extraídos
4. Usuario confirma/edita items
5. Usuario ingresa datos del cliente
6. Bot envía datos a n8n para generar PDF
7. n8n retorna PDF y bot lo envía al usuario
"""

import time
import base64
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)
from pathlib import Path
from datetime import datetime, timedelta

from src.utils.logger import get_logger, audit_logger, bind_context
from src.utils.rate_limiter import check_invoice_rate
from src.utils.validators import (
    IdentityValidator,
    ContactValidator,
    ProductValidator,
    ValidationLimits
)
from src.utils.errors import (
    handle_errors,
    ExternalAPIError,
    DatabaseError,
    BusinessError
)
from src.database.connection import get_db, get_db_context
from src.database.queries.invoice_queries import create_invoice
from src.services.n8n_service import n8n_service
from src.services.text_parser import text_parser
from src.services.html_generator import html_generator
from src.bot.handlers.shared import (
    AuthStates,
    InvoiceStates,
    get_menu_keyboard,
    get_input_type_keyboard,
    get_confirm_keyboard,
    get_confirm_inline_keyboard,
    get_generate_keyboard,
    get_metodo_pago_keyboard,
    get_bancos_keyboard,
    limpiar_datos_factura,
    is_authenticated,
    format_currency,
    format_title_case,
    MENSAJES,
    GUIA_INPUT_BASE,
    GUIA_TEXTO,
    GUIA_VOZ,
    GUIA_FOTO
)
from src.bot.handlers.formatters import (
    format_items_list,
    format_cliente_info,
    format_metodo_pago,
    calculate_items_total
)
from config.constants import InvoiceStatus, InputType
from config.settings import settings
from src.metrics.tracker import get_metrics_tracker

logger = get_logger(__name__)
metrics = get_metrics_tracker()

# Estados de la conversación (aliases para compatibilidad)
SELECCIONAR_INPUT = InvoiceStates.SELECCIONAR_INPUT
RECIBIR_INPUT = InvoiceStates.RECIBIR_INPUT
CONFIRMAR_DATOS = InvoiceStates.CONFIRMAR_DATOS
EDITAR_ITEMS = InvoiceStates.EDITAR_ITEMS
DATOS_CLIENTE = InvoiceStates.DATOS_CLIENTE
CLIENTE_TELEFONO = InvoiceStates.CLIENTE_TELEFONO
CLIENTE_CEDULA = InvoiceStates.CLIENTE_CEDULA
GENERAR_FACTURA = InvoiceStates.GENERAR_FACTURA
# Nuevos estados
CLIENTE_DIRECCION = InvoiceStates.CLIENTE_DIRECCION
CLIENTE_CIUDAD = InvoiceStates.CLIENTE_CIUDAD
CLIENTE_EMAIL = InvoiceStates.CLIENTE_EMAIL
# Estados para edición granular
EDITAR_SELECCIONAR_ITEM = InvoiceStates.EDITAR_SELECCIONAR_ITEM
EDITAR_ITEM_CAMPO = InvoiceStates.EDITAR_ITEM_CAMPO
EDITAR_ITEM_NOMBRE = InvoiceStates.EDITAR_ITEM_NOMBRE
EDITAR_ITEM_CANTIDAD = InvoiceStates.EDITAR_ITEM_CANTIDAD
EDITAR_ITEM_PRECIO = InvoiceStates.EDITAR_ITEM_PRECIO
AGREGAR_ITEM = InvoiceStates.AGREGAR_ITEM
AGREGAR_ITEM_CANTIDAD = InvoiceStates.AGREGAR_ITEM_CANTIDAD
AGREGAR_ITEM_PRECIO = InvoiceStates.AGREGAR_ITEM_PRECIO
# Estados de método de pago
METODO_PAGO = InvoiceStates.METODO_PAGO
BANCO_ORIGEN = InvoiceStates.BANCO_ORIGEN
BANCO_DESTINO = InvoiceStates.BANCO_DESTINO
# Estado de edición de descripción
EDITAR_ITEM_DESCRIPCION = InvoiceStates.EDITAR_ITEM_DESCRIPCION


# ============================================================================
# FUNCIONES HELPER PARA PROCESAR INPUT (Clean Code - SRP)
# ============================================================================

async def _procesar_input_texto(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> tuple:
    """
    Procesa input de texto usando parser local.

    Returns:
        Tuple[response, error_msg]: response del parser o None con mensaje de error
    """
    text = update.message.text
    if not text:
        return None, "No se recibió texto"

    context.user_data['input_raw'] = text

    # Track mensaje de texto
    org_id = context.user_data.get('organization_id')
    user_id = update.effective_user.id
    await metrics.track_bot_message(
        organization_id=str(org_id) if org_id else None,
        user_id=user_id,
        message_type="text_invoice"
    )

    # Usar parser local para texto (más rápido y sin costo)
    response = text_parser.parse(text)
    logger.info(f"Texto parseado localmente: {response.success}, {len(response.items)} items")

    return response, None


async def _procesar_input_voz(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> tuple:
    """
    Procesa input de voz: descarga audio y envía a n8n.

    Returns:
        Tuple[response, error_msg]: response de n8n o None con mensaje de error
    """
    voice = update.message.voice
    if not voice:
        return None, "No se recibió audio"

    cedula = context.user_data.get('cedula')

    # Crear directorio uploads si no existe
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(exist_ok=True)

    # Descargar archivo
    file = await context.bot.get_file(voice.file_id)
    audio_path = upload_dir / f"{voice.file_id}.ogg"
    await file.download_to_drive(str(audio_path))

    context.user_data['input_raw'] = str(audio_path)

    # Track y procesar voz con métricas
    org_id = context.user_data.get('organization_id')
    user_id = update.effective_user.id
    start_time = time.time()

    response = await n8n_service.send_voice_input(str(audio_path), cedula)

    duration_ms = (time.time() - start_time) * 1000
    await metrics.track_bot_voice(
        organization_id=str(org_id) if org_id else None,
        user_id=user_id,
        success=response.success if response else False,
        duration_ms=duration_ms
    )

    # Track extracción IA
    if response:
        await metrics.track_ai_extraction(
            organization_id=str(org_id) if org_id else "unknown",
            user_id=user_id,
            extraction_type="voice",
            success=response.success,
            duration_ms=duration_ms,
            items_extracted=len(response.items) if response.items else 0
        )

    return response, None


async def _procesar_input_foto(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> tuple:
    """
    Procesa input de foto: descarga imagen y envía a n8n.

    Returns:
        Tuple[response, error_msg]: response de n8n o None con mensaje de error
    """
    photos = update.message.photo
    if not photos:
        return None, "No se recibió foto"

    cedula = context.user_data.get('cedula')
    photo = photos[-1]  # La última es la más grande

    # Crear directorio uploads si no existe
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(exist_ok=True)

    # Descargar archivo
    file = await context.bot.get_file(photo.file_id)
    photo_path = upload_dir / f"{photo.file_id}.jpg"
    await file.download_to_drive(str(photo_path))

    context.user_data['input_raw'] = str(photo_path)

    # Track y procesar foto con métricas
    org_id = context.user_data.get('organization_id')
    user_id = update.effective_user.id
    start_time = time.time()

    response = await n8n_service.send_photo_input(str(photo_path), cedula)

    duration_ms = (time.time() - start_time) * 1000
    await metrics.track_bot_photo(
        organization_id=str(org_id) if org_id else None,
        user_id=user_id,
        success=response.success if response else False,
        duration_ms=duration_ms
    )

    # Track extracción IA
    if response:
        await metrics.track_ai_extraction(
            organization_id=str(org_id) if org_id else "unknown",
            user_id=user_id,
            extraction_type="photo",
            success=response.success,
            duration_ms=duration_ms,
            items_extracted=len(response.items) if response.items else 0
        )

    return response, None


def _formatear_respuesta_items(response, context: ContextTypes.DEFAULT_TYPE) -> str:
    """
    Formatea la respuesta con items extraídos para mostrar al usuario.

    Args:
        response: Respuesta del parser o n8n
        context: Contexto de la conversación

    Returns:
        Mensaje formateado para enviar al usuario
    """
    # Formatear items con Title Case
    formatted_items = []
    for item in response.items:
        formatted_item = item.copy()
        if formatted_item.get('nombre'):
            formatted_item['nombre'] = format_title_case(formatted_item['nombre'])
        if formatted_item.get('descripcion'):
            formatted_item['descripcion'] = format_title_case(formatted_item['descripcion'])
        formatted_items.append(formatted_item)

    # Formatear cliente con Title Case
    formatted_cliente = None
    if response.cliente:
        formatted_cliente = response.cliente.copy()
        if formatted_cliente.get('nombre'):
            formatted_cliente['nombre'] = format_title_case(formatted_cliente['nombre'])
        if formatted_cliente.get('ciudad'):
            formatted_cliente['ciudad'] = format_title_case(formatted_cliente['ciudad'])

    # Guardar respuesta completa
    context.user_data['n8n_response'] = {
        'items': formatted_items,
        'cliente': formatted_cliente,
        'vendedor': getattr(response, 'vendedor', None),
        'factura': response.factura,
        'totales': response.totales,
        'transcripcion': response.transcripcion,
        'input_type': response.input_type
    }
    context.user_data['items'] = formatted_items
    context.user_data['transcripcion'] = response.transcripcion

    # Guardar cliente detectado si existe
    if formatted_cliente:
        context.user_data['cliente_detectado'] = formatted_cliente

    # Calcular total usando format_items_list
    total = sum(
        item.get('cantidad', 1) * item.get('precio', 0)
        for item in formatted_items
    )
    context.user_data['subtotal'] = total
    context.user_data['total'] = total

    # Construir mensaje usando formatters
    items_text = format_items_list(formatted_items)

    mensaje = (
        "📦 PRODUCTOS DETECTADOS\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{items_text}\n"
        f"💰 Subtotal: {format_currency(total)}\n"
    )

    # Mostrar cliente detectado si existe
    if response.cliente:
        cliente = response.cliente
        has_cliente_data = any([
            cliente.get('nombre'),
            cliente.get('telefono'),
            cliente.get('direccion')
        ])
        if has_cliente_data:
            mensaje += "\n👤 CLIENTE DETECTADO\n"
            mensaje += "━━━━━━━━━━━━━━━━━━━━\n"
            if cliente.get('nombre'):
                mensaje += f"   Nombre: {cliente.get('nombre')}\n"
            if cliente.get('telefono'):
                mensaje += f"   Tel: {cliente.get('telefono')}\n"
            if cliente.get('direccion'):
                mensaje += f"   Dir: {cliente.get('direccion')}\n"
            if cliente.get('ciudad'):
                mensaje += f"   Ciudad: {cliente.get('ciudad')}\n"
            if cliente.get('email'):
                mensaje += f"   Email: {cliente.get('email')}\n"

    if response.transcripcion:
        mensaje += f"\n🎤 Transcripción: {response.transcripcion[:100]}...\n"

    mensaje += "\n¿Qué deseas hacer?"

    return mensaje, formatted_items


# ============================================================================
# HANDLERS PRINCIPALES
# ============================================================================

async def iniciar_nueva_factura(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el proceso de crear una nueva factura"""

    if not is_authenticated(context):
        await update.message.reply_text(MENSAJES['no_autenticado'])
        return ConversationHandler.END

    # Asegurar contexto de logging está establecido
    user_id = context.user_data.get('user_id')
    org_id = context.user_data.get('organization_id')
    if user_id and org_id:
        bind_context(org_id=str(org_id), user_id=str(user_id))

    logger.info("Iniciando flujo de nueva factura")

    await update.message.reply_text(
        "🧾 NUEVA FACTURA\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "¿Cómo deseas ingresar los productos?\n\n"
        "⌨️ Texto · Escribe los productos\n"
        "🎙️ Voz · Dicta los productos\n"
        "📸 Foto · Captura lista o ticket",
        reply_markup=get_input_type_keyboard()
    )

    return SELECCIONAR_INPUT


async def seleccionar_tipo_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Procesa la selección del tipo de input"""
    opcion = update.message.text.lower()

    if 'cancelar' in opcion:
        rol = context.user_data.get('rol')
        await update.message.reply_text(
            MENSAJES['operacion_cancelada'],
            reply_markup=get_menu_keyboard(rol)
        )
        return AuthStates.MENU_PRINCIPAL

    if 'texto' in opcion:
        context.user_data['input_type'] = InputType.TEXTO.value
        # Enviar guía completa antes de solicitar input
        await update.message.reply_text(
            GUIA_INPUT_BASE,
            reply_markup=ReplyKeyboardRemove()
        )
        await update.message.reply_text(GUIA_TEXTO)
        return RECIBIR_INPUT

    elif 'voz' in opcion:
        context.user_data['input_type'] = InputType.VOZ.value
        # Enviar guía completa antes de solicitar input
        await update.message.reply_text(
            GUIA_INPUT_BASE,
            reply_markup=ReplyKeyboardRemove()
        )
        await update.message.reply_text(GUIA_VOZ)
        return RECIBIR_INPUT

    elif 'foto' in opcion:
        context.user_data['input_type'] = InputType.FOTO.value
        # Enviar guía completa antes de solicitar input
        await update.message.reply_text(
            GUIA_INPUT_BASE,
            reply_markup=ReplyKeyboardRemove()
        )
        await update.message.reply_text(GUIA_FOTO)
        return RECIBIR_INPUT

    elif 'test' in opcion or 'prueba' in opcion:
        # Ejecutar test PDF con datos de prueba
        await ejecutar_test_pdf(update, context)
        return AuthStates.MENU_PRINCIPAL

    # Opción no reconocida
    await update.message.reply_text(
        "❓ Opción no reconocida\n\n"
        "Por favor, selecciona una opción del menú:",
        reply_markup=get_input_type_keyboard()
    )
    return SELECCIONAR_INPUT


async def recibir_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Recibe el input del usuario (texto, voz o foto).

    Refactorizado para usar funciones helper separadas (Clean Code - SRP).
    Cada tipo de input tiene su propia función de procesamiento.
    """
    input_type = context.user_data.get('input_type')

    # Mostrar mensaje de procesando
    processing_msg = await update.message.reply_text(
        "⏳ Procesando...\n\n"
        "Por favor, espera un momento."
    )

    try:
        response = None
        error_msg = None

        # Delegar a función específica según tipo de input
        if input_type == InputType.TEXTO.value:
            response, error_msg = await _procesar_input_texto(update, context)
            if error_msg:
                await processing_msg.edit_text(
                    f"⚠ {error_msg}\n\nPor favor, escribe los productos:"
                )
                return RECIBIR_INPUT

        elif input_type == InputType.VOZ.value:
            response, error_msg = await _procesar_input_voz(update, context)
            if error_msg:
                await processing_msg.edit_text(
                    f"⚠ {error_msg}\n\nPor favor, envía un mensaje de voz:"
                )
                return RECIBIR_INPUT

        elif input_type == InputType.FOTO.value:
            response, error_msg = await _procesar_input_foto(update, context)
            if error_msg:
                await processing_msg.edit_text(
                    f"⚠ {error_msg}\n\nPor favor, envía una imagen:"
                )
                return RECIBIR_INPUT

        else:
            await processing_msg.edit_text(
                "⚠ Tipo de entrada no reconocido\n\n"
                "Por favor, intenta de nuevo."
            )
            return SELECCIONAR_INPUT

        # Procesar respuesta exitosa
        if response and response.success and response.items:
            mensaje, formatted_items = _formatear_respuesta_items(response, context)

            await processing_msg.edit_text(mensaje)

            # Usar InlineKeyboard para edición granular
            has_cliente = bool(response.cliente and response.cliente.get('nombre'))
            await update.message.reply_text(
                "Selecciona una opción:",
                reply_markup=get_confirm_inline_keyboard(has_cliente)
            )

            return CONFIRMAR_DATOS

        else:
            # Fallback: pedir ingreso manual
            error_msg = response.error if response else "Error de conexión"

            await processing_msg.edit_text(
                f"⚠ No se pudo procesar automáticamente\n"
                f"   Razón: {error_msg}\n\n"
                "📝 Ingresa los productos manualmente:\n\n"
                "Formato: nombre - $precio\n\n"
                "Ejemplo:\n"
                "Anillo oro 18k - $500000\n"
                "Cadena plata - $150000"
            )

            context.user_data['input_type'] = InputType.TEXTO.value
            context.user_data['manual_mode'] = True
            return RECIBIR_INPUT

    except Exception as e:
        # Loggear con contexto completo
        from src.utils.errors import ExternalAPIError
        api_error = ExternalAPIError(
            message=f"Error procesando input: {str(e)}",
            service="n8n",
            original_error=e
        )
        logger.error(
            f"[{api_error.correlation_id[:8]}] {api_error.message}",
            exc_info=True
        )

        # Track error
        org_id = context.user_data.get('organization_id')
        user_id = update.effective_user.id if update.effective_user else None
        await metrics.track_bot_error(
            organization_id=str(org_id) if org_id else None,
            user_id=user_id,
            error_type="input_processing",
            error_message=str(e)
        )

        await processing_msg.edit_text(
            "⚠ Error al procesar\n\n"
            "El servicio no está disponible.\n"
            "Intenta de nuevo o ingresa manualmente.\n\n"
            f"📋 Ref: {api_error.correlation_id[:8]}"
        )
        return RECIBIR_INPUT


async def confirmar_datos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Confirma los datos extraídos"""
    opcion = update.message.text.lower()

    if 'cancelar' in opcion:
        rol = context.user_data.get('rol')
        await update.message.reply_text(
            MENSAJES['operacion_cancelada'],
            reply_markup=get_menu_keyboard(rol)
        )
        limpiar_datos_factura(context)
        return AuthStates.MENU_PRINCIPAL

    if 'si' in opcion or 'continuar' in opcion:
        await update.message.reply_text(
            "👤 DATOS DEL CLIENTE\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Ingresa el nombre del cliente:",
            reply_markup=ReplyKeyboardRemove()
        )
        return DATOS_CLIENTE

    if 'editar' in opcion or 'manual' in opcion:
        await update.message.reply_text(
            "✏️ EDITAR PRODUCTOS\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Ingresa los productos en el formato:\n"
            "nombre - $precio\n\n"
            "Un producto por línea.\n"
            "Escribe 'listo' cuando termines.",
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data['items'] = []
        return EDITAR_ITEMS

    await update.message.reply_text(
        "❓ Opción no reconocida\n\n"
        "Por favor, selecciona una opción:",
        reply_markup=get_confirm_keyboard()
    )
    return CONFIRMAR_DATOS


async def editar_items(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Permite editar items manualmente"""
    text = update.message.text.strip()

    if text.lower() == 'listo':
        items = context.user_data.get('items', [])
        if not items:
            await update.message.reply_text(
                "⚠ Lista vacía\n\n"
                "Ingresa al menos un producto:"
            )
            return EDITAR_ITEMS

        # Calcular total usando formatter centralizado
        total = calculate_items_total(items)
        context.user_data['subtotal'] = total
        context.user_data['total'] = total

        await update.message.reply_text(
            "👤 DATOS DEL CLIENTE\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Ingresa el nombre del cliente:",
            reply_markup=ReplyKeyboardRemove()
        )
        return DATOS_CLIENTE

    # Parsear item: "descripción - $precio"
    try:
        if ' - $' in text:
            parts = text.rsplit(' - $', 1)
            descripcion = parts[0].strip()
            precio = float(parts[1].replace(',', '').replace('.', ''))
        elif ' - ' in text:
            parts = text.rsplit(' - ', 1)
            descripcion = parts[0].strip()
            precio = float(parts[1].replace('$', '').replace(',', '').replace('.', ''))
        else:
            await update.message.reply_text(
                "⚠ Formato incorrecto\n\n"
                "Usa: nombre - $precio\n"
                "Ejemplo: Anillo oro 18k - $500000"
            )
            return EDITAR_ITEMS

        # Agregar item
        items = context.user_data.get('items', [])
        items.append({
            'descripcion': descripcion,
            'cantidad': 1,
            'precio': precio
        })
        context.user_data['items'] = items

        await update.message.reply_text(
            f"✅ Agregado: {descripcion}\n"
            f"   Precio: {format_currency(precio)}\n\n"
            f"📦 Total productos: {len(items)}\n\n"
            "Ingresa otro o escribe 'listo':"
        )
        return EDITAR_ITEMS

    except (ValueError, IndexError):
        await update.message.reply_text(
            "⚠ Precio no válido\n\n"
            "Usa: nombre - $precio\n"
            "Ejemplo: Anillo oro 18k - $500000"
        )
        return EDITAR_ITEMS


async def datos_cliente(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe el nombre del cliente"""
    nombre_raw = update.message.text.strip()

    # Validar nombre con validador centralizado
    result = IdentityValidator.validate_nombre_persona(nombre_raw)
    if not result.valid:
        await update.message.reply_text(
            f"⚠ Nombre inválido\n\n"
            f"{result.error}\n"
            "Ingresa el nombre del cliente:"
        )
        return DATOS_CLIENTE

    context.user_data['cliente_nombre'] = result.sanitized

    await update.message.reply_text(
        f"👤 Cliente: {result.sanitized}\n\n"
        "📍 Dirección (calle y número):\n"
        "   Escribe 'omitir' si no aplica"
    )
    return CLIENTE_DIRECCION


async def cliente_direccion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe la dirección del cliente"""
    direccion = update.message.text.strip()

    if direccion.lower() != 'omitir':
        context.user_data['cliente_direccion'] = direccion

    await update.message.reply_text(
        "🏙️ Ciudad del cliente:\n"
        "   Escribe 'omitir' si no aplica"
    )
    return CLIENTE_CIUDAD


async def cliente_ciudad(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe la ciudad del cliente"""
    ciudad = update.message.text.strip()

    if ciudad.lower() != 'omitir':
        context.user_data['cliente_ciudad'] = ciudad

    await update.message.reply_text(
        "📧 Email del cliente:\n"
        "   Escribe 'omitir' si no aplica"
    )
    return CLIENTE_EMAIL


async def cliente_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe el email del cliente y pide teléfono"""
    email = update.message.text.strip()

    if email.lower() != 'omitir':
        context.user_data['cliente_email'] = email

    await update.message.reply_text(
        "📱 Teléfono del cliente:\n"
        "   Escribe 'omitir' si no aplica"
    )
    return CLIENTE_TELEFONO


async def cliente_telefono(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe el teléfono del cliente y pide cédula"""
    telefono = update.message.text.strip()

    if telefono.lower() != 'omitir':
        # Validar teléfono básico
        telefono_limpio = ''.join(c for c in telefono if c.isdigit())
        if telefono_limpio:
            context.user_data['cliente_telefono'] = telefono

    await update.message.reply_text(
        "📋 Cédula/NIT del cliente:\n"
        "   Escribe 'omitir' si no aplica"
    )
    return CLIENTE_CEDULA


async def cliente_cedula(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe la cédula del cliente y pasa a método de pago"""
    cedula = update.message.text.strip()

    if cedula.lower() != 'omitir':
        # Validar cédula básica
        cedula_limpia = ''.join(c for c in cedula if c.isdigit() or c == '-')
        if cedula_limpia:
            context.user_data['cliente_cedula'] = cedula

    # Pasar a método de pago
    await update.message.reply_text(
        "💳 MÉTODO DE PAGO\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "¿Cómo pagó el cliente?",
        reply_markup=get_metodo_pago_keyboard()
    )
    return METODO_PAGO


async def metodo_pago(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe el método de pago seleccionado"""
    texto = update.message.text.strip().lower()

    if 'omitir' in texto:
        # Continuar sin método de pago
        await _mostrar_resumen_factura(update, context)
        return GENERAR_FACTURA

    if 'efectivo' in texto:
        context.user_data['metodo_pago'] = 'efectivo'
        await _mostrar_resumen_factura(update, context)
        return GENERAR_FACTURA

    elif 'tarjeta' in texto:
        context.user_data['metodo_pago'] = 'tarjeta'
        await _mostrar_resumen_factura(update, context)
        return GENERAR_FACTURA

    elif 'transferencia' in texto:
        context.user_data['metodo_pago'] = 'transferencia'
        await update.message.reply_text(
            "🏦 CUENTA DESTINO\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "¿A qué cuenta llegó el pago?",
            reply_markup=get_bancos_keyboard()
        )
        return BANCO_DESTINO

    else:
        await update.message.reply_text(
            "❓ Opción no reconocida.\n\n"
            "Selecciona un método de pago:",
            reply_markup=get_metodo_pago_keyboard()
        )
        return METODO_PAGO


async def banco_origen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe el banco de origen para transferencias"""
    texto = update.message.text.strip()

    if 'omitir' in texto.lower():
        await _mostrar_resumen_factura(update, context)
        return GENERAR_FACTURA

    context.user_data['banco_origen'] = texto

    await update.message.reply_text(
        "🏦 BANCO DESTINO\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "¿A qué banco se transfirió?",
        reply_markup=get_bancos_keyboard()
    )
    return BANCO_DESTINO


async def banco_destino(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe el banco destino y muestra resumen"""
    texto = update.message.text.strip()

    if 'omitir' not in texto.lower():
        context.user_data['banco_destino'] = texto

    # Mostrar resumen con todos los datos
    await _mostrar_resumen_factura(update, context)
    return GENERAR_FACTURA


async def _mostrar_resumen_factura(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra el resumen de la factura antes de confirmar"""
    items = context.user_data.get('items', [])
    subtotal = context.user_data.get('subtotal', 0)
    total = context.user_data.get('total', 0)

    # Usar formatters centralizados
    items_text = format_items_list(items)
    pago_text = format_metodo_pago(context.user_data)

    mensaje = (
        "📋 RESUMEN DE FACTURA\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "👤 CLIENTE\n"
        f"   Nombre: {context.user_data.get('cliente_nombre', 'N/A')}\n"
        f"   Cédula/NIT: {context.user_data.get('cliente_cedula', 'N/A')}\n"
        f"   Teléfono: {context.user_data.get('cliente_telefono', 'N/A')}\n"
        f"   Email: {context.user_data.get('cliente_email', 'N/A')}\n"
        f"   Dirección: {context.user_data.get('cliente_direccion', 'N/A')}\n"
        f"   Ciudad: {context.user_data.get('cliente_ciudad', 'N/A')}\n"
    )

    if pago_text:
        mensaje += f"\n💳 MÉTODO DE PAGO\n   {pago_text}\n"

    mensaje += (
        f"\n📦 PRODUCTOS\n{items_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Subtotal: {format_currency(subtotal)}\n"
        f"💵 TOTAL: {format_currency(total)}\n\n"
        "¿Confirmar y generar factura?"
    )

    await update.message.reply_text(
        mensaje,
        reply_markup=get_generate_keyboard()
    )


async def generar_factura(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Genera la factura final.

    1. Guarda factura en BD
    2. Solicita PDF a n8n
    3. Envía PDF al usuario
    """
    opcion = update.message.text.lower()

    if 'cancelar' in opcion:
        rol = context.user_data.get('rol')
        await update.message.reply_text(
            MENSAJES['operacion_cancelada'],
            reply_markup=get_menu_keyboard(rol)
        )
        limpiar_datos_factura(context)
        return AuthStates.MENU_PRINCIPAL

    if 'confirmar' in opcion or 'generar' in opcion:
        # Rate limit: protección contra creación excesiva de facturas
        user_id = context.user_data.get('user_id')
        org_id = context.user_data.get('organization_id')
        allowed, rate_message = check_invoice_rate(user_id, org_id)
        if not allowed:
            await update.message.reply_text(rate_message)
            return GENERAR_FACTURA

        # Mostrar mensaje de procesando
        processing_msg = await update.message.reply_text(
            "⏳ Generando factura...\n\n"
            "Por favor, espera un momento."
        )

        try:
            org_id = context.user_data.get('organization_id')

            # Calcular impuesto usando tasa configurada
            subtotal = context.user_data.get('subtotal', 0)
            impuesto = round(subtotal * settings.TAX_RATE)
            total = subtotal + impuesto

            # Normalizar items antes de guardar (BUG-001 fix)
            items_raw = context.user_data.get('items', [])
            items_normalized = []
            for item in items_raw:
                cantidad = item.get('cantidad', 1)
                precio = item.get('precio', item.get('precio_unitario', 0))
                items_normalized.append({
                    "nombre": item.get('nombre', item.get('descripcion', 'Producto')),
                    "descripcion": item.get('descripcion', ''),
                    "cantidad": cantidad,
                    "precio": precio,
                    "subtotal": cantidad * precio
                })

            # Preparar datos de factura
            invoice_data = {
                "organization_id": org_id,
                "cliente_nombre": context.user_data.get('cliente_nombre'),
                "cliente_direccion": context.user_data.get('cliente_direccion'),
                "cliente_ciudad": context.user_data.get('cliente_ciudad'),
                "cliente_email": context.user_data.get('cliente_email'),
                "cliente_telefono": context.user_data.get('cliente_telefono'),
                "cliente_cedula": context.user_data.get('cliente_cedula'),
                "items": items_normalized,
                "subtotal": subtotal,
                "impuesto": impuesto,
                "total": total,
                "estado": InvoiceStatus.PENDIENTE.value,
                "vendedor_id": context.user_data.get('user_id'),
                "input_type": context.user_data.get('input_type'),
                "input_raw": context.user_data.get('input_raw'),
                "n8n_processed": True,
                # Método de pago
                "metodo_pago": context.user_data.get('metodo_pago'),
                "banco_origen": context.user_data.get('banco_origen'),
                "banco_destino": context.user_data.get('banco_destino'),
                "referencia_pago": context.user_data.get('referencia_pago'),
            }

            # Crear factura en BD usando context manager (evita connection leak)
            # IMPORTANTE: Extraer TODOS los datos dentro del context manager
            # para evitar DetachedInstanceError al acceder después de cerrar sesión
            invoice_extracted = None
            with get_db_context() as db:
                invoice = create_invoice(db, invoice_data)
                if invoice:
                    # Extraer datos mientras la sesión está activa
                    invoice_extracted = {
                        'id': invoice.id,
                        'numero_factura': invoice.numero_factura,
                        'organization_id': str(invoice.organization_id),
                        'cliente_nombre': invoice.cliente_nombre,
                        'cliente_telefono': invoice.cliente_telefono,
                        'cliente_cedula': invoice.cliente_cedula,
                        'cliente_direccion': invoice.cliente_direccion,
                        'cliente_ciudad': invoice.cliente_ciudad,
                        'cliente_email': invoice.cliente_email,
                        'items': [
                            {
                                'nombre': item.get('nombre', item.get('descripcion', 'Producto')),
                                'descripcion': item.get('descripcion', ''),
                                'cantidad': item.get('cantidad', 1),
                                'precio': float(item.get('precio', item.get('precio_unitario', 0))),
                                'subtotal': float(item.get('subtotal', 0))
                            } for item in invoice.items
                        ],
                        'items_count': len(invoice.items),
                        'subtotal': float(invoice.subtotal),
                        'descuento': float(invoice.descuento) if invoice.descuento else 0,
                        'impuesto': float(invoice.impuesto),
                        'total': float(invoice.total),
                        'metodo_pago': invoice.metodo_pago,
                        'banco_destino': invoice.banco_destino,
                    }

            if invoice_extracted:
                # Audit: factura creada exitosamente
                audit_logger.create(
                    entity_type="invoice",
                    entity_id=str(invoice_extracted['id']),
                    new_values={
                        "numero_factura": invoice_extracted['numero_factura'],
                        "cliente": invoice_extracted['cliente_nombre'],
                        "total": invoice_extracted['total'],
                        "items_count": invoice_extracted['items_count']
                    }
                )
                logger.info(f"Factura creada: {invoice_extracted['numero_factura']}")

                # Métricas de negocio: factura creada
                await metrics.track_invoice_created(
                    organization_id=invoice_extracted['organization_id'],
                    amount=invoice_extracted['total'],
                    user_id=user_id,
                    metadata={
                        "numero_factura": invoice_extracted['numero_factura'],
                        "items_count": invoice_extracted['items_count'],
                        "input_type": context.user_data.get('input_type'),
                    }
                )

                # Actualizar mensaje
                await processing_msg.edit_text(
                    f"✅ Factura {invoice_extracted['numero_factura']} guardada\n\n"
                    "📄 Generando PDF..."
                )

                # Generar HTML local y solicitar PDF a n8n
                html_content, pdf_response = await _generar_pdf_factura(invoice_extracted, context)

                rol = context.user_data.get('rol')

                if html_content or (pdf_response and pdf_response.success):
                    # Enviar HTML y PDF al usuario
                    await _enviar_pdf_usuario(update, context, invoice_extracted, html_content, pdf_response)

                    await update.message.reply_text(
                        "🎉 FACTURA GENERADA\n"
                        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"📄 No: {invoice_extracted['numero_factura']}\n"
                        f"👤 {invoice_extracted['cliente_nombre']}\n\n"
                        f"   Subtotal: {format_currency(subtotal)}\n"
                        f"   IVA ({int(settings.TAX_RATE * 100)}%): {format_currency(impuesto)}\n"
                        f"💵 Total: {format_currency(total)}\n\n"
                        f"📌 Estado: Pendiente\n\n"
                        "✅ PDF enviado correctamente",
                        reply_markup=get_menu_keyboard(rol)
                    )
                else:
                    # Factura guardada pero sin PDF
                    await update.message.reply_text(
                        "🎉 FACTURA GENERADA\n"
                        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"📄 No: {invoice_extracted['numero_factura']}\n"
                        f"👤 {invoice_extracted['cliente_nombre']}\n"
                        f"💵 Total: {format_currency(total)}\n\n"
                        f"📌 Estado: Pendiente\n\n"
                        "⚠ PDF no disponible temporalmente",
                        reply_markup=get_menu_keyboard(rol)
                    )

                # Limpiar datos temporales
                limpiar_datos_factura(context)

                return AuthStates.MENU_PRINCIPAL

            else:
                await processing_msg.edit_text(
                    "⚠ Error al guardar la factura\n\n"
                    "Por favor, intenta de nuevo."
                )
                return GENERAR_FACTURA

        except Exception as e:
            # Loggear con contexto
            db_error = DatabaseError(
                message=f"Error generando factura: {str(e)}",
                original_error=e
            )
            logger.error(
                f"[{db_error.correlation_id[:8]}] {db_error.message}",
                exc_info=True
            )
            await processing_msg.edit_text(
                "⚠ Error al generar factura\n\n"
                "Por favor, intenta de nuevo.\n\n"
                f"📋 Ref: {db_error.correlation_id[:8]}"
            )
            return GENERAR_FACTURA

    await update.message.reply_text(
        "❓ Opción no reconocida\n\n"
        "Selecciona CONFIRMAR o Cancelar:",
        reply_markup=get_generate_keyboard()
    )
    return GENERAR_FACTURA


async def _generar_pdf_factura(invoice_data_dict: dict, context: ContextTypes.DEFAULT_TYPE):
    """
    Genera HTML localmente y solicita PDF a n8n.

    Flujo paralelo:
    1. Bot genera HTML con html_generator → envía al usuario
    2. Bot envía datos a n8n → n8n genera PDF → retorna URL

    Args:
        invoice_data_dict: Diccionario con datos de la factura (extraídos del ORM)
        context: Contexto de Telegram

    Returns:
        Tuple (html_content, pdf_response) o (None, None) si falla
    """
    try:
        # Preparar datos de la factura para html_generator y n8n
        invoice_data = {
            "numero_factura": invoice_data_dict['numero_factura'],
            "fecha_emision": datetime.now().strftime("%Y-%m-%d"),
            "fecha_vencimiento": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
            "cliente_nombre": invoice_data_dict['cliente_nombre'],
            "cliente_direccion": invoice_data_dict.get('cliente_direccion'),
            "cliente_ciudad": invoice_data_dict.get('cliente_ciudad'),
            "cliente_email": invoice_data_dict.get('cliente_email'),
            "cliente_telefono": invoice_data_dict.get('cliente_telefono'),
            "cliente_cedula": invoice_data_dict.get('cliente_cedula'),
            "items": invoice_data_dict['items'],
            "subtotal": invoice_data_dict['subtotal'],
            "descuento": invoice_data_dict.get('descuento', 0),
            "impuesto": invoice_data_dict['impuesto'],
            "total": invoice_data_dict['total'],
            "vendedor_nombre": context.user_data.get('nombre'),
            "vendedor_cedula": context.user_data.get('cedula'),
            "notas": None
        }

        # 1. Generar HTML localmente (para el usuario)
        html_content = html_generator.generate(invoice_data)
        logger.info(f"HTML generado localmente para factura {invoice_data_dict['numero_factura']}")

        # 2. Enviar datos a n8n para generar PDF
        pdf_response = await n8n_service.generate_pdf(
            invoice_data=invoice_data,
            organization_id=invoice_data_dict['organization_id']
        )

        return html_content, pdf_response

    except Exception as e:
        api_error = ExternalAPIError(
            message=f"Error generando documentos: {str(e)}",
            service="n8n",
            original_error=e
        )
        logger.error(f"[{api_error.correlation_id[:8]}] {api_error.message}")
        return None, None


async def _enviar_pdf_usuario(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    invoice_data_dict: dict,
    html_content: str,
    pdf_response
) -> bool:
    """
    Envía el HTML (generado localmente) y PDF (de n8n) al usuario.

    Flujo:
    1. HTML generado por el bot → enviado al usuario
    2. PDF generado por n8n → enviado al usuario

    Args:
        update: Update de Telegram
        context: Contexto de Telegram
        invoice_data_dict: Diccionario con datos de la factura (extraídos del ORM)
        html_content: HTML generado localmente por el bot
        pdf_response: Respuesta de n8n con PDF

    Returns:
        True si se envió correctamente
    """
    try:
        chat_id = update.effective_chat.id
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(exist_ok=True)

        pdf_enviado = False
        html_enviado = False
        numero_factura = invoice_data_dict['numero_factura']
        total = invoice_data_dict['total']

        # 1. Enviar HTML generado localmente
        if html_content:
            try:
                html_filename = f"factura_{numero_factura}.html"
                html_path = upload_dir / html_filename

                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)

                with open(html_path, 'rb') as f:
                    await context.bot.send_document(
                        chat_id=chat_id,
                        document=f,
                        filename=html_filename,
                        caption=f"📄 Factura {numero_factura} (HTML)\nAbre en navegador para visualizar"
                    )

                html_path.unlink(missing_ok=True)
                html_enviado = True
                logger.info(f"HTML enviado para factura {numero_factura}")

            except Exception as e:
                logger.warning(f"Error enviando HTML: {e}")

        # 2. Enviar PDF de n8n (si está disponible)
        if pdf_response and pdf_response.success:
            if pdf_response.pdf_url:
                try:
                    # Descargar PDF desde Google Drive
                    import aiohttp
                    async with aiohttp.ClientSession() as session:
                        async with session.get(pdf_response.pdf_url) as resp:
                            if resp.status == 200:
                                pdf_bytes = await resp.read()
                                pdf_filename = pdf_response.filename or f"factura_{numero_factura}.pdf"

                                # Guardar temporalmente
                                pdf_path = upload_dir / pdf_filename
                                with open(pdf_path, 'wb') as f:
                                    f.write(pdf_bytes)

                                # Enviar documento
                                with open(pdf_path, 'rb') as f:
                                    await context.bot.send_document(
                                        chat_id=chat_id,
                                        document=f,
                                        filename=pdf_filename,
                                        caption=f"📄 Factura {numero_factura} (PDF)\n💰 Total: {format_currency(total)}"
                                    )

                                pdf_path.unlink(missing_ok=True)
                                pdf_enviado = True
                                logger.info(f"PDF enviado para factura {numero_factura}")

                except Exception as e:
                    logger.warning(f"Error descargando PDF desde URL: {e}")
                    # Fallback: enviar link
                    if pdf_response.pdf_view_url:
                        await update.message.reply_text(
                            f"📄 PDF disponible en:\n{pdf_response.pdf_view_url}"
                        )
                        pdf_enviado = True

            elif pdf_response.pdf_base64:
                try:
                    pdf_bytes = base64.b64decode(pdf_response.pdf_base64)
                    pdf_filename = pdf_response.filename or f"factura_{numero_factura}.pdf"
                    pdf_path = upload_dir / pdf_filename

                    with open(pdf_path, 'wb') as f:
                        f.write(pdf_bytes)

                    with open(pdf_path, 'rb') as f:
                        await context.bot.send_document(
                            chat_id=chat_id,
                            document=f,
                            filename=pdf_filename,
                            caption=f"📄 Factura {numero_factura} (PDF)\n💰 Total: {format_currency(total)}"
                        )

                    pdf_path.unlink(missing_ok=True)
                    pdf_enviado = True

                except Exception as e:
                    logger.warning(f"Error enviando PDF base64: {e}")

        return pdf_enviado or html_enviado

    except Exception as e:
        from src.utils.errors import FileError
        file_error = FileError(
            message=f"Error enviando documentos: {str(e)}",
            original_error=e
        )
        logger.error(f"[{file_error.correlation_id[:8]}] {file_error.message}")
        return False


async def cancelar_factura(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela la creación de factura"""
    limpiar_datos_factura(context)
    rol = context.user_data.get('rol')

    await update.message.reply_text(
        MENSAJES['operacion_cancelada'],
        reply_markup=get_menu_keyboard(rol)
    )
    return AuthStates.MENU_PRINCIPAL


# ============================================================================
# HANDLERS DE EDICIÓN GRANULAR DE ITEMS
# ============================================================================

async def editar_item_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe nuevo nombre del item."""
    from src.bot.handlers.shared import get_items_edit_keyboard

    nombre_raw = update.message.text.strip()

    # Validar nombre de producto
    result = ProductValidator.validate_nombre_producto(nombre_raw)
    if not result.valid:
        await update.message.reply_text(
            f"⚠ Nombre inválido\n\n"
            f"{result.error}\n"
            "Escribe el nuevo nombre:"
        )
        return EDITAR_ITEM_NOMBRE

    idx = context.user_data.get('editing_item_index', 0)
    items = context.user_data.get('items', [])

    if idx < len(items):
        items[idx]['nombre'] = result.sanitized
        context.user_data['items'] = items

    # Volver al menú de items
    return await _volver_menu_items(update, context)


async def editar_item_cantidad(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe nueva cantidad del item."""
    try:
        cantidad = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text(
            "⚠ Cantidad inválida\n\n"
            "Escribe solo números:"
        )
        return EDITAR_ITEM_CANTIDAD

    # Validar cantidad con validador centralizado
    result = ProductValidator.validate_cantidad(cantidad)
    if not result.valid:
        await update.message.reply_text(
            f"⚠ Cantidad inválida\n\n"
            f"{result.error}"
        )
        return EDITAR_ITEM_CANTIDAD

    idx = context.user_data.get('editing_item_index', 0)
    items = context.user_data.get('items', [])

    if idx < len(items):
        items[idx]['cantidad'] = cantidad
        context.user_data['items'] = items
        _recalcular_totales(context)

    return await _volver_menu_items(update, context)


async def editar_item_precio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe nuevo precio del item."""
    precio_str = update.message.text.strip()

    # Parsear y validar precio con validador centralizado
    success, precio, error = ProductValidator.parse_precio(precio_str)
    if not success:
        await update.message.reply_text(
            f"⚠ Precio inválido\n\n"
            f"{error}"
        )
        return EDITAR_ITEM_PRECIO

    idx = context.user_data.get('editing_item_index', 0)
    items = context.user_data.get('items', [])

    if idx < len(items):
        items[idx]['precio'] = precio
        context.user_data['items'] = items
        _recalcular_totales(context)

    return await _volver_menu_items(update, context)


async def editar_item_descripcion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe nueva descripción del item."""
    texto = update.message.text.strip()
    idx = context.user_data.get('editing_item_index', 0)
    items = context.user_data.get('items', [])

    if idx < len(items):
        if texto.lower() == 'borrar':
            items[idx]['descripcion'] = ''
        else:
            items[idx]['descripcion'] = texto
        context.user_data['items'] = items

    return await _volver_menu_items(update, context)


async def agregar_item_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe nombre del nuevo item."""
    nombre_raw = update.message.text.strip()

    # Validar nombre de producto
    result = ProductValidator.validate_nombre_producto(nombre_raw)
    if not result.valid:
        await update.message.reply_text(
            f"⚠ Nombre inválido\n\n"
            f"{result.error}"
        )
        return AGREGAR_ITEM

    context.user_data['new_item'] = {'nombre': result.sanitized}

    await update.message.reply_text(
        f"📦 Producto: {result.sanitized}\n\n"
        "🔢 Escribe la cantidad:"
    )
    return AGREGAR_ITEM_CANTIDAD


async def agregar_item_cantidad(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe cantidad del nuevo item."""
    try:
        cantidad = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text(
            "⚠ Cantidad inválida\n\n"
            "Escribe solo números:"
        )
        return AGREGAR_ITEM_CANTIDAD

    # Validar cantidad con validador centralizado
    result = ProductValidator.validate_cantidad(cantidad)
    if not result.valid:
        await update.message.reply_text(
            f"⚠ Cantidad inválida\n\n"
            f"{result.error}"
        )
        return AGREGAR_ITEM_CANTIDAD

    new_item = context.user_data.get('new_item', {})
    new_item['cantidad'] = cantidad
    context.user_data['new_item'] = new_item

    await update.message.reply_text(
        f"📦 Producto: {new_item.get('nombre')}\n"
        f"🔢 Cantidad: {cantidad}\n\n"
        "💵 Escribe el precio unitario:"
    )
    return AGREGAR_ITEM_PRECIO


async def agregar_item_precio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe precio del nuevo item y lo agrega a la lista."""
    precio_str = update.message.text.strip()

    # Parsear y validar precio con validador centralizado
    success, precio, error = ProductValidator.parse_precio(precio_str)
    if not success:
        await update.message.reply_text(
            f"⚠ Precio inválido\n\n"
            f"{error}"
        )
        return AGREGAR_ITEM_PRECIO

    new_item = context.user_data.get('new_item', {})
    new_item['precio'] = precio

    # Agregar a lista de items
    items = context.user_data.get('items', [])
    items.append(new_item)
    context.user_data['items'] = items

    # Limpiar item temporal
    context.user_data.pop('new_item', None)
    context.user_data.pop('adding_new_item', None)

    _recalcular_totales(context)

    await update.message.reply_text(
        f"✅ Producto agregado\n\n"
        f"📦 {new_item.get('nombre')}\n"
        f"   {new_item.get('cantidad')} x {format_currency(precio)}"
    )

    return await _volver_menu_items(update, context)


async def editar_cliente_campo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe nuevo valor para campo del cliente."""
    from src.bot.handlers.shared import get_confirm_inline_keyboard

    nuevo_valor = update.message.text.strip()
    field = context.user_data.get('editing_cliente_field')
    cliente = context.user_data.get('cliente_detectado', {})

    if field and nuevo_valor:
        cliente[field] = nuevo_valor
        context.user_data['cliente_detectado'] = cliente

    # Volver a pantalla de confirmación
    items = context.user_data.get('items', [])
    total = context.user_data.get('total', 0)

    items_text = ""
    for i, item in enumerate(items, 1):
        nombre = item.get('nombre', item.get('descripcion', 'Producto'))
        cantidad = item.get('cantidad', 1)
        precio = item.get('precio', 0)
        subtotal = cantidad * precio

        items_text += f"{i}. {nombre}\n"
        items_text += f"   Cantidad: {cantidad} x {format_currency(precio)} = {format_currency(subtotal)}\n\n"

    mensaje = (
        "📦 PRODUCTOS DETECTADOS\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{items_text}"
        f"💰 Subtotal: {format_currency(total)}\n"
    )

    if cliente and any([cliente.get('nombre'), cliente.get('telefono')]):
        mensaje += "\n👤 CLIENTE DETECTADO\n"
        mensaje += "━━━━━━━━━━━━━━━━━━━━\n"
        if cliente.get('nombre'):
            mensaje += f"   Nombre: {cliente.get('nombre')}\n"
        if cliente.get('telefono'):
            mensaje += f"   Tel: {cliente.get('telefono')}\n"
        if cliente.get('direccion'):
            mensaje += f"   Dir: {cliente.get('direccion')}\n"
        if cliente.get('ciudad'):
            mensaje += f"   Ciudad: {cliente.get('ciudad')}\n"
        if cliente.get('email'):
            mensaje += f"   Email: {cliente.get('email')}\n"

    mensaje += "\n¿Qué deseas hacer?"

    has_cliente = bool(cliente and cliente.get('nombre'))

    await update.message.reply_text(mensaje)
    await update.message.reply_text(
        "Selecciona una opción:",
        reply_markup=get_confirm_inline_keyboard(has_cliente)
    )

    context.user_data.pop('editing_cliente_field', None)
    return CONFIRMAR_DATOS


def _recalcular_totales(context) -> None:
    """Recalcula subtotal y total basado en items."""
    items = context.user_data.get('items', [])
    total = sum(i.get('precio', 0) * i.get('cantidad', 1) for i in items)
    context.user_data['subtotal'] = total
    context.user_data['total'] = total


async def _volver_menu_items(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muestra el menú de edición de items."""
    from src.bot.handlers.shared import get_items_edit_keyboard

    items = context.user_data.get('items', [])

    items_text = "✏️ EDITAR PRODUCTOS\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    total = 0
    for i, item in enumerate(items, 1):
        nombre = item.get('nombre', item.get('descripcion', f'Item {i}'))
        cantidad = item.get('cantidad', 1)
        precio = item.get('precio', 0)
        subtotal = cantidad * precio
        total += subtotal
        items_text += f"{i}. {nombre}\n"
        items_text += f"   {cantidad} x {format_currency(precio)} = {format_currency(subtotal)}\n\n"

    items_text += f"━━━━━━━━━━━━━━━━━━━━━━\n"
    items_text += f"💵 Total: {format_currency(total)}\n\n"
    items_text += "Selecciona un producto para editar:"

    await update.message.reply_text(
        items_text,
        reply_markup=get_items_edit_keyboard(items)
    )

    return EDITAR_SELECCIONAR_ITEM


async def ejecutar_test_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Ejecuta test de generacion PDF con datos de prueba fijos.

    No requiere extraccion previa - usa datos dummy para probar
    el flujo de generacion de HTML y PDF.
    """
    rol = context.user_data.get('rol')

    # Datos de prueba fijos
    test_items = [
        {
            "nombre": "Anillo Oro 18K",
            "descripcion": "Solitario con diamante 0.5ct",
            "cantidad": 1,
            "precio": 2500000
        },
        {
            "nombre": "Cadena Plata 925",
            "descripcion": "Cadena eslabones 50cm",
            "cantidad": 2,
            "precio": 180000
        },
        {
            "nombre": "Aretes Perlas",
            "descripcion": "Aretes gota perlas cultivadas",
            "cantidad": 1,
            "precio": 350000
        }
    ]

    # Calcular subtotal (los items son dicts con valores int)
    subtotal: int = 0
    for item in test_items:
        precio = item['precio']
        cantidad = item['cantidad']
        if isinstance(precio, int) and isinstance(cantidad, int):
            subtotal += precio * cantidad
    impuesto = int(subtotal * settings.TAX_RATE)
    total = subtotal + impuesto

    # Mostrar mensaje de procesamiento
    processing_msg = await update.message.reply_text(
        "🧪 TEST PDF\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 Items: {len(test_items)}\n"
        f"💰 Subtotal: {format_currency(subtotal)}\n"
        f"📊 IVA ({int(settings.TAX_RATE * 100)}%): {format_currency(impuesto)}\n"
        f"💵 Total: {format_currency(total)}\n\n"
        "⏳ Generando documentos..."
    )

    try:
        invoice_data = {
            "numero_factura": "TEST-001",
            "fecha_emision": datetime.now().strftime("%Y-%m-%d"),
            "fecha_vencimiento": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
            "cliente_nombre": "Cliente de Prueba",
            "cliente_direccion": "Calle 123 #45-67",
            "cliente_ciudad": "Bogota",
            "cliente_email": "cliente@test.com",
            "cliente_telefono": "3001234567",
            "cliente_cedula": "1234567890",
            "items": test_items,
            "subtotal": subtotal,
            "descuento": 0,
            "impuesto": impuesto,
            "total": total,
            "vendedor_nombre": context.user_data.get('nombre', 'Vendedor Test'),
            "vendedor_cedula": context.user_data.get('cedula', '0000000000'),
            "notas": "Factura de prueba - Test PDF"
        }

        # 1. Generar HTML local
        html_content = html_generator.generate(invoice_data)
        logger.info("HTML de prueba generado")

        # 2. Enviar HTML al usuario
        chat_id = update.effective_chat.id
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(exist_ok=True)

        html_filename = "factura_TEST-001.html"
        html_path = upload_dir / html_filename

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        with open(html_path, 'rb') as f:
            await context.bot.send_document(
                chat_id=chat_id,
                document=f,
                filename=html_filename,
                caption="📄 HTML de prueba\nAbre en navegador para visualizar"
            )

        html_path.unlink(missing_ok=True)

        # 3. Enviar a n8n para PDF
        await processing_msg.edit_text(
            "🧪 TEST PDF\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ HTML generado y enviado\n"
            "⏳ Solicitando PDF a n8n..."
        )

        pdf_response = await n8n_service.generate_pdf(
            invoice_data=invoice_data,
            organization_id=str(context.user_data.get('organization_id', 'test'))
        )

        # 4. Mostrar resultado
        resultado = (
            "🧪 TEST PDF - RESULTADO\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📦 Items: {len(test_items)}\n"
            f"💰 Subtotal: {format_currency(subtotal)}\n"
            f"📊 IVA ({int(settings.TAX_RATE * 100)}%): {format_currency(impuesto)}\n"
            f"💵 Total: {format_currency(total)}\n\n"
            "✅ HTML: Generado y enviado\n"
        )

        if pdf_response and pdf_response.success:
            resultado += "✅ PDF n8n: Exitoso\n"
            if pdf_response.pdf_url:
                resultado += f"🔗 {pdf_response.pdf_url}\n"
        else:
            error_msg = pdf_response.error if pdf_response else "Sin respuesta"
            resultado += f"⚠ PDF n8n: {error_msg}\n"

        resultado += "\n🔄 Volviendo al menú..."

        await processing_msg.edit_text(resultado)

        # Mostrar menu
        await update.message.reply_text(
            "✅ Test completado\n\n¿Qué deseas hacer?",
            reply_markup=get_menu_keyboard(rol)
        )

    except Exception as e:
        logger.error(f"Error en test_pdf: {e}")
        await processing_msg.edit_text(
            f"🧪 TEST PDF - ERROR\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"⚠ {str(e)}"
        )
        await update.message.reply_text(
            "¿Qué deseas hacer?",
            reply_markup=get_menu_keyboard(rol)
        )


async def test_pdf_comando(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Comando /test_pdf para probar generacion de PDF.
    Redirige a ejecutar_test_pdf con datos de prueba.
    """
    if not is_authenticated(context):
        await update.message.reply_text(
            "🔐 Sesión requerida\n\n"
            "Para continuar, inicia sesión con /start"
        )
        return

    await ejecutar_test_pdf(update, context)


def get_invoice_conversation_handler() -> ConversationHandler:
    """Retorna el ConversationHandler para crear facturas"""
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r'^1\. Nueva Factura$'), iniciar_nueva_factura)
        ],
        states={
            SELECCIONAR_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, seleccionar_tipo_input)
            ],
            RECIBIR_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_input),
                MessageHandler(filters.VOICE, recibir_input),
                MessageHandler(filters.PHOTO, recibir_input)
            ],
            CONFIRMAR_DATOS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, confirmar_datos)
            ],
            EDITAR_ITEMS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, editar_items)
            ],
            DATOS_CLIENTE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, datos_cliente)
            ],
            CLIENTE_DIRECCION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, cliente_direccion)
            ],
            CLIENTE_CIUDAD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, cliente_ciudad)
            ],
            CLIENTE_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, cliente_email)
            ],
            CLIENTE_TELEFONO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, cliente_telefono)
            ],
            CLIENTE_CEDULA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, cliente_cedula)
            ],
            METODO_PAGO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, metodo_pago)
            ],
            BANCO_DESTINO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, banco_destino)
            ],
            EDITAR_ITEM_DESCRIPCION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, editar_item_descripcion)
            ],
            GENERAR_FACTURA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, generar_factura)
            ]
        },
        fallbacks=[
            MessageHandler(filters.Regex(r'^Cancelar$'), cancelar_factura)
        ],
        map_to_parent={
            AuthStates.MENU_PRINCIPAL: AuthStates.MENU_PRINCIPAL
        }
    )