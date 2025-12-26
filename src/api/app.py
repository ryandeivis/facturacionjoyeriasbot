"""
FastAPI Application

Aplicación principal de la API REST.
Incluye todos los routers y configuración.
"""

from typing import Optional
from datetime import datetime

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Intentar importar FastAPI
try:
    from fastapi import FastAPI, Request, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    logger.warning("FastAPI no instalado. API REST no disponible.")


def create_app() -> Optional["FastAPI"]:
    """
    Crea y configura la aplicación FastAPI.

    Returns:
        Aplicación FastAPI o None si no está disponible
    """
    if not FASTAPI_AVAILABLE:
        return None

    from config.settings import settings

    # Crear aplicación
    app = FastAPI(
        title="Jewelry Invoice Bot API",
        description="API REST para el sistema de facturación de joyería",
        version=settings.VERSION,
        docs_url="/docs" if settings.ENVIRONMENT.value != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT.value != "production" else None,
    )

    # Configurar CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # En producción, especificar dominios
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # =========================================================================
    # MIDDLEWARE
    # =========================================================================

    @app.middleware("http")
    async def add_request_context(request: Request, call_next):
        """Agrega contexto a cada request."""
        from src.utils.logger import new_correlation_id, clear_context

        # Generar correlation ID
        correlation_id = request.headers.get("X-Correlation-ID") or new_correlation_id()

        # Procesar request
        start_time = datetime.utcnow()
        response = await call_next(request)
        duration = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Agregar headers de respuesta
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Response-Time"] = f"{duration:.2f}ms"

        # Limpiar contexto
        clear_context()

        return response

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """Loggea todas las requests."""
        logger.info(f"{request.method} {request.url.path}")
        response = await call_next(request)
        return response

    # =========================================================================
    # ERROR HANDLERS
    # =========================================================================

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Maneja excepciones no capturadas."""
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "message": str(exc) if settings.ENVIRONMENT.value != "production" else "Error interno",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Maneja HTTPExceptions."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "status_code": exc.status_code,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        )

    # =========================================================================
    # ROUTERS
    # =========================================================================

    # Health
    from src.api.health import health_router
    if health_router:
        app.include_router(health_router)

    # Metrics
    from src.api.metrics import metrics_router
    if metrics_router:
        app.include_router(metrics_router)

    # Organizations
    from src.api.organizations import organizations_router
    if organizations_router:
        app.include_router(organizations_router, prefix="/api/v1")

    # Invoices
    from src.api.invoices import invoices_router
    if invoices_router:
        app.include_router(invoices_router, prefix="/api/v1")

    # =========================================================================
    # ROOT ENDPOINT
    # =========================================================================

    @app.get("/")
    async def root():
        """Endpoint raíz."""
        return {
            "name": "Jewelry Invoice Bot API",
            "version": settings.VERSION,
            "status": "running",
            "docs": "/docs" if settings.ENVIRONMENT.value != "production" else None
        }

    @app.get("/api/v1")
    async def api_info():
        """Información de la API."""
        return {
            "version": "1.0.0",
            "endpoints": {
                "health": "/health",
                "metrics": "/metrics",
                "organizations": "/api/v1/organizations",
                "invoices": "/api/v1/invoices"
            }
        }

    # =========================================================================
    # STARTUP/SHUTDOWN
    # =========================================================================

    @app.on_event("startup")
    async def startup():
        """Inicialización al arrancar."""
        logger.info("API iniciando...")
        # Inicializar DB si es necesario
        from src.database.connection import init_async_db
        init_async_db()
        logger.info("API lista")

    @app.on_event("shutdown")
    async def shutdown():
        """Limpieza al cerrar."""
        logger.info("API cerrando...")
        from src.database.connection import close_async_db
        await close_async_db()
        logger.info("API cerrada")

    return app


# Crear instancia de la aplicación
app = create_app()


def run_api(host: str = "0.0.0.0", port: int = 8000):
    """
    Ejecuta el servidor de la API.

    Args:
        host: Host para escuchar
        port: Puerto para escuchar
    """
    if not FASTAPI_AVAILABLE:
        logger.error("FastAPI no está instalado. Instálalo con: pip install fastapi uvicorn")
        return

    import uvicorn

    logger.info(f"Iniciando API en http://{host}:{port}")
    uvicorn.run(
        "src.api.app:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )


if __name__ == "__main__":
    run_api()