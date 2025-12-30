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
    # Nuevas funciones con items normalizados
    create_invoice_with_items_async,
    get_invoice_with_items_async,
    update_invoice_with_items_async,
    get_invoices_by_customer_async,
)

# Queries de cliente - Sync
from src.database.queries.customer_queries import (
    get_customer_by_cedula,
    get_customer_by_id,
    get_customer_by_telefono,
    create_customer,
    search_customers,
)

# Queries de cliente - Async
from src.database.queries.customer_queries import (
    get_customer_by_cedula_async,
    get_customer_by_id_async,
    get_customer_by_telefono_async,
    create_customer_async,
    find_or_create_customer_async,
    update_customer_async,
    get_customers_by_org_async,
    search_customers_async,
    soft_delete_customer_async,
    count_customers_async,
    get_recent_customers_async,
)

# Queries de items de factura - Sync
from src.database.queries.invoice_item_queries import (
    get_item_by_id,
    get_items_by_invoice,
    create_invoice_item,
    create_invoice_items_batch,
    delete_items_by_invoice,
)

# Queries de items de factura - Async
from src.database.queries.invoice_item_queries import (
    get_item_by_id_async,
    get_items_by_invoice_async,
    create_invoice_item_async,
    create_invoice_items_async,
    update_item_async,
    delete_item_async,
    delete_items_by_invoice_async,
    replace_invoice_items_async,
    count_items_by_invoice_async,
    get_invoice_total_from_items_async,
    # Análisis de joyería
    get_items_by_material_async,
    get_items_by_tipo_prenda_async,
    get_top_selling_items_async,
    get_sales_by_material_async,
)

# Queries de borradores - Sync
from src.database.queries.draft_queries import (
    get_draft_by_id,
    get_active_draft_by_chat,
    create_draft,
    cancel_draft,
    # Constantes
    DRAFT_STATUS_ACTIVE,
    DRAFT_STATUS_COMPLETED,
    DRAFT_STATUS_CANCELLED,
    DRAFT_STATUS_EXPIRED,
    DEFAULT_EXPIRATION_HOURS,
)

# Queries de borradores - Async
from src.database.queries.draft_queries import (
    get_draft_by_id_async,
    get_active_draft_async,
    create_draft_async,
    update_draft_step_async,
    record_input_async,
    record_ai_extraction_async,
    record_user_edit_async,
    update_draft_data_async,
    finalize_draft_async,
    cancel_draft_async,
    cancel_draft_by_chat_async,
    cleanup_expired_drafts_async,
    get_drafts_by_user_async,
    get_drafts_by_org_async,
    count_drafts_async,
    get_draft_with_history_async,
)

# Queries de métricas - Sync
from src.database.queries.metrics_queries import (
    create_metric_event,
    get_recent_events,
    get_event_counts,
    get_daily_stats,
    get_hourly_distribution,
    get_organization_summary,
    get_global_summary,
    cleanup_old_events,
)

# Queries de métricas - Async
from src.database.queries.metrics_queries import (
    async_create_metric_event,
    async_get_event_counts,
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
    # Nuevas funciones con items normalizados
    'create_invoice_with_items_async',
    'get_invoice_with_items_async',
    'update_invoice_with_items_async',
    'get_invoices_by_customer_async',

    # Customer sync
    'get_customer_by_cedula',
    'get_customer_by_id',
    'get_customer_by_telefono',
    'create_customer',
    'search_customers',

    # Customer async
    'get_customer_by_cedula_async',
    'get_customer_by_id_async',
    'get_customer_by_telefono_async',
    'create_customer_async',
    'find_or_create_customer_async',
    'update_customer_async',
    'get_customers_by_org_async',
    'search_customers_async',
    'soft_delete_customer_async',
    'count_customers_async',
    'get_recent_customers_async',

    # Invoice Item sync
    'get_item_by_id',
    'get_items_by_invoice',
    'create_invoice_item',
    'create_invoice_items_batch',
    'delete_items_by_invoice',

    # Invoice Item async
    'get_item_by_id_async',
    'get_items_by_invoice_async',
    'create_invoice_item_async',
    'create_invoice_items_async',
    'update_item_async',
    'delete_item_async',
    'delete_items_by_invoice_async',
    'replace_invoice_items_async',
    'count_items_by_invoice_async',
    'get_invoice_total_from_items_async',
    # Análisis de joyería
    'get_items_by_material_async',
    'get_items_by_tipo_prenda_async',
    'get_top_selling_items_async',
    'get_sales_by_material_async',

    # Draft sync
    'get_draft_by_id',
    'get_active_draft_by_chat',
    'create_draft',
    'cancel_draft',

    # Draft async
    'get_draft_by_id_async',
    'get_active_draft_async',
    'create_draft_async',
    'update_draft_step_async',
    'record_input_async',
    'record_ai_extraction_async',
    'record_user_edit_async',
    'update_draft_data_async',
    'finalize_draft_async',
    'cancel_draft_async',
    'cancel_draft_by_chat_async',
    'cleanup_expired_drafts_async',
    'get_drafts_by_user_async',
    'get_drafts_by_org_async',
    'count_drafts_async',
    'get_draft_with_history_async',

    # Draft constantes
    'DRAFT_STATUS_ACTIVE',
    'DRAFT_STATUS_COMPLETED',
    'DRAFT_STATUS_CANCELLED',
    'DRAFT_STATUS_EXPIRED',
    'DEFAULT_EXPIRATION_HOURS',

    # Metrics sync
    'create_metric_event',
    'get_recent_events',
    'get_event_counts',
    'get_daily_stats',
    'get_hourly_distribution',
    'get_organization_summary',
    'get_global_summary',
    'cleanup_old_events',

    # Metrics async
    'async_create_metric_event',
    'async_get_event_counts',
]