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
# GUÍAS DE ENTRADA PARA FACTURACIÓN
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


# ============================================================================
# MENSAJES DE FACTURACIÓN
# ============================================================================

MSG_SELECCIONAR_INPUT = """
NUEVA FACTURA
=============

Selecciona cómo deseas ingresar los productos:
"""

MSG_CONFIRMAR_DATOS = """
CONFIRMAR DATOS
===============

{resumen}

¿Los datos son correctos?
"""

MSG_FACTURA_GENERADA = """
FACTURA GENERADA
================

Número: {numero}
Cliente: {cliente}
Total: {total}

La factura ha sido creada exitosamente.
"""


# ============================================================================
# MENSAJES DE EDICIÓN
# ============================================================================

MSG_EDITAR_ITEM = """
EDITAR ITEM #{numero}
====================

Nombre: {nombre}
Cantidad: {cantidad}
Precio: {precio}

¿Qué campo deseas editar?
"""

MSG_INGRESA_NUEVO_VALOR = """
Ingresa el nuevo valor para {campo}:
"""

MSG_ITEM_ACTUALIZADO = """
Item actualizado correctamente.
"""


# ============================================================================
# MENSAJES DE CLIENTE
# ============================================================================

MSG_DATOS_CLIENTE = """
DATOS DEL CLIENTE
=================

Ingresa el nombre completo del cliente:
"""

MSG_CLIENTE_TELEFONO = """
Ingresa el teléfono del cliente:
"""

MSG_CLIENTE_DIRECCION = """
Ingresa la dirección del cliente:
"""

MSG_CLIENTE_CIUDAD = """
Ingresa la ciudad del cliente:
"""

MSG_CLIENTE_EMAIL = """
Ingresa el email del cliente (opcional, escribe 'skip' para omitir):
"""