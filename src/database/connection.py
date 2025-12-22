"""
Conexión a Base de Datos

Gestiona la conexión a SQLite (desarrollo) o PostgreSQL (producción).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from pathlib import Path

# Base para los modelos
Base = declarative_base()

# Variables globales
engine = None
SessionLocal = None


def init_db():
    """
    Inicializa la conexión a la base de datos.
    Usa SQLite por defecto.
    """
    global engine, SessionLocal

    from config.settings import settings

    database_url = settings.DATABASE_URL

    # Si es SQLite, asegurar que el directorio existe
    if database_url.startswith("sqlite"):
        # Extraer path del archivo
        db_path = database_url.replace("sqlite:///", "")
        if db_path:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        database_url,
        echo=settings.DATABASE_ECHO,
        connect_args={"check_same_thread": False} if "sqlite" in database_url else {}
    )

    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )

    return engine


def create_tables():
    """Crea todas las tablas en la base de datos."""
    global engine

    if engine is None:
        init_db()

    # Importar modelos para registrarlos
    from src.database import models  # noqa

    Base.metadata.create_all(bind=engine)


def get_db():
    """
    Generator que proporciona una sesión de base de datos.

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