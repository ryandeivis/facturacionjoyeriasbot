"""
Servicio de Formateo de Facturas

DEPRECATED: Este módulo está obsoleto y será eliminado en futuras versiones.
Las funciones de formateo han sido movidas a:
- src/bot/handlers/shared/utils.py (format_currency, format_title_case)
- src/services/html_generator.py (generación de HTML/PDF)

Este archivo se mantiene temporalmente por compatibilidad.
Fecha de deprecación: 2026-01-01

Maneja el formateo de datos de factura para presentación.
Extraído de invoice.py para seguir el principio de responsabilidad única.
"""

import warnings

warnings.warn(
    "invoice_formatter está deprecated. Use shared/utils.py o html_generator.py",
    DeprecationWarning,
    stacklevel=2
)

from typing import Optional


def format_currency(amount: float) -> str:
    """
    Formatea un monto como moneda colombiana.

    Args:
        amount: Monto a formatear

    Returns:
        String formateado (ej: "$1,500,000")
    """
    return f"${amount:,.0f}"


def format_title_case(text: str) -> str:
    """
    Formatea texto a Title Case.

    Args:
        text: Texto a formatear

    Returns:
        Texto en Title Case
    """
    if not text:
        return text
    return text.lower().title()


class InvoiceFormatter:
    """Servicio para formatear datos de factura."""

    @staticmethod
    def format_items_summary(items: list) -> str:
        """
        Formatea lista de items para mostrar al usuario.

        Args:
            items: Lista de items

        Returns:
            String formateado con los items
        """
        if not items:
            return "No hay items"

        lines = []
        total = 0

        for i, item in enumerate(items, 1):
            nombre = item.get('nombre', item.get('descripcion', 'Producto'))
            descripcion = item.get('descripcion', '')
            cantidad = item.get('cantidad', 1)
            precio = item.get('precio', 0)
            subtotal = cantidad * precio
            total += subtotal

            lines.append(f"{i}. {nombre}")
            if descripcion and descripcion != nombre:
                lines.append(f"   {descripcion}")
            lines.append(f"   {cantidad} x {format_currency(precio)} = {format_currency(subtotal)}")
            lines.append("")

        lines.append(f"TOTAL: {format_currency(total)}")

        return "\n".join(lines)

    @staticmethod
    def format_cliente_summary(cliente: dict) -> str:
        """
        Formatea datos del cliente para mostrar.

        Args:
            cliente: Diccionario con datos del cliente

        Returns:
            String formateado con datos del cliente
        """
        if not cliente:
            return "Sin datos de cliente"

        lines = []

        if cliente.get('nombre'):
            lines.append(f"Nombre: {cliente.get('nombre')}")
        if cliente.get('telefono'):
            lines.append(f"Telefono: {cliente.get('telefono')}")
        if cliente.get('direccion'):
            lines.append(f"Direccion: {cliente.get('direccion')}")
        if cliente.get('ciudad'):
            lines.append(f"Ciudad: {cliente.get('ciudad')}")
        if cliente.get('email'):
            lines.append(f"Email: {cliente.get('email')}")
        if cliente.get('cedula'):
            lines.append(f"Cedula: {cliente.get('cedula')}")

        return "\n".join(lines) if lines else "Sin datos de cliente"

    @staticmethod
    def format_invoice_preview(
        items: list,
        cliente: dict = None,
        subtotal: float = 0,
        impuesto: float = 0,
        total: float = 0
    ) -> str:
        """
        Formatea vista previa completa de factura.

        Args:
            items: Lista de items
            cliente: Datos del cliente
            subtotal: Subtotal
            impuesto: Impuesto
            total: Total

        Returns:
            String formateado con vista previa
        """
        lines = [
            "RESUMEN DE FACTURA",
            "=" * 30,
            ""
        ]

        # Sección cliente
        if cliente:
            lines.append("CLIENTE:")
            lines.append(f"  Nombre: {cliente.get('nombre', 'N/A')}")
            if cliente.get('direccion'):
                lines.append(f"  Direccion: {cliente.get('direccion')}")
            if cliente.get('ciudad'):
                lines.append(f"  Ciudad: {cliente.get('ciudad')}")
            if cliente.get('email'):
                lines.append(f"  Email: {cliente.get('email')}")
            if cliente.get('telefono'):
                lines.append(f"  Telefono: {cliente.get('telefono')}")
            lines.append("")

        # Sección items
        lines.append("ITEMS:")
        for i, item in enumerate(items, 1):
            nombre = item.get('nombre', item.get('descripcion', 'Producto'))
            cantidad = item.get('cantidad', 1)
            precio = item.get('precio', 0)
            item_total = cantidad * precio

            lines.append(f"  {i}. {nombre}")
            lines.append(f"     {cantidad} x {format_currency(precio)} = {format_currency(item_total)}")

        lines.append("")

        # Totales
        lines.append(f"SUBTOTAL: {format_currency(subtotal)}")
        if impuesto > 0:
            lines.append(f"IVA: {format_currency(impuesto)}")
        lines.append(f"TOTAL: {format_currency(total)}")

        return "\n".join(lines)

    @staticmethod
    def format_items_for_n8n(items: list) -> list:
        """
        Formatea items con Title Case para enviar a n8n.

        Args:
            items: Lista de items sin formatear

        Returns:
            Lista de items formateados
        """
        formatted = []
        for item in items:
            formatted_item = item.copy()
            if formatted_item.get('nombre'):
                formatted_item['nombre'] = format_title_case(formatted_item['nombre'])
            if formatted_item.get('descripcion'):
                formatted_item['descripcion'] = format_title_case(formatted_item['descripcion'])
            formatted.append(formatted_item)
        return formatted

    @staticmethod
    def format_cliente_for_n8n(cliente: dict) -> dict:
        """
        Formatea datos del cliente con Title Case.

        Args:
            cliente: Datos del cliente sin formatear

        Returns:
            Datos formateados
        """
        if not cliente:
            return None

        formatted = cliente.copy()
        if formatted.get('nombre'):
            formatted['nombre'] = format_title_case(formatted['nombre'])
        if formatted.get('ciudad'):
            formatted['ciudad'] = format_title_case(formatted['ciudad'])
        return formatted


# Instancia singleton
invoice_formatter = InvoiceFormatter()