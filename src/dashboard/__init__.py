"""
Dashboard de Estadísticas en Tiempo Real

Módulo Streamlit para visualización de métricas del sistema de facturación.
Conecta directamente a la base de datos y muestra datos actualizados.

Ejecutar:
    streamlit run src/dashboard/app.py
"""

from .queries import DashboardQueries

__all__ = ["DashboardQueries"]
