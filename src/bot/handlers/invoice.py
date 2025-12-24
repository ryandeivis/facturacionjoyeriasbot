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

from src.utils.logger import get_logger
from src.database.connection import get_db
from src.database.queries.invoice_queries import create_invoice
from src.services.n8n_service import n8n_service
from src.services.text_parser import text_parser
from src.bot.handlers.shared import (
    AuthStates,
    InvoiceStates,
    get_menu_keyboard,
    get_input_type_keyboard,
    get_confirm_keyboard,
    get_confirm_inline_keyboard,
    get_generate_keyboard,
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
from config.constants import InvoiceStatus, InputType
from config.settings import settings

logger = get_logger(__name__)

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


async def iniciar_nueva_factura(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el proceso de crear una nueva factura"""

    if not is_authenticated(context):
        await update.message.reply_text(MENSAJES['no_autenticado'])
        return ConversationHandler.END

    await update.message.reply_text(
        "NUEVA FACTURA\n"
        "=========================\n\n"
        "¿Cómo deseas ingresar los items?\n\n"
        "- Texto: escribe los productos\n"
        "- Voz: dicta los productos\n"
        "- Foto: toma foto de lista/ticket",
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

    # Opción no reconocida
    await update.message.reply_text(
        "Opción no reconocida.\n"
        "Selecciona una opción del teclado:",
        reply_markup=get_input_type_keyboard()
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
            # Texto directo - usar parser local (no n8n)
            text = update.message.text
            if not text:
                await processing_msg.edit_text(
                    "No se recibió texto.\n"
                    "Por favor, escribe los productos:"
                )
                return RECIBIR_INPUT

            context.user_data['input_raw'] = text
            # Usar parser local para texto (más rápido y sin costo)
            response = text_parser.parse(text)
            logger.info(f"Texto parseado localmente: {response.success}, {len(response.items)} items")

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

            # Guardar respuesta completa para no perder datos
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

            # Mostrar items extraídos
            items_text = ""
            total = 0
            for i, item in enumerate(formatted_items, 1):
                precio = item.get('precio', 0)
                cantidad = item.get('cantidad', 1)
                subtotal = precio * cantidad
                total += subtotal

                # Fix: usar 'nombre' primero, luego 'descripcion' como fallback
                nombre = item.get('nombre', 'Producto')
                descripcion = item.get('descripcion', '')

                items_text += f"{i}. {nombre}\n"
                if descripcion:
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

            # Mostrar cliente detectado si existe
            if response.cliente:
                cliente = response.cliente
                has_cliente_data = any([
                    cliente.get('nombre'),
                    cliente.get('telefono'),
                    cliente.get('direccion')
                ])
                if has_cliente_data:
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

            if response.transcripcion:
                mensaje += f"\nTranscripción: {response.transcripcion[:100]}...\n"

            mensaje += "\nSelecciona una opción:"

            await processing_msg.edit_text(mensaje)

            # Usar InlineKeyboard para edición granular
            has_cliente = bool(response.cliente and response.cliente.get('nombre'))
            await update.message.reply_text(
                "Confirma los datos:",
                reply_markup=get_confirm_inline_keyboard(has_cliente)
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
        rol = context.user_data.get('rol')
        await update.message.reply_text(
            MENSAJES['operacion_cancelada'],
            reply_markup=get_menu_keyboard(rol)
        )
        limpiar_datos_factura(context)
        return AuthStates.MENU_PRINCIPAL

    if 'si' in opcion or 'continuar' in opcion:
        await update.message.reply_text(
            "DATOS DEL CLIENTE\n"
            "=========================\n\n"
            "Ingresa el nombre del cliente:",
            reply_markup=ReplyKeyboardRemove()
        )
        return DATOS_CLIENTE

    if 'editar' in opcion or 'manual' in opcion:
        await update.message.reply_text(
            "EDITAR ITEMS\n"
            "=========================\n\n"
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
            "=========================\n\n"
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
            f"Item agregado: {descripcion} - {format_currency(precio)}\n\n"
            f"Total items: {len(items)}\n\n"
            "Ingresa otro item o escribe 'listo':"
        )
        return EDITAR_ITEMS

    except (ValueError, IndexError):
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
        "Direccion del cliente (calle y numero):\n"
        "(Escribe 'omitir' si no tienes)"
    )
    return CLIENTE_DIRECCION


async def cliente_direccion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe la dirección del cliente"""
    direccion = update.message.text.strip()

    if direccion.lower() != 'omitir':
        context.user_data['cliente_direccion'] = direccion

    await update.message.reply_text(
        "Ciudad del cliente:\n"
        "(Escribe 'omitir' si no tienes)"
    )
    return CLIENTE_CIUDAD


async def cliente_ciudad(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe la ciudad del cliente"""
    ciudad = update.message.text.strip()

    if ciudad.lower() != 'omitir':
        context.user_data['cliente_ciudad'] = ciudad

    await update.message.reply_text(
        "Email del cliente:\n"
        "(Escribe 'omitir' si no tienes)"
    )
    return CLIENTE_EMAIL


async def cliente_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe el email del cliente y muestra resumen"""
    email = update.message.text.strip()

    if email.lower() != 'omitir':
        context.user_data['cliente_email'] = email

    # Mostrar resumen con todos los datos
    await _mostrar_resumen_factura(update, context)
    return GENERAR_FACTURA


async def _mostrar_resumen_factura(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra el resumen de la factura antes de confirmar"""
    items = context.user_data.get('items', [])
    subtotal = context.user_data.get('subtotal', 0)
    total = context.user_data.get('total', 0)

    # Formatear items
    items_text = ""
    for i, item in enumerate(items, 1):
        nombre = item.get('nombre', item.get('descripcion', 'Producto'))
        descripcion = item.get('descripcion', '')
        cantidad = item.get('cantidad', 1)
        precio = item.get('precio', 0)
        item_total = cantidad * precio

        items_text += f"{i}. {nombre}\n"
        if descripcion and descripcion != nombre:
            items_text += f"   {descripcion}\n"
        items_text += f"   {cantidad} x {format_currency(precio)} = {format_currency(item_total)}\n\n"

    mensaje = (
        "RESUMEN DE FACTURA\n"
        "==============================\n\n"
        "CLIENTE:\n"
        f"  Nombre: {context.user_data.get('cliente_nombre', 'N/A')}\n"
        f"  Direccion: {context.user_data.get('cliente_direccion', 'N/A')}\n"
        f"  Ciudad: {context.user_data.get('cliente_ciudad', 'N/A')}\n"
        f"  Email: {context.user_data.get('cliente_email', 'N/A')}\n\n"
        f"ITEMS:\n{items_text}"
        f"SUBTOTAL: {format_currency(subtotal)}\n"
        f"TOTAL: {format_currency(total)}\n\n"
        "Confirmar y generar factura?"
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
        # Mostrar mensaje de procesando
        processing_msg = await update.message.reply_text(
            "Generando factura... Por favor espera."
        )

        try:
            db = next(get_db())
            org_id = context.user_data.get('organization_id')

            # Calcular impuesto usando tasa configurada
            subtotal = context.user_data.get('subtotal', 0)
            impuesto = round(subtotal * settings.TAX_RATE)
            total = subtotal + impuesto

            # Preparar datos de factura
            invoice_data = {
                "organization_id": org_id,
                "cliente_nombre": context.user_data.get('cliente_nombre'),
                "cliente_direccion": context.user_data.get('cliente_direccion'),
                "cliente_ciudad": context.user_data.get('cliente_ciudad'),
                "cliente_email": context.user_data.get('cliente_email'),
                "cliente_telefono": context.user_data.get('cliente_telefono'),
                "cliente_cedula": context.user_data.get('cliente_cedula'),
                "items": context.user_data.get('items', []),
                "subtotal": subtotal,
                "impuesto": impuesto,
                "total": total,
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

                # Actualizar mensaje
                await processing_msg.edit_text(
                    f"Factura {invoice.numero_factura} guardada.\n"
                    "Generando PDF..."
                )

                # Solicitar PDF a n8n
                pdf_data = await _generar_pdf_factura(invoice, context)

                rol = context.user_data.get('rol')

                if pdf_data and pdf_data.success:
                    # Enviar PDF al usuario
                    await _enviar_pdf_usuario(update, context, invoice, pdf_data)

                    await update.message.reply_text(
                        "FACTURA GENERADA\n"
                        "==============================\n\n"
                        f"No. Factura: {invoice.numero_factura}\n"
                        f"Cliente: {invoice.cliente_nombre}\n"
                        f"Subtotal: {format_currency(subtotal)}\n"
                        f"IVA ({int(settings.TAX_RATE * 100)}%): {format_currency(impuesto)}\n"
                        f"Total: {format_currency(total)}\n"
                        f"Estado: PENDIENTE\n\n"
                        "PDF enviado exitosamente.",
                        reply_markup=get_menu_keyboard(rol)
                    )
                else:
                    # Factura guardada pero sin PDF
                    await update.message.reply_text(
                        "FACTURA GENERADA\n"
                        "==============================\n\n"
                        f"No. Factura: {invoice.numero_factura}\n"
                        f"Cliente: {invoice.cliente_nombre}\n"
                        f"Total: {format_currency(total)}\n"
                        f"Estado: PENDIENTE\n\n"
                        "Factura guardada.\n"
                        "(PDF no disponible temporalmente)",
                        reply_markup=get_menu_keyboard(rol)
                    )

                # Limpiar datos temporales
                limpiar_datos_factura(context)

                return AuthStates.MENU_PRINCIPAL

            else:
                await processing_msg.edit_text(
                    "Error al guardar la factura.\n"
                    "Por favor intenta de nuevo."
                )
                return GENERAR_FACTURA

        except Exception as e:
            logger.error(f"Error generando factura: {e}")
            await processing_msg.edit_text(
                f"Error: {str(e)}\n\n"
                "Intenta de nuevo."
            )
            return GENERAR_FACTURA

    await update.message.reply_text(
        "Opcion no reconocida.\n"
        "Selecciona CONFIRMAR o Cancelar:",
        reply_markup=get_generate_keyboard()
    )
    return GENERAR_FACTURA


async def _generar_pdf_factura(invoice, context: ContextTypes.DEFAULT_TYPE):
    """
    Solicita generación de PDF a n8n.

    Args:
        invoice: Objeto Invoice de la BD
        context: Contexto de Telegram

    Returns:
        N8NPDFResponse o None si falla
    """
    try:
        # Preparar datos para n8n
        pdf_request_data = {
            "id": str(invoice.id),
            "numero_factura": invoice.numero_factura,
            "fecha_emision": datetime.utcnow().strftime("%Y-%m-%d"),
            "fecha_vencimiento": (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d"),
            "cliente_nombre": invoice.cliente_nombre,
            "cliente_direccion": invoice.cliente_direccion,
            "cliente_ciudad": invoice.cliente_ciudad,
            "cliente_email": invoice.cliente_email,
            "cliente_telefono": invoice.cliente_telefono,
            "cliente_cedula": invoice.cliente_cedula,
            "items": invoice.items,
            "subtotal": invoice.subtotal,
            "descuento": invoice.descuento,
            "impuesto": invoice.impuesto,
            "total": invoice.total,
            "vendedor_nombre": context.user_data.get('nombre'),
            "vendedor_cedula": context.user_data.get('cedula'),
            "notas": None
        }

        # Llamar a n8n
        response = await n8n_service.generate_pdf(
            invoice_data=pdf_request_data,
            organization_id=str(invoice.organization_id)
        )

        return response

    except Exception as e:
        logger.error(f"Error solicitando PDF a n8n: {e}")
        return None


async def _enviar_pdf_usuario(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    invoice,
    pdf_data
) -> bool:
    """
    Envía el PDF y HTML generados al usuario.

    Args:
        update: Update de Telegram
        context: Contexto de Telegram
        invoice: Objeto Invoice
        pdf_data: Respuesta de n8n con PDF y HTML

    Returns:
        True si se envió correctamente
    """
    try:
        chat_id = update.effective_chat.id
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(exist_ok=True)

        pdf_enviado = False
        html_enviado = False

        # 1. Enviar PDF (desde URL de Drive o base64)
        if pdf_data.pdf_url:
            try:
                # Descargar PDF desde Google Drive
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(pdf_data.pdf_url) as resp:
                        if resp.status == 200:
                            pdf_bytes = await resp.read()
                            pdf_filename = pdf_data.filename or f"factura_{invoice.numero_factura}.pdf"

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
                                    caption=f"Factura {invoice.numero_factura}\nTotal: {format_currency(invoice.total)}"
                                )

                            pdf_path.unlink(missing_ok=True)
                            pdf_enviado = True
            except Exception as e:
                logger.warning(f"Error descargando PDF desde URL: {e}")
                # Fallback: enviar link
                if pdf_data.pdf_view_url:
                    await update.message.reply_text(
                        f"PDF disponible en:\n{pdf_data.pdf_view_url}"
                    )
                    pdf_enviado = True

        elif pdf_data.pdf_base64:
            try:
                pdf_bytes = base64.b64decode(pdf_data.pdf_base64)
                pdf_filename = pdf_data.filename or f"factura_{invoice.numero_factura}.pdf"
                pdf_path = upload_dir / pdf_filename

                with open(pdf_path, 'wb') as f:
                    f.write(pdf_bytes)

                with open(pdf_path, 'rb') as f:
                    await context.bot.send_document(
                        chat_id=chat_id,
                        document=f,
                        filename=pdf_filename,
                        caption=f"Factura {invoice.numero_factura}\nTotal: {format_currency(invoice.total)}"
                    )

                pdf_path.unlink(missing_ok=True)
                pdf_enviado = True

            except Exception as e:
                logger.warning(f"Error enviando PDF base64: {e}")

        # 2. Enviar HTML como archivo adjunto
        if pdf_data.html:
            try:
                html_filename = f"factura_{invoice.numero_factura}.html"
                html_path = upload_dir / html_filename

                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(pdf_data.html)

                with open(html_path, 'rb') as f:
                    await context.bot.send_document(
                        chat_id=chat_id,
                        document=f,
                        filename=html_filename,
                        caption="Vista web de la factura (abrir en navegador)"
                    )

                html_path.unlink(missing_ok=True)
                html_enviado = True

            except Exception as e:
                logger.warning(f"Error enviando HTML: {e}")

        return pdf_enviado or html_enviado

    except Exception as e:
        logger.error(f"Error enviando documentos: {e}")
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

    nuevo_nombre = update.message.text.strip()
    idx = context.user_data.get('editing_item_index', 0)
    items = context.user_data.get('items', [])

    if idx < len(items):
        items[idx]['nombre'] = nuevo_nombre
        context.user_data['items'] = items

    # Volver al menú de items
    return await _volver_menu_items(update, context)


async def editar_item_cantidad(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe nueva cantidad del item."""
    try:
        cantidad = int(update.message.text.strip())
        if cantidad < 1:
            raise ValueError()
    except ValueError:
        await update.message.reply_text(
            "Cantidad inválida.\n"
            "Escribe un número mayor a 0:"
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
    try:
        precio_str = update.message.text.strip()
        precio_str = precio_str.replace('$', '').replace(',', '').replace('.', '')
        precio = float(precio_str)
        if precio < 0:
            raise ValueError()
    except ValueError:
        await update.message.reply_text(
            "Precio inválido.\n"
            "Escribe solo números:"
        )
        return EDITAR_ITEM_PRECIO

    idx = context.user_data.get('editing_item_index', 0)
    items = context.user_data.get('items', [])

    if idx < len(items):
        items[idx]['precio'] = precio
        context.user_data['items'] = items
        _recalcular_totales(context)

    return await _volver_menu_items(update, context)


async def agregar_item_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe nombre del nuevo item."""
    nombre = update.message.text.strip()

    if len(nombre) < 2:
        await update.message.reply_text(
            "El nombre debe tener al menos 2 caracteres.\n"
            "Escribe el nombre del producto:"
        )
        return AGREGAR_ITEM

    context.user_data['new_item'] = {'nombre': nombre}

    await update.message.reply_text(
        f"Producto: {nombre}\n\n"
        "Escribe la cantidad:"
    )
    return AGREGAR_ITEM_CANTIDAD


async def agregar_item_cantidad(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe cantidad del nuevo item."""
    try:
        cantidad = int(update.message.text.strip())
        if cantidad < 1:
            raise ValueError()
    except ValueError:
        await update.message.reply_text(
            "Cantidad inválida.\n"
            "Escribe un número mayor a 0:"
        )
        return AGREGAR_ITEM_CANTIDAD

    new_item = context.user_data.get('new_item', {})
    new_item['cantidad'] = cantidad
    context.user_data['new_item'] = new_item

    await update.message.reply_text(
        f"Producto: {new_item.get('nombre')}\n"
        f"Cantidad: {cantidad}\n\n"
        "Escribe el precio unitario (solo números):"
    )
    return AGREGAR_ITEM_PRECIO


async def agregar_item_precio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe precio del nuevo item y lo agrega a la lista."""
    try:
        precio_str = update.message.text.strip()
        precio_str = precio_str.replace('$', '').replace(',', '').replace('.', '')
        precio = float(precio_str)
        if precio < 0:
            raise ValueError()
    except ValueError:
        await update.message.reply_text(
            "Precio inválido.\n"
            "Escribe solo números:"
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
        f"Item agregado: {new_item.get('nombre')}\n"
        f"Cantidad: {new_item.get('cantidad')} x {format_currency(precio)}"
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
        "ITEMS DETECTADOS\n"
        "=========================\n\n"
        f"{items_text}"
        f"SUBTOTAL: {format_currency(total)}\n"
    )

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

    await update.message.reply_text(mensaje)
    await update.message.reply_text(
        "Confirma los datos:",
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

    await update.message.reply_text(
        items_text,
        reply_markup=get_items_edit_keyboard(items)
    )

    return EDITAR_SELECCIONAR_ITEM


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