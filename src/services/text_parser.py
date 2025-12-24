"""
Servicio de Parsing de Texto Local

Extrae items de factura desde texto usando expresiones regulares.
Diseñado para input estructurado (listas de productos con cantidad y precio).

Arquitectura:
- Service Layer (igual que n8n_service.py)
- Retorna N8NResponse para compatibilidad con el resto del sistema
- Sin dependencias externas (no requiere API calls)

Formatos soportados:
1. "1. Cadena plata - cantidad 2 - precio $200.000"
2. "Cadena plata x2 $200000"
3. "3 cadenas a 200000"
4. "una cadena por 200000"
5. "Cadena plata 200000"
"""

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from src.models.invoice import N8NResponse
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _format_title_case(text: str) -> str:
    """
    Formatea texto a Title Case.

    Versión local para evitar import circular con handlers.
    """
    if not text:
        return text
    return text.lower().title()


@dataclass
class ParsedItem:
    """Item parseado del texto"""
    nombre: str
    descripcion: str = ""
    cantidad: int = 1
    precio: float = 0.0

    @property
    def total(self) -> float:
        return self.cantidad * self.precio

    def to_dict(self) -> Dict[str, Any]:
        return {
            "numero": 0,
            "nombre": self.nombre,
            "descripcion": self.descripcion,
            "cantidad": self.cantidad,
            "precio": self.precio,
            "total": self.total
        }


class TextParserService:
    """
    Servicio para extraer items de factura desde texto.

    Sigue el mismo patrón que N8NService para mantener
    consistencia en la arquitectura.
    """

    # Mapeo de palabras a números
    WORD_TO_NUMBER = {
        'un': 1, 'una': 1, 'uno': 1,
        'dos': 2, 'tres': 3, 'cuatro': 4,
        'cinco': 5, 'seis': 6, 'siete': 7,
        'ocho': 8, 'nueve': 9, 'diez': 10
    }

    def __init__(self):
        """Inicializa patrones regex compilados."""
        self._compile_patterns()

    def _compile_patterns(self):
        """Compila patrones regex para eficiencia."""
        self.patterns = {
            # "1. Cadena plata - cantidad 2 - precio $200.000"
            'numbered_full': re.compile(
                r'^\s*\d+[.\)]\s*'
                r'(?P<nombre>[^-\n]+?)\s*'
                r'-?\s*(?:cantidad|cant|qty|x)\s*(?P<cantidad>\d+)\s*'
                r'-?\s*(?:precio|price|\$)?\s*\$?\s*(?P<precio>[\d.,]+)',
                re.IGNORECASE | re.MULTILINE
            ),

            # "Cadena plata x2 $200000" o "Cadena plata $200000"
            'inline_price': re.compile(
                r'^(?P<nombre>[^$\d\n][^$\n]*?)\s*'
                r'(?:x\s*(?P<cantidad>\d+)\s*)?'
                r'\$\s*(?P<precio>[\d.,]+)\s*$',
                re.IGNORECASE | re.MULTILINE
            ),

            # "3 cadenas a 200000" o "2 aretes de 95000"
            'quantity_first': re.compile(
                r'^\s*(?P<cantidad>\d+)\s+'
                r'(?P<nombre>[^$\n]+?)\s*'
                r'(?:a|de|por|@)\s*'
                r'\$?\s*(?P<precio>[\d.,]+)',
                re.IGNORECASE | re.MULTILINE
            ),

            # "un anillo por 1500000" o "una cadena de 200000"
            'word_quantity': re.compile(
                r'^\s*(?P<cantidad_word>un|una|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\s+'
                r'(?P<nombre>[^$\n]+?)\s*'
                r'(?:a|de|por|@)\s*'
                r'\$?\s*(?P<precio>[\d.,]+)',
                re.IGNORECASE | re.MULTILINE
            ),

            # Fallback: "Producto 200000" (nombre seguido de número grande)
            'simple': re.compile(
                r'^(?P<nombre>[a-zA-ZáéíóúñÁÉÍÓÚÑ][^$\n]*?)\s+'
                r'(?P<precio>\d{4,})\s*$',
                re.IGNORECASE | re.MULTILINE
            ),
        }

    def parse(self, text: str) -> N8NResponse:
        """
        Parsea texto y extrae items de factura.

        Args:
            text: Texto con descripción de productos

        Returns:
            N8NResponse compatible con el flujo existente
        """
        if not text or not text.strip():
            return N8NResponse(
                success=False,
                error="Texto vacío"
            )

        # Limpiar texto
        text = self._clean_text(text)

        # Intentar parsear con cada patrón
        items = self._extract_items(text)

        if not items:
            logger.warning(f"No se pudieron extraer items del texto: {text[:100]}")
            return N8NResponse(
                success=False,
                error="No se pudieron identificar productos.\n\nFormato sugerido:\nProducto - cantidad X - precio $XXX\n\no simplemente:\nProducto $precio"
            )

        # Calcular totales
        totales = self._calculate_totals(items)

        # Formatear items para respuesta
        items_dict = []
        for i, item in enumerate(items, 1):
            item_dict = item.to_dict()
            item_dict['numero'] = i
            items_dict.append(item_dict)

        logger.info(f"Texto parseado exitosamente: {len(items)} items, total ${totales['total']:,.0f}")

        return N8NResponse(
            success=True,
            items=items_dict,
            totales=totales,
            input_type="text",
            confianza=0.9
        )

    def _clean_text(self, text: str) -> str:
        """Limpia y normaliza el texto de entrada."""
        # Normalizar saltos de línea
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        # Remover líneas vacías múltiples
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Trim
        return text.strip()

    def _extract_items(self, text: str) -> List[ParsedItem]:
        """Extrae items usando múltiples patrones."""
        all_items = []
        matched_ranges = []

        # Intentar cada patrón en orden de especificidad
        pattern_order = ['numbered_full', 'quantity_first', 'word_quantity', 'inline_price', 'simple']

        for pattern_name in pattern_order:
            pattern = self.patterns[pattern_name]
            for match in pattern.finditer(text):
                # Evitar matches superpuestos
                start, end = match.span()
                if any(start < me and end > ms for ms, me in matched_ranges):
                    continue

                item = self._match_to_item(match, pattern_name)
                if item and item.precio > 0:
                    all_items.append(item)
                    matched_ranges.append((start, end))

        # Eliminar duplicados
        items = self._deduplicate_items(all_items)

        return items

    def _match_to_item(self, match: re.Match, pattern_name: str) -> Optional[ParsedItem]:
        """Convierte un match regex a ParsedItem."""
        try:
            nombre = match.group('nombre').strip()
            # Limpiar caracteres extra
            nombre = re.sub(r'[-,;]+$', '', nombre).strip()
            nombre = _format_title_case(nombre)

            # Cantidad
            if pattern_name == 'word_quantity':
                cantidad_word = match.group('cantidad_word').lower()
                cantidad = self.WORD_TO_NUMBER.get(cantidad_word, 1)
            elif 'cantidad' in match.groupdict() and match.group('cantidad'):
                cantidad = int(match.group('cantidad'))
            else:
                cantidad = 1

            # Precio
            precio_str = match.group('precio')
            precio = self._parse_price(precio_str)

            if precio <= 0:
                return None

            return ParsedItem(
                nombre=nombre,
                cantidad=cantidad,
                precio=precio
            )
        except Exception as e:
            logger.debug(f"Error parseando match: {e}")
            return None

    def _parse_price(self, price_str: str) -> float:
        """Convierte string de precio a float."""
        if not price_str:
            return 0.0

        # Remover símbolos y espacios
        price_str = price_str.replace('$', '').replace(' ', '').strip()

        if not price_str:
            return 0.0

        # Manejar formato colombiano (1.000.000 o 1,000,000)
        if '.' in price_str and ',' not in price_str:
            parts = price_str.split('.')
            # Si tiene múltiples puntos O el último grupo tiene 3 dígitos -> separador de miles
            if len(parts) > 2 or (len(parts) == 2 and len(parts[-1]) == 3):
                price_str = price_str.replace('.', '')
        elif ',' in price_str:
            # Formato con coma: puede ser decimal o miles
            parts = price_str.split(',')
            if len(parts[-1]) == 3:
                # Es separador de miles
                price_str = price_str.replace('.', '').replace(',', '')
            else:
                # Es decimal
                price_str = price_str.replace('.', '').replace(',', '.')

        try:
            return float(price_str)
        except ValueError:
            return 0.0

    def _deduplicate_items(self, items: List[ParsedItem]) -> List[ParsedItem]:
        """Elimina items duplicados basándose en nombre y precio."""
        seen = set()
        unique = []

        for item in items:
            key = (item.nombre.lower(), item.precio)
            if key not in seen:
                seen.add(key)
                unique.append(item)

        return unique

    def _calculate_totals(self, items: List[ParsedItem]) -> Dict[str, float]:
        """Calcula subtotal y total."""
        subtotal = sum(item.total for item in items)
        return {
            "subtotal": subtotal,
            "descuento": 0.0,
            "impuesto": 0.0,
            "total": subtotal
        }


# Instancia global (singleton)
text_parser = TextParserService()