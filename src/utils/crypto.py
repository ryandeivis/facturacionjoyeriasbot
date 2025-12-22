"""
Utilidades de Criptografía

Funciones para hashing de contraseñas y verificación.
"""

from passlib.context import CryptContext

# Contexto de hashing con bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Genera un hash bcrypt de la contraseña.

    Args:
        password: Contraseña en texto plano

    Returns:
        Hash bcrypt de la contraseña
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica si una contraseña coincide con su hash.

    Args:
        plain_password: Contraseña en texto plano
        hashed_password: Hash bcrypt almacenado

    Returns:
        True si coinciden, False en caso contrario
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False