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


# Validaciones
PASSWORD_MIN_LENGTH = 8
CEDULA_MIN_LENGTH = 7
CEDULA_MAX_LENGTH = 15

# Formatos
DATE_FORMAT = "%d/%m/%Y"
DATETIME_FORMAT = "%d/%m/%Y %H:%M:%S"