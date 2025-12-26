"""
Servicio de Edición de Items

Maneja la lógica de edición de items en facturas.
Extraído de invoice.py para seguir el principio de responsabilidad única.
"""

from typing import Optional
from dataclasses import dataclass


@dataclass
class ItemEditResult:
    """Resultado de una operación de edición."""
    success: bool
    message: str
    items: list = None


class ItemEditorService:
    """Servicio para editar items de factura."""

    @staticmethod
    def update_item_field(
        items: list,
        item_index: int,
        field: str,
        value
    ) -> ItemEditResult:
        """
        Actualiza un campo específico de un item.

        Args:
            items: Lista de items
            item_index: Índice del item a modificar
            field: Campo a modificar ('nombre', 'cantidad', 'precio')
            value: Nuevo valor

        Returns:
            ItemEditResult con el resultado de la operación
        """
        if item_index < 0 or item_index >= len(items):
            return ItemEditResult(
                success=False,
                message="Índice de item inválido"
            )

        if field not in ('nombre', 'cantidad', 'precio', 'descripcion'):
            return ItemEditResult(
                success=False,
                message=f"Campo '{field}' no válido"
            )

        items[item_index][field] = value

        return ItemEditResult(
            success=True,
            message=f"Item actualizado: {field} = {value}",
            items=items
        )

    @staticmethod
    def add_item(
        items: list,
        nombre: str,
        cantidad: int,
        precio: float,
        descripcion: str = None,
        max_items: int = 6
    ) -> ItemEditResult:
        """
        Agrega un nuevo item a la lista.

        Args:
            items: Lista actual de items
            nombre: Nombre del producto
            cantidad: Cantidad
            precio: Precio unitario
            descripcion: Descripción opcional
            max_items: Máximo número de items permitidos

        Returns:
            ItemEditResult con el resultado
        """
        if len(items) >= max_items:
            return ItemEditResult(
                success=False,
                message=f"Máximo {max_items} items permitidos"
            )

        new_item = {
            'nombre': nombre,
            'cantidad': cantidad,
            'precio': precio
        }
        if descripcion:
            new_item['descripcion'] = descripcion

        items.append(new_item)

        return ItemEditResult(
            success=True,
            message=f"Item agregado: {nombre}",
            items=items
        )

    @staticmethod
    def delete_item(items: list, item_index: int) -> ItemEditResult:
        """
        Elimina un item de la lista.

        Args:
            items: Lista de items
            item_index: Índice del item a eliminar

        Returns:
            ItemEditResult con el resultado
        """
        if item_index < 0 or item_index >= len(items):
            return ItemEditResult(
                success=False,
                message="Índice de item inválido"
            )

        if len(items) <= 1:
            return ItemEditResult(
                success=False,
                message="Debe haber al menos 1 item"
            )

        deleted_item = items.pop(item_index)
        nombre = deleted_item.get('nombre', deleted_item.get('descripcion', 'Item'))

        return ItemEditResult(
            success=True,
            message=f"Item eliminado: {nombre}",
            items=items
        )

    @staticmethod
    def calculate_totals(items: list) -> dict:
        """
        Calcula subtotal y total de los items.

        Args:
            items: Lista de items

        Returns:
            Dict con subtotal y total
        """
        subtotal = sum(
            item.get('precio', 0) * item.get('cantidad', 1)
            for item in items
        )
        return {
            'subtotal': subtotal,
            'total': subtotal  # Sin impuestos aún
        }

    @staticmethod
    def validate_item_data(
        nombre: str = None,
        cantidad: int = None,
        precio: float = None
    ) -> tuple[bool, str]:
        """
        Valida datos de un item.

        Args:
            nombre: Nombre a validar
            cantidad: Cantidad a validar
            precio: Precio a validar

        Returns:
            Tuple (es_válido, mensaje_error)
        """
        if nombre is not None and len(nombre.strip()) < 2:
            return False, "El nombre debe tener al menos 2 caracteres"

        if cantidad is not None and cantidad < 1:
            return False, "La cantidad debe ser mayor a 0"

        if precio is not None and precio < 0:
            return False, "El precio no puede ser negativo"

        return True, ""

    @staticmethod
    def parse_manual_item(text: str) -> Optional[dict]:
        """
        Parsea un item ingresado manualmente.

        Formatos soportados:
        - "descripción - $precio"
        - "descripción - precio"

        Args:
            text: Texto del item

        Returns:
            Dict con datos del item o None si no se pudo parsear
        """
        try:
            if ' - $' in text:
                parts = text.rsplit(' - $', 1)
                descripcion = parts[0].strip()
                precio_str = parts[1].replace(',', '').replace('.', '')
                precio = float(precio_str)
            elif ' - ' in text:
                parts = text.rsplit(' - ', 1)
                descripcion = parts[0].strip()
                precio_str = parts[1].replace('$', '').replace(',', '').replace('.', '')
                precio = float(precio_str)
            else:
                return None

            return {
                'descripcion': descripcion,
                'nombre': descripcion,
                'cantidad': 1,
                'precio': precio
            }

        except (ValueError, IndexError):
            return None


# Instancia singleton
item_editor = ItemEditorService()