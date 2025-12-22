"""
Tests para el módulo de criptografía.
"""

import pytest
from src.utils.crypto import (
    hash_password,
    verify_password,
    validate_password_strength,
    InputSanitizer,
    JWTService,
    PIIEncryption,
    CryptoService,
)


class TestPasswordHashing:
    """Tests para hashing de contraseñas."""

    def test_hash_password_returns_hash(self):
        """Verifica que hash_password retorna un hash."""
        password = "Test123!"
        hashed = hash_password(password)

        assert hashed is not None
        assert hashed != password
        assert len(hashed) > 0

    def test_hash_password_different_for_same_password(self):
        """Verifica que el mismo password genera hashes diferentes (salt)."""
        password = "Test123!"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 != hash2

    def test_verify_password_correct(self):
        """Verifica password correcto."""
        password = "Test123!"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Verifica password incorrecto."""
        password = "Test123!"
        wrong_password = "Wrong456!"
        hashed = hash_password(password)

        assert verify_password(wrong_password, hashed) is False

    def test_verify_password_invalid_hash(self):
        """Verifica comportamiento con hash inválido."""
        assert verify_password("any", "invalid_hash") is False


class TestPasswordStrength:
    """Tests para validación de fortaleza de contraseñas."""

    def test_valid_password(self):
        """Verifica password válido."""
        is_valid, message = validate_password_strength("Test123!")
        assert is_valid is True
        assert message == ""

    def test_password_too_short(self):
        """Verifica password muy corto."""
        is_valid, message = validate_password_strength("Te1!")
        assert is_valid is False
        assert "8 caracteres" in message

    def test_password_no_uppercase(self):
        """Verifica password sin mayúsculas."""
        is_valid, message = validate_password_strength("test1234!")
        assert is_valid is False
        assert "mayúscula" in message

    def test_password_no_lowercase(self):
        """Verifica password sin minúsculas."""
        is_valid, message = validate_password_strength("TEST1234!")
        assert is_valid is False
        assert "minúscula" in message

    def test_password_no_number(self):
        """Verifica password sin números."""
        is_valid, message = validate_password_strength("TestTest!")
        assert is_valid is False
        assert "número" in message


class TestInputSanitizer:
    """Tests para sanitización de inputs."""

    def test_sanitize_text_basic(self):
        """Verifica sanitización básica."""
        result = InputSanitizer.sanitize_text("Hello World")
        assert result == "Hello World"

    def test_sanitize_text_html(self):
        """Verifica escape de HTML."""
        result = InputSanitizer.sanitize_text("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_sanitize_text_max_length(self):
        """Verifica truncado de texto largo."""
        long_text = "a" * 2000
        result = InputSanitizer.sanitize_text(long_text, max_length=100)
        assert len(result) == 100

    def test_sanitize_cedula(self):
        """Verifica sanitización de cédula."""
        result = InputSanitizer.sanitize_cedula("123-456-789")
        assert result == "123456789"

    def test_sanitize_telefono(self):
        """Verifica sanitización de teléfono."""
        result = InputSanitizer.sanitize_telefono("+57 (300) 123-4567")
        assert result == "+57 (300) 123-4567"

    def test_sanitize_email_valid(self):
        """Verifica sanitización de email válido."""
        result = InputSanitizer.sanitize_email("Test@Example.COM")
        assert result == "test@example.com"

    def test_sanitize_email_invalid(self):
        """Verifica sanitización de email inválido."""
        result = InputSanitizer.sanitize_email("not-an-email")
        assert result == ""

    def test_sanitize_nombre(self):
        """Verifica sanitización de nombre."""
        result = InputSanitizer.sanitize_nombre("José García-López")
        assert result == "José García-López"

    def test_sanitize_nombre_removes_special(self):
        """Verifica que remueve caracteres especiales."""
        result = InputSanitizer.sanitize_nombre("José<script>García")
        assert "<script>" not in result

    def test_detect_sql_injection(self):
        """Verifica detección de SQL injection."""
        assert InputSanitizer.detect_injection("'; DROP TABLE users; --") is True
        assert InputSanitizer.detect_injection("SELECT * FROM users") is True
        assert InputSanitizer.detect_injection("normal text") is False

    def test_detect_xss(self):
        """Verifica detección de XSS."""
        assert InputSanitizer.detect_injection("<script>alert('xss')</script>") is True
        assert InputSanitizer.detect_injection("onclick=evil()") is True
        assert InputSanitizer.detect_injection("normal text") is False


class TestJWTService:
    """Tests para el servicio JWT."""

    @pytest.fixture
    def jwt_service(self):
        """Crea un servicio JWT para tests."""
        return JWTService(
            secret_key="test_secret_key",
            access_token_expire_hours=1
        )

    def test_create_access_token(self, jwt_service):
        """Verifica creación de access token."""
        token = jwt_service.create_access_token(
            user_id=1,
            org_id="org-123",
            rol="VENDEDOR"
        )

        assert token is not None
        assert len(token) > 0

    def test_verify_token_valid(self, jwt_service):
        """Verifica token válido."""
        token = jwt_service.create_access_token(user_id=1, org_id="org-123")
        payload = jwt_service.verify_token(token)

        assert payload is not None
        assert payload["sub"] == "1"
        assert payload["org_id"] == "org-123"
        assert payload["type"] == "access"

    def test_verify_token_invalid(self, jwt_service):
        """Verifica token inválido."""
        payload = jwt_service.verify_token("invalid.token.here")
        assert payload is None

    def test_verify_token_wrong_type(self, jwt_service):
        """Verifica token con tipo incorrecto."""
        token = jwt_service.create_refresh_token(user_id=1, org_id="org-123")
        payload = jwt_service.verify_token(token, token_type="access")
        assert payload is None

    def test_get_user_id(self, jwt_service):
        """Verifica extracción de user_id."""
        token = jwt_service.create_access_token(user_id=42, org_id="org-123")
        user_id = jwt_service.get_user_id(token)
        assert user_id == 42

    def test_get_org_id(self, jwt_service):
        """Verifica extracción de org_id."""
        token = jwt_service.create_access_token(user_id=1, org_id="org-456")
        org_id = jwt_service.get_org_id(token)
        assert org_id == "org-456"


class TestPIIEncryption:
    """Tests para encriptación de PII."""

    @pytest.fixture
    def pii_service(self):
        """Crea un servicio de encriptación PII."""
        return PIIEncryption(password="test_password")

    def test_encrypt_decrypt(self, pii_service):
        """Verifica ciclo completo de encriptación/desencriptación."""
        original = "123456789"
        encrypted = pii_service.encrypt(original)
        decrypted = pii_service.decrypt(encrypted)

        assert encrypted != original
        assert decrypted == original

    def test_encrypt_empty_string(self, pii_service):
        """Verifica encriptación de string vacío."""
        result = pii_service.encrypt("")
        assert result == ""

    def test_encrypt_none(self, pii_service):
        """Verifica encriptación de None."""
        result = pii_service.encrypt(None)
        assert result is None

    def test_encrypt_dict(self, pii_service):
        """Verifica encriptación de campos en diccionario."""
        data = {
            "cedula": "123456789",
            "nombre": "Test User",
            "email": "test@test.com",
        }
        encrypted = pii_service.encrypt_dict(data, ["cedula", "email"])

        assert encrypted["cedula"] != "123456789"
        assert encrypted["nombre"] == "Test User"  # No encriptado
        assert encrypted["email"] != "test@test.com"

    def test_decrypt_dict(self, pii_service):
        """Verifica desencriptación de campos en diccionario."""
        data = {
            "cedula": "123456789",
            "email": "test@test.com",
        }
        encrypted = pii_service.encrypt_dict(data, ["cedula", "email"])
        decrypted = pii_service.decrypt_dict(encrypted, ["cedula", "email"])

        assert decrypted["cedula"] == "123456789"
        assert decrypted["email"] == "test@test.com"

    def test_generate_key(self):
        """Verifica generación de clave."""
        key = PIIEncryption.generate_key()
        assert key is not None
        assert len(key) > 0


class TestCryptoService:
    """Tests para el servicio unificado de criptografía."""

    @pytest.fixture
    def crypto_service(self):
        """Crea un servicio de criptografía."""
        return CryptoService(
            secret_key="test_secret_key",
            jwt_expire_hours=1
        )

    def test_hash_password(self, crypto_service):
        """Verifica hash de password via servicio."""
        hashed = crypto_service.hash_password("Test123!")
        assert crypto_service.verify_password("Test123!", hashed) is True

    def test_create_verify_token(self, crypto_service):
        """Verifica creación y verificación de token."""
        token = crypto_service.create_token(user_id=1, org_id="org-123", rol="ADMIN")
        payload = crypto_service.verify_token(token)

        assert payload is not None
        assert payload["sub"] == "1"

    def test_encrypt_decrypt_pii(self, crypto_service):
        """Verifica encriptación/desencriptación de PII."""
        original = "sensitive_data"
        encrypted = crypto_service.encrypt_pii(original)
        decrypted = crypto_service.decrypt_pii(encrypted)

        assert encrypted != original
        assert decrypted == original

    def test_sanitize(self, crypto_service):
        """Verifica sanitización via servicio."""
        result = crypto_service.sanitize("<script>evil</script>")
        assert "<script>" not in result

    def test_is_safe(self, crypto_service):
        """Verifica detección de inputs peligrosos."""
        assert crypto_service.is_safe("normal text") is True
        assert crypto_service.is_safe("'; DROP TABLE --") is False