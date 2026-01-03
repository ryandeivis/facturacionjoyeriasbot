"""
Queries SQL para el Dashboard

Proporciona consultas optimizadas para obtener métricas en tiempo real.
Compatible con SQLite y PostgreSQL.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine


class DashboardQueries:
    """Queries para métricas del dashboard."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def get_invoice_summary(self) -> Dict[str, Any]:
        """Obtiene resumen general de facturas."""
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        query = text("""
            SELECT
                COUNT(*) as total,
                COALESCE(SUM(total), 0) as ingresos_totales,
                COUNT(CASE WHEN DATE(created_at) = :today THEN 1 END) as facturas_hoy,
                COALESCE(SUM(CASE WHEN DATE(created_at) = :today THEN total ELSE 0 END), 0) as ingresos_hoy,
                COUNT(CASE WHEN DATE(created_at) >= :week_ago THEN 1 END) as facturas_semana,
                COALESCE(SUM(CASE WHEN DATE(created_at) >= :week_ago THEN total ELSE 0 END), 0) as ingresos_semana,
                COUNT(CASE WHEN DATE(created_at) >= :month_ago THEN 1 END) as facturas_mes,
                COALESCE(SUM(CASE WHEN DATE(created_at) >= :month_ago THEN total ELSE 0 END), 0) as ingresos_mes
            FROM invoices
            WHERE is_deleted = false
        """)

        with self.engine.connect() as conn:
            result = conn.execute(query, {
                "today": str(today),
                "week_ago": str(week_ago),
                "month_ago": str(month_ago)
            }).fetchone()

        return {
            "total_facturas": result[0] or 0,
            "ingresos_totales": result[1] or 0,
            "facturas_hoy": result[2] or 0,
            "ingresos_hoy": result[3] or 0,
            "facturas_semana": result[4] or 0,
            "ingresos_semana": result[5] or 0,
            "facturas_mes": result[6] or 0,
            "ingresos_mes": result[7] or 0,
        }

    def get_invoices_by_status(self) -> pd.DataFrame:
        """Obtiene conteo de facturas por estado."""
        query = text("""
            SELECT
                estado,
                COUNT(*) as cantidad,
                COALESCE(SUM(total), 0) as monto
            FROM invoices
            WHERE is_deleted = 0
            GROUP BY estado
            ORDER BY cantidad DESC
        """)

        with self.engine.connect() as conn:
            result = conn.execute(query).fetchall()

        return pd.DataFrame(result, columns=["Estado", "Cantidad", "Monto"])

    def get_payment_methods(self) -> pd.DataFrame:
        """Obtiene distribución de métodos de pago."""
        query = text("""
            SELECT
                COALESCE(metodo_pago, 'Sin especificar') as metodo,
                COUNT(*) as cantidad,
                COALESCE(SUM(total), 0) as monto
            FROM invoices
            WHERE is_deleted = 0
            GROUP BY metodo_pago
            ORDER BY cantidad DESC
        """)

        with self.engine.connect() as conn:
            result = conn.execute(query).fetchall()

        return pd.DataFrame(result, columns=["Método", "Cantidad", "Monto"])

    def get_daily_revenue(self, days: int = 7) -> pd.DataFrame:
        """Obtiene ingresos diarios de los últimos N días."""
        start_date = datetime.now().date() - timedelta(days=days)

        query = text("""
            SELECT
                DATE(created_at) as fecha,
                COUNT(*) as facturas,
                COALESCE(SUM(total), 0) as ingresos
            FROM invoices
            WHERE is_deleted = 0
              AND DATE(created_at) >= :start_date
            GROUP BY DATE(created_at)
            ORDER BY fecha
        """)

        with self.engine.connect() as conn:
            result = conn.execute(query, {"start_date": str(start_date)}).fetchall()

        return pd.DataFrame(result, columns=["Fecha", "Facturas", "Ingresos"])

    def get_top_sellers(self, limit: int = 5) -> pd.DataFrame:
        """Obtiene los vendedores con más ventas."""
        query = text("""
            SELECT
                u.nombre_completo as vendedor,
                COUNT(i.id) as facturas,
                COALESCE(SUM(i.total), 0) as total_ventas
            FROM invoices i
            JOIN users u ON i.vendedor_id = u.id
            WHERE i.is_deleted = false
            GROUP BY u.id, u.nombre_completo
            ORDER BY total_ventas DESC
            LIMIT :limit
        """)

        with self.engine.connect() as conn:
            result = conn.execute(query, {"limit": limit}).fetchall()

        return pd.DataFrame(result, columns=["Vendedor", "Facturas", "Total Ventas"])

    def get_recent_invoices(self, limit: int = 10) -> pd.DataFrame:
        """Obtiene las últimas facturas."""
        query = text("""
            SELECT
                numero_factura,
                cliente_nombre,
                total,
                estado,
                metodo_pago,
                created_at
            FROM invoices
            WHERE is_deleted = 0
            ORDER BY created_at DESC
            LIMIT :limit
        """)

        with self.engine.connect() as conn:
            result = conn.execute(query, {"limit": limit}).fetchall()

        return pd.DataFrame(
            result,
            columns=["Factura", "Cliente", "Total", "Estado", "Pago", "Fecha"]
        )

    def get_hourly_distribution(self) -> pd.DataFrame:
        """Obtiene distribución de facturas por hora del día."""
        # PostgreSQL usa EXTRACT
        query = text("""
            SELECT
                EXTRACT(HOUR FROM created_at)::INTEGER as hora,
                COUNT(*) as facturas
            FROM invoices
            WHERE is_deleted = false
            GROUP BY EXTRACT(HOUR FROM created_at)
            ORDER BY hora
        """)

        with self.engine.connect() as conn:
            result = conn.execute(query).fetchall()

        return pd.DataFrame(result, columns=["Hora", "Facturas"])

    def get_clients_count(self) -> int:
        """Obtiene el número de clientes únicos."""
        query = text("""
            SELECT COUNT(DISTINCT cliente_cedula)
            FROM invoices
            WHERE is_deleted = false
              AND cliente_cedula IS NOT NULL
              AND cliente_cedula != ''
        """)

        with self.engine.connect() as conn:
            result = conn.execute(query).scalar()

        return result or 0

    def get_metric_events_summary(self) -> Dict[str, int]:
        """Obtiene resumen de eventos de métricas."""
        query = text("""
            SELECT
                event_type,
                COUNT(*) as cantidad
            FROM metric_events
            GROUP BY event_type
            ORDER BY cantidad DESC
            LIMIT 10
        """)

        with self.engine.connect() as conn:
            result = conn.execute(query).fetchall()

        return {row[0]: row[1] for row in result}
