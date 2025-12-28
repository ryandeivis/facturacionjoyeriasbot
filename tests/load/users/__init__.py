# ==============================================================================
# Load Testing Users
# ==============================================================================
"""
Usuarios virtuales para pruebas de carga.

Cada clase representa un tipo de usuario con comportamiento específico:
- BaseAPIUser: Usuario base con autenticación
- VendedorUser: Vendedor creando/consultando facturas
- AdminUser: Administrador gestionando organizaciones
"""

from tests.load.users.base import BaseAPIUser
from tests.load.users.vendedor import VendedorUser
from tests.load.users.admin import AdminUser

__all__ = ["BaseAPIUser", "VendedorUser", "AdminUser"]
