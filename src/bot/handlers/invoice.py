"""
Handlers de Facturación

Maneja el flujo de creación de facturas con input de texto, voz o foto.
"""

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)
from pathlib import Path

from src.utils.logger import get_logger
from src.database.connection import get_db
from src.database.queries.invoice_queries import create_invoice
from src.services.n8n_service import n8n_service
from config.constants import InvoiceStatus, InputType
from config.settings import settings

logger = get_logger(__name__)

# Estados de la conversación para facturas
(
    SELECCIONAR_INPUT,
    RECIBIR_INPUT,
    CONFIRMAR_DATOS,
    EDITAR_ITEMS,
    DATOS_CLIENTE,
    CLIENTE_TELEFONO,
    CLIENTE_CEDULA,
    GENERAR_FACTURA
) = range(100, 108)  # Usar rango diferente para no conflictos con auth

# Teclado para seleccionar tipo de input
INPUT_KEYBOARD = ReplyKeyboardMarkup([
    ['Texto - Escribir items'],
    ['Voz - Dictar items'],
    ['Foto - Capturar lista'],
    ['Cancelar']
], resize_keyboard=True)

# Teclado de confirmación
CONFIRM_KEYBOARD = ReplyKeyboardMarkup([
    ['Si, continuar'],
    ['Editar manualmente'],
    ['Cancelar']
], resize_keyboard=True)


async def iniciar_nueva_factura(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el proceso de crear una nueva factura"""

    if not context.user_data.get('autenticado'):
        await update.message.reply_text(
            "Debes iniciar sesión primero.\n"
            "Usa /start para comenzar."
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "NUEVA FACTURA\n"
        "=" * 25 + "\n\n"
        "¿Cómo deseas ingresar los items?\n\n"
        "- Texto: escribe los productos\n"
        "- Voz: dicta los productos\n"
        "- Foto: toma foto de lista/ticket",
        reply_markup=INPUT_KEYBOARD
    )

    return SELECCIONAR_INPUT


async def seleccionar_tipo_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Procesa la selección del tipo de input"""
    opcion = update.message.text.lower()

    if 'cancelar' in opcion:
        from src.bot.handlers.auth import get_menu_keyboard
        rol = context.user_data.get('rol')
        await update.message.reply_text(
            "Operación cancelada.\n\n"
            "¿Qué deseas hacer?",
            reply_markup=get_menu_keyboard(rol)
        )
        return 2  # MENU_PRINCIPAL de auth

    if 'texto' in opcion:
        context.user_data['input_type'] = InputType.TEXTO.value
        await update.message.reply_text(
            "INGRESO POR TEXTO\n"
            "=" * 25 + "\n\n"
            "Escribe los productos a facturar.\n\n"
            "Ejemplo:\n"
            "- Anillo oro 18k, 5g - $500.000\n"
            "- Cadena plata 925, 20g - $150.000\n"
            "- Aretes diamante - $1.200.000",
            reply_markup=ReplyKeyboardRemove()
        )
        return RECIBIR_INPUT

    elif 'voz' in opcion:
        context.user_data['input_type'] = InputType.VOZ.value
        await update.message.reply_text(
            "INGRESO POR VOZ\n"
            "=" * 25 + "\n\n"
            "Envía un mensaje de voz dictando los productos.\n\n"
            "Ejemplo:\n"
            "'Un anillo de oro 18 kilates de 5 gramos a 500 mil pesos,\n"
            "una cadena de plata 925 de 20 gramos a 150 mil...'",
            reply_markup=ReplyKeyboardRemove()
        )
        return RECIBIR_INPUT

    elif 'foto' in opcion:
        context.user_data['input_type'] = InputType.FOTO.value
        await update.message.reply_text(
            "INGRESO POR FOTO\n"
            "=" * 25 + "\n\n"
            "Envía una foto de:\n"
            "- Lista de productos escrita\n"
            "- Ticket o recibo\n"
            "- Cotización previa",
            reply_markup=ReplyKeyboardRemove()
        )
        return RECIBIR_INPUT

    # Opción no reconocida
    await update.message.reply_text(
        "Opción no reconocida.\n"
        "Selecciona una opción del teclado:",
        reply_markup=INPUT_KEYBOARD
    )
    return SELECCIONAR_INPUT


async def recibir_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe el input del usuario (texto, voz o foto)"""
    input_type = context.user_data.get('input_type')
    cedula = context.user_data.get('cedula')

    # Mostrar mensaje de procesando
    processing_msg = await update.message.reply_text(
        "Procesando... Por favor espera."
    )

    try:
        response = None

        if input_type == InputType.TEXTO.value:
            # Texto directo
            text = update.message.text
            if not text:
                await processing_msg.edit_text(
                    "No se recibió texto.\n"
                    "Por favor, escribe los productos:"
                )
                return RECIBIR_INPUT

            context.user_data['input_raw'] = text
            response = await n8n_service.send_text_input(text, cedula)

        elif input_type == InputType.VOZ.value:
            # Descargar audio
            voice = update.message.voice
            if not voice:
                await processing_msg.edit_text(
                    "No se recibió audio.\n"
                    "Por favor, envía un mensaje de voz:"
                )
                return RECIBIR_INPUT

            # Crear directorio uploads si no existe
            upload_dir = Path(settings.UPLOAD_DIR)
            upload_dir.mkdir(exist_ok=True)

            # Descargar archivo
            file = await context.bot.get_file(voice.file_id)
            audio_path = upload_dir / f"{voice.file_id}.ogg"
            await file.download_to_drive(str(audio_path))

            context.user_data['input_raw'] = str(audio_path)
            response = await n8n_service.send_voice_input(str(audio_path), cedula)

        elif input_type == InputType.FOTO.value:
            # Descargar foto (la más grande disponible)
            photos = update.message.photo
            if not photos:
                await processing_msg.edit_text(
                    "No se recibió foto.\n"
                    "Por favor, envía una imagen:"
                )
                return RECIBIR_INPUT

            photo = photos[-1]  # La última es la más grande

            # Crear directorio uploads si no existe
            upload_dir = Path(settings.UPLOAD_DIR)
            upload_dir.mkdir(exist_ok=True)

            # Descargar archivo
            file = await context.bot.get_file(photo.file_id)
            photo_path = upload_dir / f"{photo.file_id}.jpg"
            await file.download_to_drive(str(photo_path))

            context.user_data['input_raw'] = str(photo_path)
            response = await n8n_service.send_photo_input(str(photo_path), cedula)

        else:
            await processing_msg.edit_text(
                "Tipo de input no reconocido.\n"
                "Por favor, intenta de nuevo."
            )
            return SELECCIONAR_INPUT

        # Procesar respuesta de n8n
        if response and response.success and response.items:
            context.user_data['items'] = response.items
            context.user_data['transcripcion'] = response.transcripcion

            # Mostrar items extraídos
            items_text = ""
            total = 0
            for i, item in enumerate(response.items, 1):
                precio = item.get('precio', 0)
                cantidad = item.get('cantidad', 1)
                subtotal = precio * cantidad
                total += subtotal
                items_text += f"{i}. {item.get('descripcion', 'Sin descripción')}\n"
                items_text += f"   Cantidad: {cantidad} x ${precio:,.0f} = ${subtotal:,.0f}\n\n"

            context.user_data['subtotal'] = total
            context.user_data['total'] = total

            mensaje = (
                "ITEMS DETECTADOS\n"
                "=" * 25 + "\n\n"
                f"{items_text}"
                f"SUBTOTAL: ${total:,.0f}\n\n"
            )

            if response.transcripcion:
                mensaje += f"Transcripción: {response.transcripcion[:100]}...\n\n"

            mensaje += "¿Los datos son correctos?"

            await processing_msg.edit_text(mensaje)
            await update.message.reply_text(
                "Confirma los datos:",
                reply_markup=CONFIRM_KEYBOARD
            )

            return CONFIRMAR_DATOS

        else:
            # Fallback: pedir ingreso manual
            error_msg = response.error if response else "Error de conexión"

            await processing_msg.edit_text(
                f"No se pudo procesar automáticamente.\n"
                f"Razón: {error_msg}\n\n"
                "Por favor, ingresa los items manualmente.\n"
                "Formato: descripción - $precio\n\n"
                "Ejemplo:\n"
                "Anillo oro 18k - $500000\n"
                "Cadena plata - $150000"
            )

            context.user_data['input_type'] = InputType.TEXTO.value
            context.user_data['manual_mode'] = True
            return RECIBIR_INPUT

    except Exception as e:
        logger.error(f"Error procesando input: {e}")
        await processing_msg.edit_text(
            f"Error al procesar: {str(e)}\n\n"
            "Intenta de nuevo o ingresa manualmente."
        )
        return RECIBIR_INPUT


async def confirmar_datos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Confirma los datos extraídos"""
    opcion = update.message.text.lower()

    if 'cancelar' in opcion:
        from src.bot.handlers.auth import get_menu_keyboard
        rol = context.user_data.get('rol')
        await update.message.reply_text(
            "Operación cancelada.\n\n"
            "¿Qué deseas hacer?",
            reply_markup=get_menu_keyboard(rol)
        )
        # Limpiar datos temporales
        for key in ['items', 'input_type', 'input_raw', 'subtotal', 'total', 'transcripcion']:
            context.user_data.pop(key, None)
        return 2  # MENU_PRINCIPAL

    if 'si' in opcion or 'continuar' in opcion:
        await update.message.reply_text(
            "DATOS DEL CLIENTE\n"
            "=" * 25 + "\n\n"
            "Ingresa el nombre del cliente:",
            reply_markup=ReplyKeyboardRemove()
        )
        return DATOS_CLIENTE

    if 'editar' in opcion or 'manual' in opcion:
        await update.message.reply_text(
            "EDITAR ITEMS\n"
            "=" * 25 + "\n\n"
            "Ingresa los items en el formato:\n"
            "descripción - $precio\n\n"
            "Un item por línea.\n"
            "Escribe 'listo' cuando termines.",
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data['items'] = []
        return EDITAR_ITEMS

    await update.message.reply_text(
        "Opción no reconocida.\n"
        "Selecciona una opción:",
        reply_markup=CONFIRM_KEYBOARD
    )
    return CONFIRMAR_DATOS


async def editar_items(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Permite editar items manualmente"""
    text = update.message.text.strip()

    if text.lower() == 'listo':
        items = context.user_data.get('items', [])
        if not items:
            await update.message.reply_text(
                "No has ingresado ningún item.\n"
                "Ingresa al menos un producto:"
            )
            return EDITAR_ITEMS

        # Calcular total
        total = sum(item.get('precio', 0) * item.get('cantidad', 1) for item in items)
        context.user_data['subtotal'] = total
        context.user_data['total'] = total

        await update.message.reply_text(
            "DATOS DEL CLIENTE\n"
            "=" * 25 + "\n\n"
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
                "Formato incorrecto.\n"
                "Usa: descripción - $precio\n"
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
            f"Item agregado: {descripcion} - ${precio:,.0f}\n\n"
            f"Total items: {len(items)}\n\n"
            "Ingresa otro item o escribe 'listo':"
        )
        return EDITAR_ITEMS

    except (ValueError, IndexError) as e:
        await update.message.reply_text(
            "No pude entender el precio.\n"
            "Usa: descripción - $precio\n"
            "Ejemplo: Anillo oro 18k - $500000"
        )
        return EDITAR_ITEMS


async def datos_cliente(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe el nombre del cliente"""
    nombre = update.message.text.strip()

    if len(nombre) < 3:
        await update.message.reply_text(
            "El nombre debe tener al menos 3 caracteres.\n"
            "Ingresa el nombre del cliente:"
        )
        return DATOS_CLIENTE

    context.user_data['cliente_nombre'] = nombre

    await update.message.reply_text(
        f"Cliente: {nombre}\n\n"
        "Teléfono del cliente:\n"
        "(Escribe 'omitir' si no tienes)"
    )
    return CLIENTE_TELEFONO


async def cliente_telefono(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe el teléfono del cliente"""
    telefono = update.message.text.strip()

    if telefono.lower() != 'omitir':
        context.user_data['cliente_telefono'] = telefono

    await update.message.reply_text(
        "Cédula del cliente:\n"
        "(Escribe 'omitir' si no tienes)"
    )
    return CLIENTE_CEDULA


async def cliente_cedula(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe la cédula del cliente y muestra resumen"""
    cedula_cliente = update.message.text.strip()

    if cedula_cliente.lower() != 'omitir':
        context.user_data['cliente_cedula'] = cedula_cliente

    # Mostrar resumen
    items = context.user_data.get('items', [])
    subtotal = context.user_data.get('subtotal', 0)
    total = context.user_data.get('total', 0)

    items_text = ""
    for item in items:
        precio = item.get('precio', 0)
        cantidad = item.get('cantidad', 1)
        items_text += f"  - {item.get('descripcion')}: ${precio:,.0f}\n"

    mensaje = (
        "RESUMEN DE FACTURA\n"
        "=" * 30 + "\n\n"
        f"Cliente: {context.user_data.get('cliente_nombre')}\n"
        f"Teléfono: {context.user_data.get('cliente_telefono', 'N/A')}\n"
        f"Cédula: {context.user_data.get('cliente_cedula', 'N/A')}\n\n"
        f"Items:\n{items_text}\n"
        f"SUBTOTAL: ${subtotal:,.0f}\n"
        f"TOTAL: ${total:,.0f}\n\n"
        "¿Confirmar y generar factura?"
    )

    await update.message.reply_text(
        mensaje,
        reply_markup=ReplyKeyboardMarkup([
            ['CONFIRMAR Y GENERAR'],
            ['Cancelar']
        ], resize_keyboard=True)
    )

    return GENERAR_FACTURA


async def generar_factura(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Genera la factura final"""
    opcion = update.message.text.lower()

    if 'cancelar' in opcion:
        from src.bot.handlers.auth import get_menu_keyboard
        rol = context.user_data.get('rol')
        await update.message.reply_text(
            "Operación cancelada.\n\n"
            "¿Qué deseas hacer?",
            reply_markup=get_menu_keyboard(rol)
        )
        # Limpiar datos temporales
        limpiar_datos_factura(context)
        return 2  # MENU_PRINCIPAL

    if 'confirmar' in opcion or 'generar' in opcion:
        try:
            db = next(get_db())

            # Preparar datos de factura
            invoice_data = {
                "cliente_nombre": context.user_data.get('cliente_nombre'),
                "cliente_telefono": context.user_data.get('cliente_telefono'),
                "cliente_cedula": context.user_data.get('cliente_cedula'),
                "items": context.user_data.get('items', []),
                "subtotal": context.user_data.get('subtotal', 0),
                "total": context.user_data.get('total', 0),
                "estado": InvoiceStatus.PENDIENTE.value,
                "vendedor_id": context.user_data.get('user_id'),
                "input_type": context.user_data.get('input_type'),
                "input_raw": context.user_data.get('input_raw'),
                "n8n_processed": True
            }

            # Crear factura en BD
            invoice = create_invoice(db, invoice_data)
            db.close()

            if invoice:
                logger.info(f"Factura creada: {invoice.numero_factura} por {context.user_data.get('cedula')}")

                from src.bot.handlers.auth import get_menu_keyboard
                rol = context.user_data.get('rol')

                await update.message.reply_text(
                    "FACTURA GENERADA\n"
                    "=" * 30 + "\n\n"
                    f"No. Factura: {invoice.numero_factura}\n"
                    f"Cliente: {invoice.cliente_nombre}\n"
                    f"Total: ${invoice.total:,.0f}\n"
                    f"Estado: PENDIENTE\n\n"
                    "La factura ha sido guardada exitosamente.",
                    reply_markup=get_menu_keyboard(rol)
                )

                # Limpiar datos temporales
                limpiar_datos_factura(context)

                return 2  # MENU_PRINCIPAL

            else:
                await update.message.reply_text(
                    "Error al guardar la factura.\n"
                    "Por favor intenta de nuevo.",
                    reply_markup=ReplyKeyboardRemove()
                )
                return GENERAR_FACTURA

        except Exception as e:
            logger.error(f"Error generando factura: {e}")
            await update.message.reply_text(
                f"Error: {str(e)}",
                reply_markup=ReplyKeyboardRemove()
            )
            return GENERAR_FACTURA

    await update.message.reply_text(
        "Opción no reconocida.\n"
        "Selecciona CONFIRMAR o Cancelar:",
        reply_markup=ReplyKeyboardMarkup([
            ['CONFIRMAR Y GENERAR'],
            ['Cancelar']
        ], resize_keyboard=True)
    )
    return GENERAR_FACTURA


def limpiar_datos_factura(context: ContextTypes.DEFAULT_TYPE):
    """Limpia los datos temporales de factura del contexto"""
    keys_to_remove = [
        'items', 'cliente_nombre', 'cliente_telefono', 'cliente_cedula',
        'subtotal', 'total', 'input_type', 'input_raw', 'transcripcion',
        'manual_mode'
    ]
    for key in keys_to_remove:
        context.user_data.pop(key, None)


async def cancelar_factura(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela la creación de factura"""
    from src.bot.handlers.auth import get_menu_keyboard

    limpiar_datos_factura(context)
    rol = context.user_data.get('rol')

    await update.message.reply_text(
        "Operación cancelada.\n\n"
        "¿Qué deseas hacer?",
        reply_markup=get_menu_keyboard(rol)
    )
    return 2  # MENU_PRINCIPAL


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
            CLIENTE_TELEFONO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, cliente_telefono)
            ],
            CLIENTE_CEDULA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, cliente_cedula)
            ],
            GENERAR_FACTURA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, generar_factura)
            ]
        },
        fallbacks=[
            MessageHandler(filters.Regex(r'^Cancelar$'), cancelar_factura)
        ],
        map_to_parent={
            2: 2  # Mapear MENU_PRINCIPAL al del auth handler
        }
    )