"""Queries de base de datos"""
from src.database.queries.user_queries import (
    get_user_by_cedula,
    get_user_by_telegram_id,
    update_last_login,
    create_user
)
from src.database.queries.invoice_queries import (
    generate_invoice_number,
    create_invoice,
    get_invoices_by_vendedor,
    get_invoice_by_id,
    update_invoice_status
)