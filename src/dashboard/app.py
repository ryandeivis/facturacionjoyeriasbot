"""
Dashboard de Estadísticas en Tiempo Real

Dashboard interactivo con Streamlit para visualizar métricas
del sistema de facturación de joyería.

Ejecutar:
    streamlit run src/dashboard/app.py
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path
ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import time

from sqlalchemy import create_engine
from dotenv import load_dotenv
import os

from src.dashboard.queries import DashboardQueries

# Cargar variables de entorno
load_dotenv()

# Configuración de página
st.set_page_config(
    page_title="Jewelry Invoice - Dashboard",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Estilos CSS personalizados
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
    }
    div[data-testid="stMetricValue"] {
        font-size: 2rem;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_db_engine():
    """Obtiene el engine de base de datos (cacheado)."""
    database_url = os.getenv("DATABASE_URL", "sqlite:///jewelry_invoices.db")

    # Convertir URL async a sync si es necesario
    if "+asyncpg" in database_url:
        database_url = database_url.replace("+asyncpg", "")
    elif "+aiosqlite" in database_url:
        database_url = database_url.replace("+aiosqlite", "")

    # Para SQLite, agregar check_same_thread
    if "sqlite" in database_url:
        return create_engine(database_url, connect_args={"check_same_thread": False})

    return create_engine(database_url)


def format_currency(value: float) -> str:
    """Formatea un valor como moneda colombiana."""
    return f"${value:,.0f}".replace(",", ".")


def main():
    """Función principal del dashboard."""
    # Header
    st.title("💎 Jewelry Invoice - Dashboard")
    st.markdown(f"📅 Última actualización: **{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}**")

    # Obtener datos
    try:
        engine = get_db_engine()
        queries = DashboardQueries(engine)

        # Resumen general
        summary = queries.get_invoice_summary()

        # Métricas principales (KPIs)
        st.markdown("---")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                label="💰 Ingresos Hoy",
                value=format_currency(summary["ingresos_hoy"]),
                delta=f"{summary['facturas_hoy']} facturas"
            )

        with col2:
            st.metric(
                label="📦 Facturas Totales",
                value=summary["total_facturas"],
                delta=f"+{summary['facturas_semana']} esta semana"
            )

        with col3:
            clients = queries.get_clients_count()
            st.metric(
                label="👥 Clientes Únicos",
                value=clients
            )

        with col4:
            st.metric(
                label="📈 Ingresos Totales",
                value=format_currency(summary["ingresos_totales"])
            )

        # Gráficos en dos columnas
        st.markdown("---")
        col_left, col_right = st.columns(2)

        with col_left:
            # Gráfico de facturas por estado
            st.subheader("📊 Facturas por Estado")
            df_status = queries.get_invoices_by_status()

            if not df_status.empty:
                fig_status = px.pie(
                    df_status,
                    values="Cantidad",
                    names="Estado",
                    color_discrete_sequence=px.colors.qualitative.Set2,
                    hole=0.4
                )
                fig_status.update_traces(textposition='inside', textinfo='percent+label')
                fig_status.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig_status, use_container_width=True)
            else:
                st.info("No hay datos de facturas")

        with col_right:
            # Gráfico de ingresos últimos 7 días
            st.subheader("📈 Ingresos Últimos 7 Días")
            df_daily = queries.get_daily_revenue(days=7)

            if not df_daily.empty:
                fig_daily = px.line(
                    df_daily,
                    x="Fecha",
                    y="Ingresos",
                    markers=True,
                    color_discrete_sequence=["#667eea"]
                )
                fig_daily.update_layout(
                    xaxis_title="",
                    yaxis_title="Ingresos ($)",
                    margin=dict(t=0, b=0, l=0, r=0)
                )
                st.plotly_chart(fig_daily, use_container_width=True)
            else:
                st.info("No hay datos de los últimos 7 días")

        # Segunda fila de gráficos
        st.markdown("---")
        col_left2, col_right2 = st.columns(2)

        with col_left2:
            # Top vendedores
            st.subheader("🏆 Top Vendedores")
            df_sellers = queries.get_top_sellers(limit=5)

            if not df_sellers.empty:
                fig_sellers = px.bar(
                    df_sellers,
                    x="Total Ventas",
                    y="Vendedor",
                    orientation="h",
                    color="Total Ventas",
                    color_continuous_scale="Viridis"
                )
                fig_sellers.update_layout(
                    showlegend=False,
                    margin=dict(t=0, b=0, l=0, r=0),
                    yaxis={'categoryorder': 'total ascending'}
                )
                st.plotly_chart(fig_sellers, use_container_width=True)
            else:
                st.info("No hay datos de vendedores")

        with col_right2:
            # Métodos de pago
            st.subheader("💳 Métodos de Pago")
            df_payment = queries.get_payment_methods()

            if not df_payment.empty:
                fig_payment = px.pie(
                    df_payment,
                    values="Cantidad",
                    names="Método",
                    color_discrete_sequence=px.colors.qualitative.Pastel,
                    hole=0.3
                )
                fig_payment.update_traces(textposition='inside', textinfo='percent+label')
                fig_payment.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig_payment, use_container_width=True)
            else:
                st.info("No hay datos de métodos de pago")

        # Tabla de últimas facturas
        st.markdown("---")
        st.subheader("📋 Últimas 10 Facturas")
        df_recent = queries.get_recent_invoices(limit=10)

        if not df_recent.empty:
            # Formatear columnas
            df_recent["Total"] = df_recent["Total"].apply(lambda x: format_currency(x) if x else "$0")
            df_recent["Fecha"] = df_recent["Fecha"].apply(
                lambda x: x.strftime("%Y-%m-%d %H:%M") if x else ""
            )
            df_recent["Pago"] = df_recent["Pago"].fillna("Sin especificar")

            st.dataframe(
                df_recent,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Factura": st.column_config.TextColumn("Factura", width="medium"),
                    "Cliente": st.column_config.TextColumn("Cliente", width="medium"),
                    "Total": st.column_config.TextColumn("Total", width="small"),
                    "Estado": st.column_config.TextColumn("Estado", width="small"),
                    "Pago": st.column_config.TextColumn("Pago", width="small"),
                    "Fecha": st.column_config.TextColumn("Fecha", width="medium"),
                }
            )
        else:
            st.info("No hay facturas registradas")

        # Footer con información de conexión
        st.markdown("---")
        db_url = os.getenv("DATABASE_URL", "sqlite:///jewelry_invoices.db")
        db_type = "PostgreSQL (Supabase)" if "postgresql" in db_url else "SQLite (Local)"
        st.caption(f"🔗 Conectado a: **{db_type}** | Auto-refresh: 10 segundos")

    except Exception as e:
        st.error(f"Error al conectar con la base de datos: {str(e)}")
        st.info("Verifica que la base de datos esté disponible y la URL sea correcta.")
        return


if __name__ == "__main__":
    # Auto-refresh cada 10 segundos
    main()
    time.sleep(10)
    st.rerun()
