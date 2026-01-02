"""
Mensajes del Bot

Define todos los mensajes de texto utilizados en el bot.
Separado de shared.py para seguir el principio de responsabilidad única.
"""


# ============================================================================
# MENSAJES DEL SISTEMA
# ============================================================================

MENSAJES = {
    'bienvenida': (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "       ✨ JOYERÍA ✨\n"
        "   Sistema de Facturación\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Bienvenido al sistema de facturación\n"
        "exclusivo para joyerías.\n\n"
        "📋 Ingresa tu número de cédula:"
    ),
    'no_autenticado': (
        "🔐 Sesión requerida\n\n"
        "Para continuar, inicia sesión con /start"
    ),
    'operacion_cancelada': (
        "✖ Operación cancelada\n\n"
        "¿En qué puedo ayudarte?"
    ),
    'error_conexion': (
        "⚠ Sin conexión\n\n"
        "No fue posible conectar con el servidor.\n"
        "Por favor, intenta en unos minutos."
    ),
    'sesion_cerrada': (
        "👋 ¡Hasta pronto!\n\n"
        "Tu sesión ha sido cerrada.\n"
        "Gracias por usar nuestro sistema."
    ),
    'usuario_no_encontrado': (
        "🔍 Usuario no registrado\n\n"
        "No encontramos tu cuenta en el sistema.\n"
        "Contacta al administrador para registrarte."
    ),
    'usuario_inactivo': (
        "⏸ Cuenta suspendida\n\n"
        "Tu cuenta está temporalmente inactiva.\n"
        "Contacta al administrador para más información."
    ),
    'password_incorrecta': (
        "🔑 Contraseña incorrecta\n\n"
        "Verifica tu contraseña e intenta nuevamente.\n"
        "Usa /start para reiniciar."
    ),
    'error_general': (
        "⚠ Algo salió mal\n\n"
        "Ocurrió un error inesperado.\n"
        "Por favor, intenta de nuevo."
    )
}


# ============================================================================
# GUÍAS DE ENTRADA PARA FACTURACIÓN
# ============================================================================

GUIA_INPUT_BASE = """
📝 INFORMACIÓN REQUERIDA
━━━━━━━━━━━━━━━━━━━━━━━━

Para generar tu factura necesito:

📦 PRODUCTOS
   • Nombre del producto
   • Descripción breve
   • Cantidad
   • Precio unitario

👤 CLIENTE (se solicita después)
   • Nombre completo
   • Dirección
   • Ciudad
   • Email

💡 Puedes incluir hasta 6 productos.
"""

GUIA_TEXTO = """
⌨️ INGRESO POR TEXTO
━━━━━━━━━━━━━━━━━━━━

📌 Formato recomendado:
   Joya, descripción detallada - $precio

📌 Ejemplos:

1️⃣ Anillo, oro 18k 5g con diamante 0.5ct - $2.500.000

2️⃣ Cadena, plata 925 eslabones 50cm - $180.000

3️⃣ 2 Aretes, perlas cultivadas tipo gota - $95.000

💡 La coma separa el nombre de la descripción.
   Ejemplo: "Anillo, 18k con diamante" genera:
   • Nombre: Anillo
   • Descripción: 18k con diamante
"""

GUIA_VOZ = """
🎙️ INGRESO POR VOZ
━━━━━━━━━━━━━━━━━━

Envía un mensaje de voz dictando los productos.

📌 Formato recomendado:
   "Joya coma descripción, precio X pesos"

📌 Ejemplo de lo que debes decir:

"Anillo coma oro 18 kilates con diamante,
dos millones quinientos mil pesos.

Cadena coma plata 925 eslabones 50 centímetros,
ciento ochenta mil pesos.

Dos aretes coma perlas cultivadas tipo gota,
noventa y cinco mil pesos cada uno."

💡 La palabra "coma" separa el nombre de la descripción.
   Habla claro y menciona el precio de cada ítem.
"""

GUIA_FOTO = """
📸 INGRESO POR FOTO
━━━━━━━━━━━━━━━━━━━

Envía una foto clara de:
   • Lista de productos escrita
   • Ticket o recibo
   • Cotización previa
   • Nota de pedido

📌 Formato recomendado en la foto:
   Joya, descripción - $precio

✅ Asegúrate que la imagen tenga:
   • Buena iluminación
   • Texto legible
   • Nombres y precios visibles

💡 La coma separa el nombre de la descripción.
   Evita sombras y reflejos.
"""


# ============================================================================
# MENSAJES DE FACTURACIÓN
# ============================================================================

MSG_SELECCIONAR_INPUT = """
🧾 NUEVA FACTURA
━━━━━━━━━━━━━━━━

¿Cómo deseas ingresar los productos?
"""

MSG_CONFIRMAR_DATOS = """
✅ CONFIRMAR DATOS
━━━━━━━━━━━━━━━━━━

{resumen}

¿Los datos son correctos?
"""

MSG_FACTURA_GENERADA = """
🎉 FACTURA GENERADA
━━━━━━━━━━━━━━━━━━━

📄 Número: {numero}
👤 Cliente: {cliente}
💰 Total: {total}

Tu factura ha sido creada exitosamente.
"""


# ============================================================================
# MENSAJES DE EDICIÓN
# ============================================================================

MSG_EDITAR_ITEM = """
✏️ EDITAR ÍTEM #{numero}
━━━━━━━━━━━━━━━━━━━━━━

📦 Nombre: {nombre}
🔢 Cantidad: {cantidad}
💵 Precio: {precio}

¿Qué campo deseas modificar?
"""

MSG_INGRESA_NUEVO_VALOR = """
📝 Ingresa el nuevo valor para {campo}:
"""

MSG_ITEM_ACTUALIZADO = """
✅ Ítem actualizado correctamente.
"""


# ============================================================================
# MENSAJES DE CLIENTE
# ============================================================================

MSG_DATOS_CLIENTE = """
👤 DATOS DEL CLIENTE
━━━━━━━━━━━━━━━━━━━━

Ingresa el nombre completo del cliente:
"""

MSG_CLIENTE_TELEFONO = """
📱 Ingresa el teléfono del cliente:
"""

MSG_CLIENTE_DIRECCION = """
📍 Ingresa la dirección del cliente:
"""

MSG_CLIENTE_CIUDAD = """
🏙️ Ingresa la ciudad del cliente:
"""

MSG_CLIENTE_EMAIL = """
📧 Ingresa el email del cliente
   (escribe 'skip' para omitir):
"""