"""
Health Check de Base de Datos

Proporciona verificación de estado de la conexión a la base de datos.
Útil para monitoring, kubernetes probes y diagnóstico.
"""

from typing import Dict, Any, Optional, Union
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.pool import QueuePool

from src.database.connection import get_async_db, async_engine
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DatabaseHealth:
    """
    Servicio de health check para la base de datos.

    Proporciona métodos para verificar:
    - Conectividad básica
    - Tiempos de respuesta
    - Estado del pool de conexiones
    """

    @staticmethod
    async def check_connection() -> Dict[str, Any]:
        """
        Verifica la conexión a la base de datos.

        Returns:
            Dict con estado de la conexión
        """
        start_time = datetime.utcnow()

        try:
            async with get_async_db() as db:
                # Query simple para verificar conexión
                result = await db.execute(text("SELECT 1"))
                _ = result.scalar()

            elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000

            return {
                "status": "healthy",
                "connected": True,
                "latency_ms": round(elapsed, 2),
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error(f"Database health check failed: {e}")

            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e),
                "latency_ms": round(elapsed, 2),
                "timestamp": datetime.utcnow().isoformat()
            }

    @staticmethod
    async def get_pool_status() -> Dict[str, Any]:
        """
        Obtiene el estado del pool de conexiones.

        Returns:
            Dict con estadísticas del pool
        """
        if async_engine is None:
            return {
                "status": "not_initialized",
                "pool_size": 0,
                "checked_in": 0,
                "checked_out": 0,
                "overflow": 0
            }

        pool = async_engine.pool

        # Usar getattr con defaults para compatibilidad con diferentes tipos de Pool
        # QueuePool tiene estos métodos, pero el tipo base Pool no los expone
        return {
            "status": "active",
            "pool_size": getattr(pool, 'size', lambda: 0)(),
            "checked_in": getattr(pool, 'checkedin', lambda: 0)(),
            "checked_out": getattr(pool, 'checkedout', lambda: 0)(),
            "overflow": getattr(pool, 'overflow', lambda: 0)(),
            "invalid": getattr(pool, 'invalidatedcount', lambda: 0)()
        }

    @staticmethod
    async def get_table_stats(db: AsyncSession) -> Dict[str, Any]:
        """
        Obtiene conteo de registros por tabla principal.

        Args:
            db: Sesión de base de datos

        Returns:
            Dict con conteos por tabla (int) o error (str)
        """
        from src.database.models import Organization, User, Invoice, AuditLog

        stats = {}

        try:
            # Conteo de organizaciones
            result = await db.execute(
                text("SELECT COUNT(*) FROM organizations WHERE is_deleted = 0")
            )
            stats["organizations"] = result.scalar() or 0

            # Conteo de usuarios
            result = await db.execute(
                text("SELECT COUNT(*) FROM users WHERE is_deleted = 0")
            )
            stats["users"] = result.scalar() or 0

            # Conteo de facturas
            result = await db.execute(
                text("SELECT COUNT(*) FROM invoices WHERE is_deleted = 0")
            )
            stats["invoices"] = result.scalar() or 0

            # Conteo de audit logs
            result = await db.execute(
                text("SELECT COUNT(*) FROM audit_logs")
            )
            stats["audit_logs"] = result.scalar() or 0

        except Exception as e:
            logger.error(f"Error getting table stats: {e}")
            stats["error"] = str(e)

        return stats

    @staticmethod
    async def full_health_check() -> Dict[str, Any]:
        """
        Ejecuta un health check completo.

        Returns:
            Dict con estado completo de la base de datos
        """
        connection = await DatabaseHealth.check_connection()
        pool = await DatabaseHealth.get_pool_status()

        # Solo obtener stats si la conexión está sana
        table_stats = {}
        if connection.get("connected"):
            try:
                async with get_async_db() as db:
                    table_stats = await DatabaseHealth.get_table_stats(db)
            except Exception as e:
                table_stats = {"error": str(e)}

        return {
            "connection": connection,
            "pool": pool,
            "tables": table_stats,
            "overall_status": "healthy" if connection.get("connected") else "unhealthy"
        }


# Instancia singleton
db_health = DatabaseHealth()