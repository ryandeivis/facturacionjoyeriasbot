"""
Queries de Usuario

Funciones para consultar y modificar usuarios en la base de datos.
"""

from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from src.database.models import User
from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_user_by_cedula(db: Session, cedula: str) -> Optional[User]:
    """
    Busca un usuario por su cédula.

    Args:
        db: Sesión de base de datos
        cedula: Número de cédula

    Returns:
        Usuario encontrado o None
    """
    return db.query(User).filter(User.cedula == cedula).first()


def get_user_by_telegram_id(db: Session, telegram_id: int) -> Optional[User]:
    """
    Busca un usuario por su ID de Telegram.

    Args:
        db: Sesión de base de datos
        telegram_id: ID de Telegram del usuario

    Returns:
        Usuario encontrado o None
    """
    return db.query(User).filter(User.telegram_id == telegram_id).first()


def update_last_login(db: Session, cedula: str) -> bool:
    """
    Actualiza la fecha de último login de un usuario.

    Args:
        db: Sesión de base de datos
        cedula: Cédula del usuario

    Returns:
        True si se actualizó correctamente
    """
    try:
        user = get_user_by_cedula(db, cedula)
        if user:
            user.ultimo_login = datetime.utcnow()
            db.commit()
            return True
        return False
    except Exception as e:
        logger.error(f"Error actualizando último login: {e}")
        db.rollback()
        return False


def create_user(db: Session, user_data: dict) -> Optional[User]:
    """
    Crea un nuevo usuario en la base de datos.

    Args:
        db: Sesión de base de datos
        user_data: Diccionario con datos del usuario

    Returns:
        Usuario creado o None si hubo error
    """
    try:
        user = User(**user_data)
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"Usuario creado: {user.cedula}")
        return user
    except Exception as e:
        logger.error(f"Error creando usuario: {e}")
        db.rollback()
        return None