"""
Constantes de Estados de Conversación

Define los estados para los flujos de conversación del bot.
Separado de shared.py para seguir el principio de responsabilidad única.
"""

from enum import IntEnum


class AuthStates(IntEnum):
    """Estados para el flujo de autenticación."""
    CEDULA = 0
    PASSWORD = 1
    MENU_PRINCIPAL = 2


class InvoiceStates(IntEnum):
    """Estados para el flujo de facturación."""
    # Estados principales
    SELECCIONAR_INPUT = 100
    RECIBIR_INPUT = 101
    CONFIRMAR_DATOS = 102
    EDITAR_ITEMS = 103

    # Estados de datos del cliente
    DATOS_CLIENTE = 104
    CLIENTE_TELEFONO = 105
    CLIENTE_CEDULA = 106
    GENERAR_FACTURA = 107
    CLIENTE_DIRECCION = 108
    CLIENTE_CIUDAD = 109
    CLIENTE_EMAIL = 110

    # Estados para edición granular de items
    EDITAR_SELECCIONAR_ITEM = 111
    EDITAR_ITEM_CAMPO = 112
    EDITAR_ITEM_NOMBRE = 113
    EDITAR_ITEM_CANTIDAD = 114
    EDITAR_ITEM_PRECIO = 115
    AGREGAR_ITEM = 116
    AGREGAR_ITEM_CANTIDAD = 117
    AGREGAR_ITEM_PRECIO = 118

    # Estado para edición de cliente desde pantalla confirmación
    EDITAR_CLIENTE_CAMPO = 119

    # Estados para método de pago
    METODO_PAGO = 120
    BANCO_ORIGEN = 121
    BANCO_DESTINO = 122

    # Estado para edición de descripción de item
    EDITAR_ITEM_DESCRIPCION = 123

    # Estados para IVA y Descuento
    APLICAR_IVA = 124
    APLICAR_DESCUENTO = 125
    MONTO_DESCUENTO = 126


# Constantes de límites
MAX_ITEMS_PER_INVOICE = 6
MAX_ITEM_NAME_LENGTH = 20

# Keys para context.user_data
INVOICE_CONTEXT_KEYS = [
    'items', 'cliente_nombre', 'cliente_telefono', 'cliente_cedula',
    'cliente_direccion', 'cliente_ciudad', 'cliente_email',
    'subtotal', 'total', 'input_type', 'input_raw', 'transcripcion',
    'manual_mode', 'n8n_response', 'cliente_detectado',
    'editing_item_index', 'editing_field', 'new_item',
    'metodo_pago', 'banco_origen', 'banco_destino', 'referencia_pago',
    'aplicar_iva', 'aplicar_descuento', 'descuento_monto'
]

# Métodos de pago válidos
METODOS_PAGO = ['efectivo', 'tarjeta', 'transferencia']

# Bancos comunes en Colombia
BANCOS_COLOMBIA = [
    'Bancolombia',
    'Davivienda',
    'BBVA',
    'Banco de Bogotá',
    'Banco Popular',
    'Banco de Occidente',
    'Nequi',
    'Daviplata',
    'Otro'
]