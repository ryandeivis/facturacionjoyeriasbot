"""
Conexión a Base de Datos

Gestiona conexiones sync y async a SQLite (desarrollo) o PostgreSQL (producción).
Incluye connection pooling y context managers.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.pool import NullPool, QueuePool
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import AsyncGenerator, Generator, Optional

# Base para los modelos
Base = declarative_base()

# Variables globales - Sync (para migraciones y compatibilidad)
engine = None
SessionLocal = None

# Variables globales - Async (para la aplicación)
async_engine = None
AsyncSessionLocal = None


def init_db() -> None:
    """
    Inicializa la conexión sincrónica a la base de datos.
    Usado principalmente para migraciones con Alembic.
    """
    global engine, SessionLocal

    from config.settings import settings

    database_url = settings.get_sync_database_url()

    # Si es SQLite, asegurar que el directorio existe
    if "sqlite" in database_url:
        db_path = database_url.replace("sqlite:///", "")
        if db_path and not db_path.startswith(":memory:"):
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        engine = create_engine(
            database_url,
            echo=settings.DATABASE_ECHO,
            connect_args={"check_same_thread": False}
        )
    else:
        # PostgreSQL con connection pooling
        engine = create_engine(
            database_url,
            echo=settings.DATABASE_ECHO,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
            pool_recycle=settings.DATABASE_POOL_RECYCLE,
            pool_pre_ping=True
        )

    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )


def init_async_db() -> None:
    """
    Inicializa la conexión asincrónica a la base de datos.
    Usado para operaciones en la aplicación.
    """
    global async_engine, AsyncSessionLocal

    from config.settings import settings

    database_url = settings.get_async_database_url()

    # Si es SQLite async
    if "aiosqlite" in database_url:
        db_path = database_url.replace("sqlite+aiosqlite:///", "")
        if db_path and not db_path.startswith(":memory:"):
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        async_engine = create_async_engine(
            database_url,
            echo=settings.DATABASE_ECHO,
            connect_args={"check_same_thread": False}
        )
    else:
        # PostgreSQL async con connection pooling
        async_engine = create_async_engine(
            database_url,
            echo=settings.DATABASE_ECHO,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
            pool_recycle=settings.DATABASE_POOL_RECYCLE,
            pool_pre_ping=True
        )

    AsyncSessionLocal = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )


async def create_tables_async() -> None:
    """Crea todas las tablas en la base de datos (async)."""
    global async_engine

    if async_engine is None:
        init_async_db()

    # Importar modelos para registrarlos
    from src.database import models  # noqa

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def create_tables() -> None:
    """Crea todas las tablas en la base de datos (sync)."""
    global engine

    if engine is None:
        init_db()

    # Importar modelos para registrarlos
    from src.database import models  # noqa

    Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager asincrónico para sesiones de base de datos.

    Uso:
        async with get_async_db() as db:
            result = await db.execute(query)
    """
    global AsyncSessionLocal

    if AsyncSessionLocal is None:
        init_async_db()

    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


@contextmanager
def get_sync_db() -> Generator[Session, None, None]:
    """
    Context manager sincrónico para sesiones de base de datos.

    Uso:
        with get_sync_db() as db:
            result = db.query(Model).all()
    """
    global SessionLocal

    if SessionLocal is None:
        init_db()

    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """
    Generator que proporciona una sesión de base de datos.
    Mantiene compatibilidad con código existente.

    Uso:
        db = next(get_db())
        # usar db...
        db.close()
    """
    global SessionLocal

    if SessionLocal is None:
        init_db()

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def close_async_db() -> None:
    """Cierra las conexiones async de la base de datos."""
    global async_engine

    if async_engine is not None:
        await async_engine.dispose()
        async_engine = None


def close_db() -> None:
    """Cierra las conexiones sync de la base de datos."""
    global engine

    if engine is not None:
        engine.dispose()
        engine = None


class DatabaseProvider:
    """
    Proveedor de base de datos para dependency injection.

    Uso:
        db_provider = DatabaseProvider()
        async with db_provider.get_session() as session:
            ...
    """

    def __init__(self):
        self._initialized = False

    async def initialize(self) -> None:
        """Inicializa las conexiones de base de datos."""
        if not self._initialized:
            init_async_db()
            self._initialized = True

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Obtiene una sesión de base de datos."""
        if not self._initialized:
            await self.initialize()

        async with get_async_db() as session:
            yield session

    async def close(self) -> None:
        """Cierra las conexiones."""
        await close_async_db()
        self._initialized = False


# Instancia global del proveedor (para DI)
db_provider = DatabaseProvider()