"""
Utilidades de Criptografía

Funciones para:
- Hashing de contraseñas (bcrypt)
- JWT tokens
- Encriptación de PII (datos personales)
- Sanitización de inputs
"""

import re
import base64
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from functools import lru_cache

from passlib.context import CryptContext

# Importación condicional de jwt
try:
    import jwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False

# Importación condicional de cryptography
try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Contexto de hashing con bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ============================================================================
# PASSWORD HASHING
# ============================================================================

def hash_password(password: str) -> str:
    """
    Genera un hash bcrypt de la contraseña.

    Args:
        password: Contraseña en texto plano

    Returns:
        Hash bcrypt de la contraseña
    """
    result: str = pwd_context.hash(password)
    return result


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
        result: bool = pwd_context.verify(plain_password, hashed_password)
        return result
    except Exception:
        return False


def validate_password_strength(password: str, min_length: int = 8) -> tuple[bool, str]:
    """
    Valida la fortaleza de una contraseña.

    Args:
        password: Contraseña a validar
        min_length: Longitud mínima requerida

    Returns:
        Tupla (es_válida, mensaje_error)
    """
    if len(password) < min_length:
        return False, f"La contraseña debe tener al menos {min_length} caracteres"

    if not re.search(r'[A-Z]', password):
        return False, "La contraseña debe contener al menos una mayúscula"

    if not re.search(r'[a-z]', password):
        return False, "La contraseña debe contener al menos una minúscula"

    if not re.search(r'\d', password):
        return False, "La contraseña debe contener al menos un número"

    return True, ""


# ============================================================================
# JWT TOKENS
# ============================================================================

class JWTService:
    """
    Servicio para manejo de JWT tokens.

    Maneja creación y verificación de tokens de acceso y refresh.
    """

    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        access_token_expire_hours: int = 24,
        refresh_token_expire_days: int = 7
    ):
        """
        Inicializa el servicio JWT.

        Args:
            secret_key: Clave secreta para firmar tokens
            algorithm: Algoritmo de firma
            access_token_expire_hours: Horas de validez del access token
            refresh_token_expire_days: Días de validez del refresh token
        """
        if not JWT_AVAILABLE:
            raise ImportError("pyjwt no está instalado. Ejecuta: pip install pyjwt")

        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire = timedelta(hours=access_token_expire_hours)
        self.refresh_token_expire = timedelta(days=refresh_token_expire_days)

    def create_access_token(
        self,
        user_id: int,
        org_id: str,
        rol: str = None,
        additional_claims: Dict[str, Any] = None
    ) -> str:
        """
        Crea un token de acceso.

        Args:
            user_id: ID del usuario
            org_id: ID de la organización
            rol: Rol del usuario
            additional_claims: Claims adicionales

        Returns:
            Token JWT codificado
        """
        now = datetime.utcnow()
        payload = {
            "sub": str(user_id),
            "org_id": org_id,
            "type": "access",
            "iat": now,
            "exp": now + self.access_token_expire,
            "jti": secrets.token_urlsafe(16)  # ID único del token
        }

        if rol:
            payload["rol"] = rol

        if additional_claims:
            payload.update(additional_claims)

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def create_refresh_token(self, user_id: int, org_id: str) -> str:
        """
        Crea un token de refresh.

        Args:
            user_id: ID del usuario
            org_id: ID de la organización

        Returns:
            Token JWT de refresh codificado
        """
        now = datetime.utcnow()
        payload = {
            "sub": str(user_id),
            "org_id": org_id,
            "type": "refresh",
            "iat": now,
            "exp": now + self.refresh_token_expire,
            "jti": secrets.token_urlsafe(16)
        }

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
        """
        Verifica y decodifica un token.

        Args:
            token: Token JWT a verificar
            token_type: Tipo esperado ("access" o "refresh")

        Returns:
            Payload del token o None si es inválido
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )

            # Verificar tipo de token
            if payload.get("type") != token_type:
                logger.warning(f"Tipo de token incorrecto: {payload.get('type')}")
                return None

            return dict(payload)

        except jwt.ExpiredSignatureError:
            logger.debug("Token expirado")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Token inválido: {e}")
            return None

    def get_user_id(self, token: str) -> Optional[int]:
        """Extrae el user_id de un token."""
        payload = self.verify_token(token)
        if payload:
            return int(payload.get("sub"))
        return None

    def get_org_id(self, token: str) -> Optional[str]:
        """Extrae el org_id de un token."""
        payload = self.verify_token(token)
        if payload:
            org_id = payload.get("org_id")
            return str(org_id) if org_id is not None else None
        return None


# ============================================================================
# PII ENCRYPTION (Datos Personales)
# ============================================================================

class PIIEncryption:
    """
    Servicio de encriptación para datos personales (PII).

    Usa Fernet (AES-128-CBC) para encriptar datos sensibles
    como cédulas, emails, teléfonos, etc.
    """

    def __init__(self, encryption_key: Optional[bytes] = None, password: Optional[str] = None):
        """
        Inicializa el servicio de encriptación.

        Args:
            encryption_key: Clave Fernet de 32 bytes base64
            password: Contraseña para derivar la clave (alternativa)
        """
        if not CRYPTO_AVAILABLE:
            raise ImportError(
                "cryptography no está instalado. Ejecuta: pip install cryptography"
            )

        if encryption_key:
            self.fernet = Fernet(encryption_key)
        elif password:
            # Derivar clave de la contraseña
            key = self._derive_key(password)
            self.fernet = Fernet(key)
        else:
            # Generar nueva clave
            self._key = Fernet.generate_key()
            self.fernet = Fernet(self._key)
            logger.warning(
                "Se generó una clave de encriptación nueva. "
                "Guárdala para poder descifrar los datos."
            )

    @staticmethod
    def _derive_key(password: str, salt: bytes = None) -> bytes:
        """Deriva una clave Fernet de una contraseña."""
        if salt is None:
            # Salt fijo (en producción usar uno aleatorio almacenado)
            salt = b'jewelry_invoice_bot_salt_v1'

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key

    @staticmethod
    def generate_key() -> bytes:
        """Genera una nueva clave de encriptación."""
        return Fernet.generate_key()

    def encrypt(self, data: str) -> str:
        """
        Encripta un string.

        Args:
            data: Datos a encriptar

        Returns:
            Datos encriptados en base64
        """
        if not data:
            return data

        encrypted = self.fernet.encrypt(data.encode('utf-8'))
        return encrypted.decode('utf-8')

    def decrypt(self, encrypted_data: str) -> str:
        """
        Desencripta un string.

        Args:
            encrypted_data: Datos encriptados

        Returns:
            Datos en texto plano
        """
        if not encrypted_data:
            return encrypted_data

        try:
            decrypted = self.fernet.decrypt(encrypted_data.encode('utf-8'))
            return decrypted.decode('utf-8')
        except InvalidToken:
            logger.error("Error al descifrar: token inválido o clave incorrecta")
            raise ValueError("No se pudo descifrar el dato")

    def encrypt_dict(self, data: dict, fields: list) -> dict:
        """
        Encripta campos específicos de un diccionario.

        Args:
            data: Diccionario con datos
            fields: Lista de campos a encriptar

        Returns:
            Diccionario con campos encriptados
        """
        result = data.copy()
        for field in fields:
            if field in result and result[field]:
                result[field] = self.encrypt(str(result[field]))
        return result

    def decrypt_dict(self, data: dict, fields: list) -> dict:
        """
        Desencripta campos específicos de un diccionario.

        Args:
            data: Diccionario con datos encriptados
            fields: Lista de campos a desencriptar

        Returns:
            Diccionario con campos desencriptados
        """
        result = data.copy()
        for field in fields:
            if field in result and result[field]:
                try:
                    result[field] = self.decrypt(str(result[field]))
                except ValueError:
                    pass  # Mantener el valor original si falla
        return result


# ============================================================================
# INPUT SANITIZATION
# ============================================================================

class InputSanitizer:
    """
    Utilidades para sanitizar input de usuarios.

    Previene XSS, SQL injection y otros ataques.
    """

    # Patrones peligrosos
    SQL_INJECTION_PATTERNS = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER)\b)",
        r"(--|;|\/\*|\*\/)",
        r"(\bOR\b\s+\d+\s*=\s*\d+)",
        r"(\bAND\b\s+\d+\s*=\s*\d+)",
    ]

    XSS_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"on\w+\s*=",
        r"<iframe",
        r"<object",
        r"<embed",
    ]

    @classmethod
    def sanitize_text(cls, text: str, max_length: int = 1000) -> str:
        """
        Sanitiza texto general.

        Args:
            text: Texto a sanitizar
            max_length: Longitud máxima permitida

        Returns:
            Texto sanitizado
        """
        if not text:
            return ""

        # Truncar
        text = text[:max_length]

        # Remover caracteres de control
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)

        # Escapar HTML básico
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        text = text.replace("'", '&#x27;')

        return text.strip()

    @classmethod
    def sanitize_cedula(cls, cedula: str) -> str:
        """
        Sanitiza un número de cédula.

        Args:
            cedula: Cédula a sanitizar

        Returns:
            Cédula sanitizada (solo dígitos)
        """
        if not cedula:
            return ""

        # Solo permitir dígitos
        return re.sub(r'[^\d]', '', cedula)[:15]

    @classmethod
    def sanitize_telefono(cls, telefono: str) -> str:
        """
        Sanitiza un número de teléfono.

        Args:
            telefono: Teléfono a sanitizar

        Returns:
            Teléfono sanitizado
        """
        if not telefono:
            return ""

        # Permitir dígitos, +, -, (, ), espacios
        sanitized = re.sub(r'[^\d+\-() ]', '', telefono)
        return sanitized[:20]

    @classmethod
    def sanitize_email(cls, email: str) -> str:
        """
        Sanitiza y valida un email.

        Args:
            email: Email a sanitizar

        Returns:
            Email sanitizado en minúsculas
        """
        if not email:
            return ""

        email = email.lower().strip()

        # Validar formato básico
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return ""

        return email[:255]

    @classmethod
    def sanitize_nombre(cls, nombre: str) -> str:
        """
        Sanitiza un nombre de persona.

        Args:
            nombre: Nombre a sanitizar

        Returns:
            Nombre sanitizado
        """
        if not nombre:
            return ""

        # Solo letras, espacios, guiones, apóstrofes
        nombre = re.sub(r'[^a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s\'-]', '', nombre)
        # Eliminar espacios múltiples
        nombre = re.sub(r'\s+', ' ', nombre)

        return nombre.strip()[:200]

    @classmethod
    def detect_injection(cls, text: str) -> bool:
        """
        Detecta intentos de inyección SQL o XSS.

        Args:
            text: Texto a analizar

        Returns:
            True si se detecta un intento de inyección
        """
        if not text:
            return False

        text_upper = text.upper()

        # Verificar patrones SQL
        for pattern in cls.SQL_INJECTION_PATTERNS:
            if re.search(pattern, text_upper, re.IGNORECASE):
                logger.warning(f"Posible SQL injection detectado: {text[:50]}...")
                return True

        # Verificar patrones XSS
        for pattern in cls.XSS_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                logger.warning(f"Posible XSS detectado: {text[:50]}...")
                return True

        return False


# ============================================================================
# CRYPTO SERVICE (Servicio Unificado)
# ============================================================================

class CryptoService:
    """
    Servicio unificado de criptografía.

    Combina todas las funcionalidades: passwords, JWT, PII encryption.
    """

    def __init__(
        self,
        secret_key: str,
        encryption_key: Optional[bytes] = None,
        jwt_expire_hours: int = 24
    ):
        """
        Inicializa el servicio de criptografía.

        Args:
            secret_key: Clave secreta para JWT
            encryption_key: Clave para encriptación PII (opcional)
            jwt_expire_hours: Horas de expiración de JWT
        """
        self.secret_key = secret_key

        # JWT
        if JWT_AVAILABLE:
            self.jwt = JWTService(
                secret_key=secret_key,
                access_token_expire_hours=jwt_expire_hours
            )
        else:
            self.jwt = None
            logger.warning("JWT no disponible - pyjwt no instalado")

        # PII Encryption
        if CRYPTO_AVAILABLE:
            if encryption_key:
                self.pii = PIIEncryption(encryption_key=encryption_key)
            else:
                # Derivar de secret_key
                self.pii = PIIEncryption(password=secret_key)
        else:
            self.pii = None
            logger.warning("PII encryption no disponible - cryptography no instalado")

        # Sanitizer
        self.sanitizer = InputSanitizer

    # Password methods
    def hash_password(self, password: str) -> str:
        return hash_password(password)

    def verify_password(self, password: str, hashed: str) -> bool:
        return verify_password(password, hashed)

    # JWT methods
    def create_token(self, user_id: int, org_id: str, rol: str = None) -> Optional[str]:
        if self.jwt:
            return self.jwt.create_access_token(user_id, org_id, rol)
        return None

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        if self.jwt:
            return self.jwt.verify_token(token)
        return None

    # PII methods
    def encrypt_pii(self, data: str) -> str:
        if self.pii:
            return self.pii.encrypt(data)
        return data

    def decrypt_pii(self, data: str) -> str:
        if self.pii:
            return self.pii.decrypt(data)
        return data

    # Sanitization
    def sanitize(self, text: str) -> str:
        return self.sanitizer.sanitize_text(text)

    def is_safe(self, text: str) -> bool:
        return not self.sanitizer.detect_injection(text)


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_crypto_service: Optional[CryptoService] = None


@lru_cache(maxsize=1)
def get_crypto_service() -> CryptoService:
    """
    Obtiene la instancia del servicio de criptografía.

    Returns:
        Instancia de CryptoService
    """
    from config.settings import settings

    # SECRET_KEY es SecretStr, extraer valor
    secret_key = settings.SECRET_KEY.get_secret_value()

    return CryptoService(
        secret_key=secret_key,
        jwt_expire_hours=settings.JWT_EXPIRATION_HOURS
    )