"""
Handlers de Autenticación

Maneja el flujo de login, logout y gestión de sesión.
"""

from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

from src.utils.logger import get_logger
from src.utils.crypto import verify_password
from src.database.connection import get_db, init_db, create_tables
from src.database.queries.user_queries import get_user_by_cedula, update_last_login
from src.database.queries.invoice_queries import get_invoices_by_vendedor
from src.bot.handlers.shared import (
    AuthStates,
    get_menu_keyboard,
    limpiar_sesion,
    format_invoice_status,
    format_currency,
    MENSAJES
)
from config.constants import UserRole

logger = get_logger(__name__)

# Estados de la conversación (aliases para compatibilidad)
CEDULA = AuthStates.CEDULA
PASSWORD = AuthStates.PASSWORD
MENU_PRINCIPAL = AuthStates.MENU_PRINCIPAL

# Inicializar base de datos al importar
try:
    init_db()
    create_tables()
    logger.info("Base de datos inicializada correctamente")
except Exception as e:
    logger.warning(f"No se pudo inicializar base de datos: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Comando /start - Inicio del bot"""
    user = update.effective_user

    logger.info(f"Usuario Telegram {user.id} inició el bot")

    await update.message.reply_text(MENSAJES['bienvenida'])

    return CEDULA


async def recibir_cedula(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe y valida la cédula"""
    cedula = update.message.text.strip()

    # Validar que solo contenga números
    if not cedula.isdigit():
        await update.message.reply_text(
            "Cédula inválida. Solo números.\n\n"
            "Ingresa tu cédula:"
        )
        return CEDULA

    # Buscar usuario en base de datos
    try:
        db = next(get_db())
        usuario = get_user_by_cedula(db, cedula)
        db.close()

        if not usuario:
            await update.message.reply_text(MENSAJES['usuario_no_encontrado'])
            logger.warning(f"Intento de login con cédula inexistente: {cedula}")
            return ConversationHandler.END

        if not usuario.activo:
            await update.message.reply_text(MENSAJES['usuario_inactivo'])
            logger.warning(f"Intento de login en usuario inactivo: {cedula}")
            return ConversationHandler.END

        # Guardar datos en contexto
        context.user_data['cedula'] = cedula
        context.user_data['user_id'] = usuario.id
        context.user_data['nombre'] = usuario.nombre_completo
        context.user_data['rol'] = usuario.rol
        context.user_data['password_hash'] = usuario.password_hash
        context.user_data['organization_id'] = usuario.organization_id

        await update.message.reply_text(
            f"Hola {usuario.nombre_completo}\n\n"
            "Ingresa tu contraseña:"
        )

        return PASSWORD

    except Exception as e:
        logger.error(f"Error al buscar usuario: {e}")
        await update.message.reply_text(MENSAJES['error_conexion'])
        return ConversationHandler.END


async def recibir_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe y valida la contraseña"""
    password = update.message.text
    cedula = context.user_data.get('cedula')
    password_hash = context.user_data.get('password_hash')

    # Borrar mensaje con password por seguridad
    try:
        await update.message.delete()
    except Exception:
        pass

    # Verificar contraseña
    if not verify_password(password, password_hash):
        await update.message.reply_text(MENSAJES['password_incorrecta'])
        logger.warning(f"Contraseña incorrecta para usuario: {cedula}")
        limpiar_sesion(context)
        return ConversationHandler.END

    # Actualizar último login
    try:
        db = next(get_db())
        update_last_login(db, cedula)
        db.close()
    except Exception as e:
        logger.error(f"Error al actualizar último login: {e}")

    logger.info(f"Login exitoso: {cedula}")

    context.user_data['autenticado'] = True

    # Mostrar menú según rol
    nombre = context.user_data.get('nombre')
    rol = context.user_data.get('rol')

    markup = get_menu_keyboard(rol)

    await update.message.reply_text(
        f"Autenticación exitosa\n\n"
        f"Bienvenido, {nombre}\n\n"
        f"¿Qué deseas hacer?",
        reply_markup=markup
    )

    return MENU_PRINCIPAL


async def menu_principal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja las opciones del menú principal"""
    opcion = update.message.text

    if '1.' in opcion or 'Nueva Factura' in opcion:
        # Importar aquí para evitar circular import en el flujo
        from src.bot.handlers.invoice import iniciar_nueva_factura
        return await iniciar_nueva_factura(update, context)

    elif '2.' in opcion or 'Mis Facturas' in opcion:
        await mostrar_mis_facturas(update, context)
        return MENU_PRINCIPAL

    elif '3.' in opcion or 'Buscar' in opcion:
        await update.message.reply_text(
            "BUSCAR FACTURA\n\n"
            "Esta función estará disponible próximamente."
        )
        return MENU_PRINCIPAL

    elif '4.' in opcion or 'Crear Usuario' in opcion:
        rol = context.user_data.get('rol')
        if rol == UserRole.ADMIN.value:
            await update.message.reply_text(
                "CREAR USUARIO\n\n"
                "Esta función estará disponible próximamente."
            )
        else:
            await update.message.reply_text(
                "No tienes permisos para esta acción."
            )
        return MENU_PRINCIPAL

    elif 'Cerrar' in opcion:
        await update.message.reply_text(
            MENSAJES['sesion_cerrada'],
            reply_markup=ReplyKeyboardRemove()
        )
        limpiar_sesion(context)
        return ConversationHandler.END

    # Si no coincide con ninguna opción, mostrar menú de nuevo
    rol = context.user_data.get('rol')
    markup = get_menu_keyboard(rol)
    await update.message.reply_text(
        "Opción no reconocida. Selecciona una opción:",
        reply_markup=markup
    )
    return MENU_PRINCIPAL


async def mostrar_mis_facturas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra las facturas del vendedor actual"""
    user_id = context.user_data.get('user_id')
    org_id = context.user_data.get('organization_id')

    try:
        db = next(get_db())
        facturas = get_invoices_by_vendedor(db, user_id, org_id, limit=10)
        db.close()

        if not facturas:
            await update.message.reply_text(
                "MIS FACTURAS\n\n"
                "No tienes facturas registradas aún."
            )
            return

        mensaje = "MIS FACTURAS (últimas 10)\n"
        mensaje += "=" * 30 + "\n\n"

        for f in facturas:
            estado_formatted = format_invoice_status(f.estado)
            mensaje += f"{estado_formatted}\n"
            mensaje += f"   No: {f.numero_factura}\n"
            mensaje += f"   Cliente: {f.cliente_nombre}\n"
            mensaje += f"   Total: {format_currency(f.total)}\n"
            mensaje += f"   Fecha: {f.created_at.strftime('%d/%m/%Y')}\n\n"

        await update.message.reply_text(mensaje)

    except Exception as e:
        logger.error(f"Error obteniendo facturas: {e}")
        await update.message.reply_text(
            "Error al obtener facturas.\n"
            "Intenta más tarde."
        )


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Comando /cancel"""
    await update.message.reply_text(
        "Operación cancelada.",
        reply_markup=ReplyKeyboardRemove()
    )
    limpiar_sesion(context)
    return ConversationHandler.END


def get_auth_conversation_handler() -> ConversationHandler:
    """Retorna el ConversationHandler de autenticación"""
    return ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CEDULA: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_cedula)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_password)],
            MENU_PRINCIPAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, menu_principal)]
        },
        fallbacks=[CommandHandler('cancel', cancelar)]
    )