"""
Queries de Base de Datos

Módulo que exporta todas las funciones de consulta a la base de datos.
Incluye operaciones sync (compatibilidad) y async (recomendado).
"""

# Clase base para queries
from src.database.queries.base import BaseQuery

# Queries de usuario - Sync
from src.database.queries.user_queries import (
    get_user_by_cedula,
    get_user_by_telegram_id,
    update_last_login,
    create_user,
)

# Queries de usuario - Async
from src.database.queries.user_queries import (
    get_user_by_cedula_async,
    get_user_by_telegram_id_async,
    get_user_by_id_async,
    update_last_login_async,
    create_user_async,
    get_users_by_org_async,
    soft_delete_user_async,
)

# Queries de factura - Sync
from src.database.queries.invoice_queries import (
    generate_invoice_number,
    create_invoice,
    get_invoices_by_vendedor,
    get_invoice_by_id,
    get_invoice_by_number,
    update_invoice_status,
)

# Queries de factura - Async
from src.database.queries.invoice_queries import (
    generate_invoice_number_async,
    create_invoice_async,
    get_invoice_by_id_async,
    get_invoice_by_number_async,
    get_invoices_by_vendedor_async,
    get_invoices_by_org_async,
    update_invoice_status_async,
    soft_delete_invoice_async,
    get_invoice_stats_async,
)

__all__ = [
    # Base
    'BaseQuery',
    # User sync
    'get_user_by_cedula',
    'get_user_by_telegram_id',
    'update_last_login',
    'create_user',
    # User async
    'get_user_by_cedula_async',
    'get_user_by_telegram_id_async',
    'get_user_by_id_async',
    'update_last_login_async',
    'create_user_async',
    'get_users_by_org_async',
    'soft_delete_user_async',
    # Invoice sync
    'generate_invoice_number',
    'create_invoice',
    'get_invoices_by_vendedor',
    'get_invoice_by_id',
    'get_invoice_by_number',
    'update_invoice_status',
    # Invoice async
    'generate_invoice_number_async',
    'create_invoice_async',
    'get_invoice_by_id_async',
    'get_invoice_by_number_async',
    'get_invoices_by_vendedor_async',
    'get_invoices_by_org_async',
    'update_invoice_status_async',
    'soft_delete_invoice_async',
    'get_invoice_stats_async',
]