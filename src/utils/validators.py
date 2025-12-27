"""
Validadores de Entrada

Módulo centralizado para validación de datos de usuario.
Diseñado para arquitectura SaaS multi-tenant.

Características:
- Validaciones reutilizables y configurables
- Soporte para límites por organización
- Mensajes de error consistentes
- Integración con logging
"""

import re
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any
from functools import lru_cache

from src.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# TIPOS DE RESULTADO
# ============================================================================

@dataclass
class ValidationResult:
    """
    Resultado de una validación.

    Attributes:
        valid: True si la validación pasó
        error: Mensaje de error (vacío si es válido)
        sanitized: Valor sanitizado (opcional)
    """
    valid: bool
    error: str = ""
    sanitized: Optional[str] = None

    def __bool__(self) -> bool:
        return self.valid


# ============================================================================
# CONSTANTES DE VALIDACIÓN
# ============================================================================

class ValidationLimits:
    """
    Límites de validación configurables.

    Pueden ser sobrescritos por configuración de tenant.
    """
    # Cédula
    CEDULA_MIN_LENGTH = 6
    CEDULA_MAX_LENGTH = 12

    # Nombres
    NOMBRE_MIN_LENGTH = 3
    NOMBRE_MAX_LENGTH = 100
    NOMBRE_PRODUCTO_MIN = 2
    NOMBRE_PRODUCTO_MAX = 150

    # Precios y cantidades
    PRECIO_MIN = 0
    PRECIO_MAX = 999_999_999  # ~1 billón COP
    CANTIDAD_MIN = 1
    CANTIDAD_MAX = 9999

    # Factura
    MAX_ITEMS_PER_INVOICE = 50
    MAX_INVOICE_TOTAL = 9_999_999_999

    # Contacto
    TELEFONO_MIN_LENGTH = 7
    TELEFONO_MAX_LENGTH = 15
    EMAIL_MAX_LENGTH = 254
    DIRECCION_MAX_LENGTH = 200

    # Texto general
    TEXT_MAX_LENGTH = 1000

    # Archivos
    MAX_FILE_SIZE_MB = 10
    MAX_VOICE_DURATION_SECONDS = 300  # 5 minutos


# ============================================================================
# VALIDADORES BASE
# ============================================================================

class BaseValidator:
    """Clase base para validadores."""

    @staticmethod
    def _ok(value: str = None) -> ValidationResult:
        """Retorna resultado válido."""
        return ValidationResult(valid=True, sanitized=value)

    @staticmethod
    def _error(message: str) -> ValidationResult:
        """Retorna resultado con error."""
        return ValidationResult(valid=False, error=message)


# ============================================================================
# VALIDADOR DE IDENTIDAD
# ============================================================================

class IdentityValidator(BaseValidator):
    """
    Validador para datos de identidad.

    Valida: cédulas, nombres de persona.
    """

    @classmethod
    def validate_cedula(
        cls,
        cedula: str,
        min_length: int = ValidationLimits.CEDULA_MIN_LENGTH,
        max_length: int = ValidationLimits.CEDULA_MAX_LENGTH
    ) -> ValidationResult:
        """
        Valida número de cédula.

        Args:
            cedula: Número de cédula a validar
            min_length: Longitud mínima
            max_length: Longitud máxima

        Returns:
            ValidationResult con estado y error si aplica
        """
        if not cedula:
            return cls._error("Cédula es requerida")

        # Sanitizar: solo dígitos
        sanitized = re.sub(r'\D', '', cedula.strip())

        if not sanitized:
            return cls._error("Solo se permiten números")

        if len(sanitized) < min_length:
            return cls._error(f"Mínimo {min_length} dígitos")

        if len(sanitized) > max_length:
            return cls._error(f"Máximo {max_length} dígitos")

        return cls._ok(sanitized)

    @classmethod
    def validate_nombre_persona(
        cls,
        nombre: str,
        min_length: int = ValidationLimits.NOMBRE_MIN_LENGTH,
        max_length: int = ValidationLimits.NOMBRE_MAX_LENGTH
    ) -> ValidationResult:
        """
        Valida nombre de persona.

        Args:
            nombre: Nombre a validar
            min_length: Longitud mínima
            max_length: Longitud máxima

        Returns:
            ValidationResult
        """
        if not nombre:
            return cls._error("Nombre es requerido")

        sanitized = nombre.strip()

        if len(sanitized) < min_length:
            return cls._error(f"Mínimo {min_length} caracteres")

        if len(sanitized) > max_length:
            return cls._error(f"Máximo {max_length} caracteres")

        # Verificar caracteres válidos (letras, espacios, guiones, apóstrofes)
        pattern = r'^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s\'\-\.]+$'
        if not re.match(pattern, sanitized):
            return cls._error("Solo letras y espacios permitidos")

        # Normalizar espacios múltiples
        sanitized = re.sub(r'\s+', ' ', sanitized)

        return cls._ok(sanitized)


# ============================================================================
# VALIDADOR DE CONTACTO
# ============================================================================

class ContactValidator(BaseValidator):
    """
    Validador para datos de contacto.

    Valida: teléfonos, emails, direcciones.
    """

    @classmethod
    def validate_telefono(
        cls,
        telefono: str,
        min_length: int = ValidationLimits.TELEFONO_MIN_LENGTH,
        max_length: int = ValidationLimits.TELEFONO_MAX_LENGTH
    ) -> ValidationResult:
        """
        Valida número de teléfono.

        Args:
            telefono: Teléfono a validar
            min_length: Longitud mínima de dígitos
            max_length: Longitud máxima de dígitos

        Returns:
            ValidationResult
        """
        if not telefono:
            return cls._ok("")  # Opcional

        # Extraer solo dígitos para validar longitud
        digits_only = re.sub(r'\D', '', telefono)

        if len(digits_only) < min_length:
            return cls._error(f"Mínimo {min_length} dígitos")

        if len(digits_only) > max_length:
            return cls._error(f"Máximo {max_length} dígitos")

        # Sanitizar: permitir dígitos, +, -, (), espacios
        sanitized = re.sub(r'[^\d+\-() ]', '', telefono.strip())

        return cls._ok(sanitized)

    @classmethod
    def validate_email(
        cls,
        email: str,
        max_length: int = ValidationLimits.EMAIL_MAX_LENGTH
    ) -> ValidationResult:
        """
        Valida dirección de email.

        Args:
            email: Email a validar
            max_length: Longitud máxima

        Returns:
            ValidationResult
        """
        if not email:
            return cls._ok("")  # Opcional

        sanitized = email.strip().lower()

        if len(sanitized) > max_length:
            return cls._error(f"Máximo {max_length} caracteres")

        # Patrón RFC 5322 simplificado
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, sanitized):
            return cls._error("Formato de email inválido")

        return cls._ok(sanitized)

    @classmethod
    def validate_direccion(
        cls,
        direccion: str,
        max_length: int = ValidationLimits.DIRECCION_MAX_LENGTH
    ) -> ValidationResult:
        """
        Valida dirección física.

        Args:
            direccion: Dirección a validar
            max_length: Longitud máxima

        Returns:
            ValidationResult
        """
        if not direccion:
            return cls._ok("")  # Opcional

        sanitized = direccion.strip()

        if len(sanitized) > max_length:
            return cls._error(f"Máximo {max_length} caracteres")

        # Normalizar espacios
        sanitized = re.sub(r'\s+', ' ', sanitized)

        return cls._ok(sanitized)


# ============================================================================
# VALIDADOR DE PRODUCTOS
# ============================================================================

class ProductValidator(BaseValidator):
    """
    Validador para datos de productos/items.

    Valida: nombres, precios, cantidades.
    """

    @classmethod
    def validate_nombre_producto(
        cls,
        nombre: str,
        min_length: int = ValidationLimits.NOMBRE_PRODUCTO_MIN,
        max_length: int = ValidationLimits.NOMBRE_PRODUCTO_MAX
    ) -> ValidationResult:
        """
        Valida nombre de producto.

        Args:
            nombre: Nombre del producto
            min_length: Longitud mínima
            max_length: Longitud máxima

        Returns:
            ValidationResult
        """
        if not nombre:
            return cls._error("Nombre de producto es requerido")

        sanitized = nombre.strip()

        if len(sanitized) < min_length:
            return cls._error(f"Mínimo {min_length} caracteres")

        if len(sanitized) > max_length:
            return cls._error(f"Máximo {max_length} caracteres")

        # Normalizar espacios
        sanitized = re.sub(r'\s+', ' ', sanitized)

        return cls._ok(sanitized)

    @classmethod
    def validate_precio(
        cls,
        precio: float,
        min_value: float = ValidationLimits.PRECIO_MIN,
        max_value: float = ValidationLimits.PRECIO_MAX
    ) -> ValidationResult:
        """
        Valida precio de producto.

        Args:
            precio: Precio a validar
            min_value: Valor mínimo
            max_value: Valor máximo

        Returns:
            ValidationResult
        """
        if precio < min_value:
            return cls._error("El precio no puede ser negativo")

        if precio > max_value:
            return cls._error(f"Precio excede el límite máximo (${max_value:,.0f})")

        return cls._ok(str(precio))

    @classmethod
    def validate_cantidad(
        cls,
        cantidad: int,
        min_value: int = ValidationLimits.CANTIDAD_MIN,
        max_value: int = ValidationLimits.CANTIDAD_MAX
    ) -> ValidationResult:
        """
        Valida cantidad de producto.

        Args:
            cantidad: Cantidad a validar
            min_value: Valor mínimo
            max_value: Valor máximo

        Returns:
            ValidationResult
        """
        if cantidad < min_value:
            return cls._error(f"Cantidad mínima es {min_value}")

        if cantidad > max_value:
            return cls._error(f"Cantidad máxima es {max_value}")

        return cls._ok(str(cantidad))

    @classmethod
    def parse_precio(cls, precio_str: str) -> Tuple[bool, float, str]:
        """
        Parsea un string de precio a float.

        Args:
            precio_str: String con el precio (ej: "$500.000", "500000")

        Returns:
            Tupla (éxito, valor, mensaje_error)
        """
        if not precio_str:
            return False, 0.0, "Precio es requerido"

        try:
            # Limpiar formato
            cleaned = precio_str.strip()
            cleaned = cleaned.replace('$', '')
            cleaned = cleaned.replace(',', '')
            cleaned = cleaned.replace('.', '')
            cleaned = cleaned.replace(' ', '')

            precio = float(cleaned)

            # Validar rango
            result = cls.validate_precio(precio)
            if not result.valid:
                return False, 0.0, result.error

            return True, precio, ""

        except ValueError:
            return False, 0.0, "Formato de precio inválido"


# ============================================================================
# VALIDADOR DE FACTURA
# ============================================================================

class InvoiceValidator(BaseValidator):
    """
    Validador para datos de factura.

    Valida: items, totales, límites.
    """

    @classmethod
    def validate_items_count(
        cls,
        count: int,
        max_items: int = ValidationLimits.MAX_ITEMS_PER_INVOICE
    ) -> ValidationResult:
        """
        Valida cantidad de items en factura.

        Args:
            count: Número de items
            max_items: Máximo permitido

        Returns:
            ValidationResult
        """
        if count == 0:
            return cls._error("La factura debe tener al menos un producto")

        if count > max_items:
            return cls._error(f"Máximo {max_items} productos por factura")

        return cls._ok()

    @classmethod
    def validate_total(
        cls,
        total: float,
        max_total: float = ValidationLimits.MAX_INVOICE_TOTAL
    ) -> ValidationResult:
        """
        Valida total de factura.

        Args:
            total: Total de la factura
            max_total: Máximo permitido

        Returns:
            ValidationResult
        """
        if total <= 0:
            return cls._error("El total debe ser mayor a cero")

        if total > max_total:
            return cls._error(f"Total excede límite (${max_total:,.0f})")

        return cls._ok()


# ============================================================================
# VALIDADOR DE ARCHIVOS
# ============================================================================

class FileValidator(BaseValidator):
    """
    Validador para archivos subidos.

    Valida: tamaño, tipo, duración (audio).
    """

    ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp'}
    ALLOWED_AUDIO_TYPES = {'audio/ogg', 'audio/mpeg', 'audio/wav'}

    @classmethod
    def validate_file_size(
        cls,
        size_bytes: int,
        max_mb: int = ValidationLimits.MAX_FILE_SIZE_MB
    ) -> ValidationResult:
        """
        Valida tamaño de archivo.

        Args:
            size_bytes: Tamaño en bytes
            max_mb: Máximo en megabytes

        Returns:
            ValidationResult
        """
        max_bytes = max_mb * 1024 * 1024

        if size_bytes > max_bytes:
            return cls._error(f"Archivo muy grande (máximo {max_mb}MB)")

        return cls._ok()

    @classmethod
    def validate_voice_duration(
        cls,
        duration_seconds: int,
        max_seconds: int = ValidationLimits.MAX_VOICE_DURATION_SECONDS
    ) -> ValidationResult:
        """
        Valida duración de audio.

        Args:
            duration_seconds: Duración en segundos
            max_seconds: Máximo permitido

        Returns:
            ValidationResult
        """
        if duration_seconds > max_seconds:
            minutes = max_seconds // 60
            return cls._error(f"Audio muy largo (máximo {minutes} minutos)")

        return cls._ok()


# ============================================================================
# SERVICIO UNIFICADO
# ============================================================================

class ValidationService:
    """
    Servicio unificado de validación.

    Punto de entrada para todas las validaciones.
    Soporta configuración por tenant para SaaS.
    """

    def __init__(self, tenant_config: Optional[Dict[str, Any]] = None):
        """
        Inicializa el servicio.

        Args:
            tenant_config: Configuración específica del tenant
        """
        self.config = tenant_config or {}
        self.identity = IdentityValidator
        self.contact = ContactValidator
        self.product = ProductValidator
        self.invoice = InvoiceValidator
        self.file = FileValidator

    def validate_cedula(self, cedula: str) -> ValidationResult:
        """Valida cédula usando config de tenant si existe."""
        min_len = self.config.get('cedula_min', ValidationLimits.CEDULA_MIN_LENGTH)
        max_len = self.config.get('cedula_max', ValidationLimits.CEDULA_MAX_LENGTH)
        return self.identity.validate_cedula(cedula, min_len, max_len)

    def validate_nombre(self, nombre: str) -> ValidationResult:
        """Valida nombre de persona."""
        return self.identity.validate_nombre_persona(nombre)

    def validate_telefono(self, telefono: str) -> ValidationResult:
        """Valida teléfono."""
        return self.contact.validate_telefono(telefono)

    def validate_email(self, email: str) -> ValidationResult:
        """Valida email."""
        return self.contact.validate_email(email)

    def validate_direccion(self, direccion: str) -> ValidationResult:
        """Valida dirección."""
        return self.contact.validate_direccion(direccion)

    def validate_producto(self, nombre: str) -> ValidationResult:
        """Valida nombre de producto."""
        return self.product.validate_nombre_producto(nombre)

    def validate_precio(self, precio: float) -> ValidationResult:
        """Valida precio."""
        max_precio = self.config.get('precio_max', ValidationLimits.PRECIO_MAX)
        return self.product.validate_precio(precio, max_value=max_precio)

    def validate_cantidad(self, cantidad: int) -> ValidationResult:
        """Valida cantidad."""
        return self.product.validate_cantidad(cantidad)

    def validate_invoice_items(self, count: int) -> ValidationResult:
        """Valida cantidad de items."""
        max_items = self.config.get('max_items', ValidationLimits.MAX_ITEMS_PER_INVOICE)
        return self.invoice.validate_items_count(count, max_items)

    def parse_precio(self, precio_str: str) -> Tuple[bool, float, str]:
        """Parsea string de precio."""
        return self.product.parse_precio(precio_str)


# ============================================================================
# SINGLETON Y HELPERS
# ============================================================================

_validation_service: Optional[ValidationService] = None


@lru_cache(maxsize=1)
def get_validation_service() -> ValidationService:
    """
    Obtiene instancia del servicio de validación.

    Returns:
        Instancia de ValidationService
    """
    return ValidationService()


def get_tenant_validation_service(tenant_config: Dict[str, Any]) -> ValidationService:
    """
    Obtiene servicio de validación con configuración de tenant.

    Args:
        tenant_config: Configuración del tenant

    Returns:
        ValidationService configurado para el tenant
    """
    return ValidationService(tenant_config)


# ============================================================================
# FUNCIONES DE CONVENIENCIA
# ============================================================================

def validar_cedula(cedula: str) -> Tuple[bool, str]:
    """
    Valida cédula (función de conveniencia).

    Args:
        cedula: Cédula a validar

    Returns:
        Tupla (es_válida, mensaje_error)
    """
    result = IdentityValidator.validate_cedula(cedula)
    return result.valid, result.error


def validar_nombre(nombre: str) -> Tuple[bool, str]:
    """
    Valida nombre (función de conveniencia).

    Args:
        nombre: Nombre a validar

    Returns:
        Tupla (es_válido, mensaje_error)
    """
    result = IdentityValidator.validate_nombre_persona(nombre)
    return result.valid, result.error


def validar_precio(precio: float) -> Tuple[bool, str]:
    """
    Valida precio (función de conveniencia).

    Args:
        precio: Precio a validar

    Returns:
        Tupla (es_válido, mensaje_error)
    """
    result = ProductValidator.validate_precio(precio)
    return result.valid, result.error


def validar_cantidad(cantidad: int) -> Tuple[bool, str]:
    """
    Valida cantidad (función de conveniencia).

    Args:
        cantidad: Cantidad a validar

    Returns:
        Tupla (es_válida, mensaje_error)
    """
    result = ProductValidator.validate_cantidad(cantidad)
    return result.valid, result.error


def validar_email(email: str) -> Tuple[bool, str]:
    """
    Valida email (función de conveniencia).

    Args:
        email: Email a validar

    Returns:
        Tupla (es_válido, mensaje_error)
    """
    result = ContactValidator.validate_email(email)
    return result.valid, result.error


def parsear_precio(precio_str: str) -> Tuple[bool, float, str]:
    """
    Parsea string de precio (función de conveniencia).

    Args:
        precio_str: String con precio

    Returns:
        Tupla (éxito, valor, mensaje_error)
    """
    return ProductValidator.parse_precio(precio_str)
