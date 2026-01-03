"""
Procesador de Datos de Cliente

Servicio modular para procesar y validar datos de clientes
extraídos de diferentes fuentes (texto, voz, foto).
"""

from typing import Optional, Dict, Any

from src.utils.logger import get_logger

logger = get_logger(__name__)


class ClientProcessor:
    """Procesa y valida datos de cliente de diferentes fuentes."""

    # Campos obligatorios para generar factura
    REQUIRED_FIELDS = ['nombre', 'cedula']

    # Campos opcionales
    OPTIONAL_FIELDS = ['telefono', 'direccion', 'ciudad', 'email']

    @staticmethod
    def process_extracted_client(
        raw_client: Dict[str, Any],
        input_type: str
    ) -> Dict[str, Any]:
        """
        Procesa cliente extraído según el tipo de input.

        Args:
            raw_client: Datos crudos del cliente
            input_type: TEXTO, VOZ o FOTO

        Returns:
            Cliente procesado con campos normalizados
        """
        processed = {
            'nombre': None,
            'cedula': None,
            'direccion': None,
            'ciudad': None,
            'email': None,
            'telefono': None,
            'cedula_detected': False  # Flag para saber si se extrajo automáticamente
        }

        if not raw_client:
            return processed

        # Copiar campos existentes
        for field in ['nombre', 'direccion', 'ciudad', 'email', 'telefono']:
            if raw_client.get(field):
                processed[field] = str(raw_client[field]).strip()

        # Procesar cédula solo para VOZ/FOTO (que usan n8n con IA)
        if input_type in ['VOZ', 'FOTO'] and raw_client.get('cedula'):
            cedula = ClientProcessor.validate_cedula(raw_client['cedula'])
            if cedula:
                processed['cedula'] = cedula
                processed['cedula_detected'] = True
                logger.info(f"Cédula extraída automáticamente: {cedula[:4]}...")

        return processed

    @staticmethod
    def validate_cedula(cedula: str) -> Optional[str]:
        """
        Valida y limpia cédula colombiana.

        Args:
            cedula: Cédula en cualquier formato

        Returns:
            Cédula limpia (solo dígitos) o None si es inválida
        """
        if not cedula:
            return None

        # Limpiar: solo dígitos
        cleaned = ''.join(c for c in str(cedula) if c.isdigit())

        # Validar longitud mínima (cédulas colombianas tienen 6-10 dígitos)
        if len(cleaned) >= 6:
            return cleaned

        logger.warning(f"Cédula inválida (muy corta): {cedula}")
        return None

    @staticmethod
    def format_checklist(cliente: Dict[str, Any], is_returning: bool = False) -> str:
        """
        Formatea checklist visual de datos del cliente.

        Indicadores:
        - ✅ Campo tiene valor
        - ❌ Campo obligatorio sin valor
        - ⬚ Campo opcional sin valor

        Args:
            cliente: Diccionario con datos del cliente
            is_returning: True si es cliente recurrente (ya existe en BD)

        Returns:
            String formateado con checklist visual
        """
        if is_returning:
            title = "🔄 CLIENTE RECURRENTE:"
        else:
            title = "🆕 CLIENTE NUEVO:"
        lines = [title, "━━━━━━━━━━━━━━━━━━━━━━━━"]

        # Campos obligatorios (✅ si existe, ❌ si falta)
        required_config = [
            ('nombre', 'Nombre'),
            ('cedula', 'Cédula'),
        ]

        # Campos opcionales (✅ si existe, ⬚ si no)
        optional_config = [
            ('telefono', 'Teléfono'),
            ('direccion', 'Dirección'),
            ('ciudad', 'Ciudad'),
            ('email', 'Email'),
        ]

        for field_key, field_label in required_config:
            value = cliente.get(field_key)
            if value:
                lines.append(f"✅ {field_label}: {value}")
            else:
                lines.append(f"❌ {field_label}: (pendiente)")

        for field_key, field_label in optional_config:
            value = cliente.get(field_key)
            if value:
                lines.append(f"✅ {field_label}: {value}")
            else:
                lines.append(f"⬚ {field_label}: (opcional)")

        return "\n".join(lines)

    @staticmethod
    def has_required_fields(cliente: Dict[str, Any]) -> bool:
        """
        Verifica si el cliente tiene todos los campos obligatorios.

        Args:
            cliente: Diccionario con datos del cliente

        Returns:
            True si tiene nombre y cédula
        """
        nombre = cliente.get('nombre')
        cedula = cliente.get('cedula')

        return bool(nombre and cedula)

    @staticmethod
    def get_missing_required_fields(cliente: Dict[str, Any]) -> list:
        """
        Obtiene lista de campos obligatorios faltantes.

        Args:
            cliente: Diccionario con datos del cliente

        Returns:
            Lista de nombres de campos faltantes
        """
        missing = []

        if not cliente.get('nombre'):
            missing.append('nombre')
        if not cliente.get('cedula'):
            missing.append('cedula')

        return missing


# Instancia singleton para uso global
client_processor = ClientProcessor()
