"""
Alembic Migration Environment

Configura el entorno de migraciones con soporte para async.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Importar configuración y modelos
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from src.database.connection import Base
from src.database import models  # noqa: F401 - Importar para registrar modelos

# Configuración de Alembic
config = context.config

# Configurar logging desde alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata de los modelos para autogenerate
target_metadata = Base.metadata


def get_url() -> str:
    """Obtiene la URL de la base de datos desde settings."""
    return settings.get_sync_database_url()


def run_migrations_offline() -> None:
    """
    Ejecuta migraciones en modo 'offline'.

    Configura el contexto solo con una URL y no un Engine.
    Las llamadas a context.execute() emiten el SQL dado al output del script.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Ejecuta las migraciones con una conexión activa."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Ejecuta migraciones en modo async.

    Crea un Engine async y asocia una conexión con el contexto.
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    # Usar URL async
    url = settings.get_async_database_url()

    connectable = create_async_engine(
        url,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    Ejecuta migraciones en modo 'online'.

    Crea un Engine y asocia una conexión con el contexto.
    """
    from sqlalchemy import create_engine

    url = get_url()

    # Para SQLite, usar configuración especial
    if "sqlite" in url:
        connectable = create_engine(
            url,
            poolclass=pool.NullPool,
            connect_args={"check_same_thread": False}
        )
    else:
        connectable = create_engine(
            url,
            poolclass=pool.NullPool,
        )

    with connectable.connect() as connection:
        do_run_migrations(connection)

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()