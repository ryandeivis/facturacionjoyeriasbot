"""
Pytest Configuration and Fixtures

Configuración global de pytest y fixtures compartidos.
"""

import os
import sys
import asyncio
from pathlib import Path
from typing import AsyncGenerator, Generator
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Agregar el directorio raíz al path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.connection import Base
from src.database.models import Organization, User, Invoice, TenantConfig
from src.utils.crypto import hash_password


# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================

def pytest_configure(config):
    """Configuración de pytest."""
    # Establecer entorno de test
    os.environ["ENVIRONMENT"] = "development"
    os.environ["DATABASE_URL"] = "sqlite:///test.db"
    os.environ["TELEGRAM_BOT_TOKEN"] = "test_token"
    os.environ["SECRET_KEY"] = "test_secret_key_for_testing_only"


@pytest.fixture(scope="session")
def event_loop():
    """Crea un event loop para tests async."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# DATABASE FIXTURES
# ============================================================================

@pytest.fixture(scope="function")
def sync_engine():
    """Crea un engine de base de datos en memoria para tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(sync_engine) -> Generator[Session, None, None]:
    """Proporciona una sesión de base de datos para tests."""
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=sync_engine
    )
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function")
async def async_engine():
    """Crea un engine async de base de datos en memoria."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()


@pytest.fixture(scope="function")
async def async_db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Proporciona una sesión async de base de datos para tests."""
    AsyncSessionLocal = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()


# ============================================================================
# SAMPLE DATA FIXTURES
# ============================================================================

@pytest.fixture
def sample_organization() -> dict:
    """Datos de una organización de ejemplo."""
    return {
        "id": "org-test-123",
        "name": "Joyería Test",
        "slug": "joyeria-test",
        "plan": "basic",
        "status": "active",
        "email": "test@joyeria.com",
        "telefono": "3001234567",
    }


@pytest.fixture
def sample_user(sample_organization) -> dict:
    """Datos de un usuario de ejemplo."""
    return {
        "organization_id": sample_organization["id"],
        "cedula": "123456789",
        "nombre_completo": "Usuario Test",
        "email": "usuario@test.com",
        "telefono": "3009876543",
        "password_hash": hash_password("Test123!"),
        "rol": "VENDEDOR",
        "activo": True,
    }


@pytest.fixture
def sample_invoice(sample_organization, sample_user) -> dict:
    """Datos de una factura de ejemplo."""
    return {
        "id": "inv-test-123",
        "organization_id": sample_organization["id"],
        "numero_factura": "FAC-202412-0001",
        "cliente_nombre": "Cliente Test",
        "cliente_telefono": "3001112222",
        "cliente_cedula": "987654321",
        "items": '[{"descripcion": "Anillo oro", "cantidad": 1, "precio": 500000}]',
        "subtotal": 500000.0,
        "descuento": 0.0,
        "impuesto": 95000.0,
        "total": 595000.0,
        "estado": "BORRADOR",
        "vendedor_id": 1,
    }


@pytest.fixture
def db_with_sample_data(db_session, sample_organization, sample_user) -> Session:
    """Proporciona una sesión con datos de ejemplo."""
    # Crear organización
    org = Organization(**sample_organization)
    db_session.add(org)
    db_session.commit()

    # Crear config de tenant
    config = TenantConfig(
        organization_id=org.id,
        invoice_prefix="FAC",
        tax_rate=0.19,
        currency="COP",
    )
    db_session.add(config)

    # Crear usuario
    user = User(**sample_user)
    db_session.add(user)
    db_session.commit()

    return db_session


@pytest.fixture
async def async_db_with_sample_data(
    async_db_session,
    sample_organization,
    sample_user
) -> AsyncSession:
    """Proporciona una sesión async con datos de ejemplo."""
    # Crear organización
    org = Organization(**sample_organization)
    async_db_session.add(org)
    await async_db_session.commit()

    # Crear config de tenant
    config = TenantConfig(
        organization_id=org.id,
        invoice_prefix="FAC",
        tax_rate=0.19,
        currency="COP",
    )
    async_db_session.add(config)

    # Crear usuario
    user = User(**sample_user)
    async_db_session.add(user)
    await async_db_session.commit()

    return async_db_session


# ============================================================================
# MOCK FIXTURES
# ============================================================================

@pytest.fixture
def mock_telegram_update():
    """Mock de un Update de Telegram."""
    update = MagicMock()
    update.effective_user.id = 123456789
    update.effective_user.username = "test_user"
    update.effective_chat.id = 123456789
    update.message.text = "/start"
    update.message.reply_text = AsyncMock()
    return update


@pytest.fixture
def mock_telegram_context():
    """Mock del contexto de Telegram."""
    context = MagicMock()
    context.user_data = {}
    context.bot_data = {}
    return context


@pytest.fixture
def mock_n8n_service():
    """Mock del servicio N8N."""
    service = MagicMock()
    service.send_text_input = AsyncMock(return_value={
        "success": True,
        "data": {
            "items": [{"descripcion": "Anillo", "cantidad": 1, "precio": 500000}],
            "cliente": "Cliente Test",
        }
    })
    service.send_voice_input = AsyncMock(return_value={"success": True})
    service.send_photo_input = AsyncMock(return_value={"success": True})
    return service


@pytest.fixture
def mock_app_context(mock_n8n_service, db_session):
    """Mock del contexto de aplicación."""
    from src.core.context import AppContext

    mock_db = MagicMock()
    mock_db.get_session = MagicMock(return_value=db_session)

    return AppContext.create_for_testing(
        mock_db=mock_db,
        mock_n8n=mock_n8n_service,
    )


# ============================================================================
# HELPER FIXTURES
# ============================================================================

@pytest.fixture
def authenticated_context(mock_telegram_context, sample_user, sample_organization):
    """Contexto de Telegram autenticado."""
    mock_telegram_context.user_data = {
        'autenticado': True,
        'cedula': sample_user["cedula"],
        'nombre': sample_user["nombre_completo"],
        'rol': sample_user["rol"],
        'user_id': 1,
        'organization_id': sample_organization["id"],
        'telegram_id': 123456789,
    }
    return mock_telegram_context


# ============================================================================
# CLEANUP FIXTURES
# ============================================================================

@pytest.fixture(autouse=True)
def cleanup_logs():
    """Limpia archivos de log después de cada test."""
    yield
    # Los logs se limpian automáticamente con la base de datos en memoria


@pytest.fixture(autouse=True)
def reset_singletons():
    """Resetea singletons entre tests."""
    yield
    # Resetear cualquier singleton si es necesario
    from src.utils.crypto import _crypto_service
    import src.utils.crypto
    src.utils.crypto._crypto_service = None