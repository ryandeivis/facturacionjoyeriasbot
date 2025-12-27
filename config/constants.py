"""
Constantes del sistema

Define valores que no cambian durante la ejecución.
"""

from enum import Enum


class UserRole(str, Enum):
    """Roles de usuario en el sistema"""
    ADMIN = "ADMIN"
    VENDEDOR = "VENDEDOR"


class InvoiceStatus(str, Enum):
    """Estados posibles de una factura"""
    BORRADOR = "BORRADOR"
    PENDIENTE = "PENDIENTE"
    PAGADA = "PAGADA"
    ANULADA = "ANULADA"


class InputType(str, Enum):
    """Tipos de input para crear factura"""
    TEXTO = "TEXTO"
    VOZ = "VOZ"
    FOTO = "FOTO"


class MaterialType(str, Enum):
    """Tipos de material de joyería"""
    ORO_24K = "ORO_24K"
    ORO_18K = "ORO_18K"
    ORO_14K = "ORO_14K"
    PLATA_925 = "PLATA_925"
    PLATINO = "PLATINO"
    ACERO = "ACERO"
    OTRO = "OTRO"


class JewelryType(str, Enum):
    """Tipos de prenda de joyería"""
    ANILLO = "ANILLO"
    COLLAR = "COLLAR"
    PULSERA = "PULSERA"
    ARETES = "ARETES"
    CADENA = "CADENA"
    DIJE = "DIJE"
    RELOJ = "RELOJ"
    OTRO = "OTRO"


class AuditAction(str, Enum):
    """Acciones registradas en audit trail"""
    LOGIN_EXITOSO = "LOGIN_EXITOSO"
    LOGIN_FALLIDO = "LOGIN_FALLIDO"
    LOGOUT = "LOGOUT"
    FACTURA_CREADA = "FACTURA_CREADA"
    FACTURA_EDITADA = "FACTURA_EDITADA"
    FACTURA_PAGADA = "FACTURA_PAGADA"
    FACTURA_ANULADA = "FACTURA_ANULADA"
    USUARIO_CREADO = "USUARIO_CREADO"


# ============================================================================
# VALIDACIONES
# ============================================================================

# Autenticación
PASSWORD_MIN_LENGTH = 8

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
# FORMATOS
# ============================================================================

DATE_FORMAT = "%d/%m/%Y"
DATETIME_FORMAT = "%d/%m/%Y %H:%M:%S"