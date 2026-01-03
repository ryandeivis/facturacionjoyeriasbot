"""
Funciones de Formateo Reutilizables

Centraliza el formateo de items, clientes y métodos de pago
para evitar duplicación de código en handlers.

Sigue principios Clean Code:
- Funciones pequeñas con responsabilidad única
- Type hints en todos los parámetros
- Docstrings descriptivos
"""

from typing import List, Dict, Any, Optional
from .utils import format_currency


def format_items_list(items: List[Dict[str, Any]]) -> str:
    """
    Formatea lista de items para mostrar en mensaje de Telegram.

    Args:
        items: Lista de diccionarios con keys: nombre/descripcion, cantidad, precio

    Returns:
        String formateado con items numerados

    Example:
        >>> items = [{"nombre": "Anillo", "cantidad": 1, "precio": 500000}]
        >>> print(format_items_list(items))
        1. Anillo
           1 x $500,000 = $500,000
    """
    if not items:
        return "(Sin items)"

    lines = []
    for i, item in enumerate(items, 1):
        nombre = item.get('nombre', item.get('descripcion', 'Producto'))
        descripcion = item.get('descripcion', '')
        cantidad = item.get('cantidad', 1)
        precio = item.get('precio', item.get('precio_unitario', 0))
        subtotal = cantidad * precio

        lines.append(f"{i}. {nombre}")
        if descripcion and descripcion != nombre:
            lines.append(f"   {descripcion}")
        lines.append(f"   {cantidad} x {format_currency(precio)} = {format_currency(subtotal)}")
        lines.append("")

    return "\n".join(lines).rstrip()


def format_items_compact(items: List[Dict[str, Any]]) -> str:
    """
    Formatea items en formato compacto (una línea por item).

    Args:
        items: Lista de items

    Returns:
        String con items en formato compacto
    """
    if not items:
        return "(Sin items)"

    lines = []
    for i, item in enumerate(items, 1):
        nombre = item.get('nombre', item.get('descripcion', 'Producto'))
        cantidad = item.get('cantidad', 1)
        precio = item.get('precio', item.get('precio_unitario', 0))
        lines.append(f"{i}. {nombre} x{cantidad} - {format_currency(precio)}")

    return "\n".join(lines)


def format_cliente_info(context_data: Dict[str, Any]) -> str:
    """
    Formatea información del cliente para mostrar en mensaje.

    Args:
        context_data: Diccionario con datos del cliente (user_data del contexto)

    Returns:
        String formateado con datos del cliente
    """
    lines = []

    if context_data.get('cliente_nombre'):
        lines.append(f"👤 {context_data['cliente_nombre']}")

    if context_data.get('cliente_telefono'):
        lines.append(f"📱 {context_data['cliente_telefono']}")

    if context_data.get('cliente_cedula'):
        lines.append(f"🆔 {context_data['cliente_cedula']}")

    if context_data.get('cliente_direccion'):
        lines.append(f"📍 {context_data['cliente_direccion']}")

    if context_data.get('cliente_ciudad'):
        lines.append(f"🏙️ {context_data['cliente_ciudad']}")

    if context_data.get('cliente_email'):
        lines.append(f"📧 {context_data['cliente_email']}")

    return "\n".join(lines) if lines else "(Sin datos de cliente)"


def format_metodo_pago(context_data: Dict[str, Any]) -> str:
    """
    Formatea método de pago para mostrar en mensaje.

    Args:
        context_data: Diccionario con datos de pago

    Returns:
        String formateado con método de pago, vacío si no hay
    """
    metodo = context_data.get('metodo_pago')
    if not metodo:
        return ""

    icons = {
        'efectivo': '💵',
        'tarjeta': '💳',
        'transferencia': '🏦'
    }

    texto = f"{icons.get(metodo, '💰')} {metodo.title()}"

    if metodo == 'transferencia':
        banco = context_data.get('banco_destino')
        if banco:
            texto += f" → {banco}"

    return texto


def format_resumen_factura(
    items: List[Dict[str, Any]],
    context_data: Dict[str, Any],
    subtotal: float,
    impuesto: float,
    total: float
) -> str:
    """
    Formatea resumen completo de factura para confirmación.

    Args:
        items: Lista de items
        context_data: Datos del cliente y pago
        subtotal: Subtotal calculado
        impuesto: Impuesto calculado
        total: Total a pagar

    Returns:
        String con resumen formateado listo para enviar
    """
    lines = ["📋 *RESUMEN DE FACTURA*", ""]

    # Items
    lines.append("*Productos:*")
    lines.append(format_items_list(items))
    lines.append("")

    # Totales
    lines.append("─" * 20)
    lines.append(f"Subtotal: {format_currency(subtotal)}")
    if impuesto > 0:
        lines.append(f"IVA: {format_currency(impuesto)}")
    lines.append(f"*TOTAL: {format_currency(total)}*")
    lines.append("")

    # Cliente
    cliente_info = format_cliente_info(context_data)
    if cliente_info != "(Sin datos de cliente)":
        lines.append("*Cliente:*")
        lines.append(cliente_info)
        lines.append("")

    # Método de pago
    pago_info = format_metodo_pago(context_data)
    if pago_info:
        lines.append(f"*Pago:* {pago_info}")

    return "\n".join(lines)


def calculate_items_total(items: List[Dict[str, Any]]) -> float:
    """
    Calcula el total de una lista de items.

    Args:
        items: Lista de items con cantidad y precio

    Returns:
        Suma total de subtotales
    """
    total = 0.0
    for item in items:
        cantidad = item.get('cantidad', 1)
        precio = item.get('precio', item.get('precio_unitario', 0))
        total += cantidad * precio
    return total
