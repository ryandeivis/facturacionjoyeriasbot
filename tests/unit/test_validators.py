"""
Tests para el módulo de validadores.

Prueba todas las funciones de validación centralizadas.
"""

import pytest
from src.utils.validators import (
    ValidationResult,
    ValidationLimits,
    IdentityValidator,
    ContactValidator,
    ProductValidator,
    InvoiceValidator,
    FileValidator,
    ValidationService,
    validar_cedula,
    validar_nombre,
    validar_precio,
    validar_cantidad,
    validar_email,
    parsear_precio,
)


# ============================================================================
# VALIDATION RESULT TESTS
# ============================================================================

class TestValidationResult:
    """Tests para ValidationResult."""

    def test_result_valid(self):
        """Resultado válido funciona correctamente."""
        result = ValidationResult(valid=True, sanitized="test")
        assert result.valid is True
        assert result.error == ""
        assert result.sanitized == "test"
        assert bool(result) is True

    def test_result_invalid(self):
        """Resultado inválido funciona correctamente."""
        result = ValidationResult(valid=False, error="Error message")
        assert result.valid is False
        assert result.error == "Error message"
        assert bool(result) is False


# ============================================================================
# IDENTITY VALIDATOR TESTS
# ============================================================================

class TestIdentityValidator:
    """Tests para validación de identidad (cédula, nombre)."""

    # --- Cédula Tests ---

    def test_cedula_valida_numerica(self):
        """Cédula numérica válida."""
        result = IdentityValidator.validate_cedula("12345678")
        assert result.valid is True
        assert result.sanitized == "12345678"
        assert result.error == ""

    def test_cedula_valida_con_puntos(self):
        """Cédula con puntos se sanitiza correctamente."""
        result = IdentityValidator.validate_cedula("12.345.678")
        assert result.valid is True
        assert result.sanitized == "12345678"

    def test_cedula_valida_con_guiones(self):
        """Cédula con guiones se sanitiza correctamente."""
        result = IdentityValidator.validate_cedula("12-345-678")
        assert result.valid is True
        assert result.sanitized == "12345678"

    def test_cedula_valida_con_espacios(self):
        """Cédula con espacios se sanitiza correctamente."""
        result = IdentityValidator.validate_cedula("  12345678  ")
        assert result.valid is True
        assert result.sanitized == "12345678"

    def test_cedula_muy_corta(self):
        """Cédula muy corta es rechazada."""
        result = IdentityValidator.validate_cedula("12345")
        assert result.valid is False
        assert "6" in result.error  # Mínimo 6 dígitos

    def test_cedula_muy_larga(self):
        """Cédula muy larga es rechazada."""
        result = IdentityValidator.validate_cedula("1234567890123")
        assert result.valid is False
        assert "12" in result.error  # Máximo 12 dígitos

    def test_cedula_con_letras_se_sanitiza(self):
        """Cédula con letras se sanitiza a solo dígitos."""
        result = IdentityValidator.validate_cedula("1234abc5678")
        assert result.valid is True
        assert result.sanitized == "12345678"

    def test_cedula_solo_letras(self):
        """Cédula con solo letras es rechazada."""
        result = IdentityValidator.validate_cedula("abcdefgh")
        assert result.valid is False
        assert "números" in result.error.lower()

    def test_cedula_vacia(self):
        """Cédula vacía es rechazada."""
        result = IdentityValidator.validate_cedula("")
        assert result.valid is False
        assert "requerida" in result.error.lower()

    def test_cedula_solo_espacios(self):
        """Cédula con solo espacios es rechazada."""
        result = IdentityValidator.validate_cedula("   ")
        assert result.valid is False

    # --- Nombre Tests ---

    def test_nombre_valido(self):
        """Nombre válido."""
        result = IdentityValidator.validate_nombre_persona("Juan Pérez")
        assert result.valid is True
        assert result.sanitized == "Juan Pérez"

    def test_nombre_con_tildes(self):
        """Nombre con tildes es válido."""
        result = IdentityValidator.validate_nombre_persona("María José Ñoño")
        assert result.valid is True

    def test_nombre_muy_corto(self):
        """Nombre muy corto es rechazado."""
        result = IdentityValidator.validate_nombre_persona("AB")
        assert result.valid is False
        assert "3" in result.error  # Mínimo 3 caracteres

    def test_nombre_muy_largo(self):
        """Nombre muy largo es rechazado."""
        result = IdentityValidator.validate_nombre_persona("A" * 150)
        assert result.valid is False
        assert "100" in result.error  # Máximo 100 caracteres

    def test_nombre_con_numeros(self):
        """Nombre con números es rechazado."""
        result = IdentityValidator.validate_nombre_persona("Juan123")
        assert result.valid is False
        assert "letras" in result.error.lower()

    def test_nombre_con_caracteres_especiales(self):
        """Nombre con caracteres especiales es rechazado."""
        result = IdentityValidator.validate_nombre_persona("Juan<script>")
        assert result.valid is False

    def test_nombre_normaliza_espacios(self):
        """Nombre normaliza espacios múltiples."""
        result = IdentityValidator.validate_nombre_persona("Juan    Pérez")
        assert result.valid is True
        assert result.sanitized == "Juan Pérez"


# ============================================================================
# CONTACT VALIDATOR TESTS
# ============================================================================

class TestContactValidator:
    """Tests para validación de contacto (teléfono, email, dirección)."""

    # --- Teléfono Tests ---

    def test_telefono_valido_colombia(self):
        """Teléfono colombiano válido."""
        result = ContactValidator.validate_telefono("3001234567")
        assert result.valid is True

    def test_telefono_con_prefijo_pais(self):
        """Teléfono con prefijo de país."""
        result = ContactValidator.validate_telefono("+573001234567")
        assert result.valid is True

    def test_telefono_con_espacios(self):
        """Teléfono con espacios se sanitiza."""
        result = ContactValidator.validate_telefono("300 123 4567")
        assert result.valid is True
        # El sanitizado mantiene el formato permitido

    def test_telefono_muy_corto(self):
        """Teléfono muy corto es rechazado."""
        result = ContactValidator.validate_telefono("12345")
        assert result.valid is False
        assert "7" in result.error  # Mínimo 7 dígitos

    def test_telefono_sanitiza_letras(self):
        """Teléfono con letras se sanitiza."""
        result = ContactValidator.validate_telefono("300abc4567")
        assert result.valid is True
        assert result.sanitized == "3004567"

    def test_telefono_vacio_es_opcional(self):
        """Teléfono vacío es válido (campo opcional)."""
        result = ContactValidator.validate_telefono("")
        assert result.valid is True

    # --- Email Tests ---

    def test_email_valido(self):
        """Email válido."""
        result = ContactValidator.validate_email("usuario@ejemplo.com")
        assert result.valid is True
        assert result.sanitized == "usuario@ejemplo.com"

    def test_email_con_subdominio(self):
        """Email con subdominio es válido."""
        result = ContactValidator.validate_email("usuario@mail.ejemplo.com")
        assert result.valid is True

    def test_email_se_normaliza_minusculas(self):
        """Email se normaliza a minúsculas."""
        result = ContactValidator.validate_email("Usuario@EJEMPLO.COM")
        assert result.valid is True
        assert result.sanitized == "usuario@ejemplo.com"

    def test_email_sin_arroba(self):
        """Email sin @ es rechazado."""
        result = ContactValidator.validate_email("usuarioejemplo.com")
        assert result.valid is False
        assert "inválido" in result.error.lower()

    def test_email_sin_dominio(self):
        """Email sin dominio es rechazado."""
        result = ContactValidator.validate_email("usuario@")
        assert result.valid is False

    def test_email_vacio_es_opcional(self):
        """Email vacío es válido (campo opcional)."""
        result = ContactValidator.validate_email("")
        assert result.valid is True

    # --- Dirección Tests ---

    def test_direccion_valida(self):
        """Dirección válida."""
        result = ContactValidator.validate_direccion("Calle 123 # 45-67")
        assert result.valid is True

    def test_direccion_muy_larga(self):
        """Dirección muy larga es rechazada."""
        result = ContactValidator.validate_direccion("A" * 250)
        assert result.valid is False
        assert "200" in result.error

    def test_direccion_vacia_es_opcional(self):
        """Dirección vacía es válida (campo opcional)."""
        result = ContactValidator.validate_direccion("")
        assert result.valid is True


# ============================================================================
# PRODUCT VALIDATOR TESTS
# ============================================================================

class TestProductValidator:
    """Tests para validación de productos."""

    # --- Nombre Producto Tests ---

    def test_nombre_producto_valido(self):
        """Nombre de producto válido."""
        result = ProductValidator.validate_nombre_producto("Anillo Oro 18K")
        assert result.valid is True

    def test_nombre_producto_muy_corto(self):
        """Nombre de producto muy corto es rechazado."""
        result = ProductValidator.validate_nombre_producto("A")
        assert result.valid is False
        assert "2" in result.error  # Mínimo 2 caracteres

    # --- Precio Tests ---

    def test_precio_valido(self):
        """Precio válido."""
        result = ProductValidator.validate_precio(500000)
        assert result.valid is True

    def test_precio_cero_valido(self):
        """Precio cero es válido."""
        result = ProductValidator.validate_precio(0)
        assert result.valid is True

    def test_precio_negativo(self):
        """Precio negativo es rechazado."""
        result = ProductValidator.validate_precio(-100)
        assert result.valid is False
        assert "negativo" in result.error.lower()

    def test_precio_muy_alto(self):
        """Precio muy alto es rechazado."""
        result = ProductValidator.validate_precio(10_000_000_000_000)
        assert result.valid is False
        assert "límite" in result.error.lower()

    # --- Cantidad Tests ---

    def test_cantidad_valida(self):
        """Cantidad válida."""
        result = ProductValidator.validate_cantidad(5)
        assert result.valid is True

    def test_cantidad_uno(self):
        """Cantidad uno es válida."""
        result = ProductValidator.validate_cantidad(1)
        assert result.valid is True

    def test_cantidad_cero(self):
        """Cantidad cero es rechazada."""
        result = ProductValidator.validate_cantidad(0)
        assert result.valid is False
        assert "mínima" in result.error.lower()

    def test_cantidad_negativa(self):
        """Cantidad negativa es rechazada."""
        result = ProductValidator.validate_cantidad(-1)
        assert result.valid is False

    def test_cantidad_muy_alta(self):
        """Cantidad muy alta es rechazada."""
        result = ProductValidator.validate_cantidad(10000)
        assert result.valid is False
        assert "máxima" in result.error.lower()

    # --- Parse Precio Tests ---

    def test_parse_precio_numero(self):
        """Parsear precio numérico."""
        success, value, error = ProductValidator.parse_precio("500000")
        assert success is True
        assert value == 500000
        assert error == ""

    def test_parse_precio_con_signo_pesos(self):
        """Parsear precio con signo de pesos."""
        success, value, error = ProductValidator.parse_precio("$500000")
        assert success is True
        assert value == 500000

    def test_parse_precio_con_puntos_miles(self):
        """Parsear precio con puntos de miles."""
        success, value, error = ProductValidator.parse_precio("500.000")
        assert success is True
        assert value == 500000

    def test_parse_precio_con_comas(self):
        """Parsear precio con comas."""
        success, value, error = ProductValidator.parse_precio("500,000")
        assert success is True
        assert value == 500000

    def test_parse_precio_con_texto(self):
        """Parsear precio con texto falla."""
        success, value, error = ProductValidator.parse_precio("quinientos mil")
        assert success is False
        assert "inválido" in error.lower()

    def test_parse_precio_vacio(self):
        """Parsear precio vacío falla."""
        success, value, error = ProductValidator.parse_precio("")
        assert success is False
        assert "requerido" in error.lower()


# ============================================================================
# INVOICE VALIDATOR TESTS
# ============================================================================

class TestInvoiceValidator:
    """Tests para validación de facturas."""

    def test_items_count_valido(self):
        """Cantidad de items válida."""
        result = InvoiceValidator.validate_items_count(5)
        assert result.valid is True

    def test_items_count_cero(self):
        """Cero items es rechazado."""
        result = InvoiceValidator.validate_items_count(0)
        assert result.valid is False
        assert "al menos un" in result.error.lower()

    def test_items_count_excede_maximo(self):
        """Demasiados items es rechazado."""
        result = InvoiceValidator.validate_items_count(100)
        assert result.valid is False
        assert "50" in result.error

    def test_total_valido(self):
        """Total válido."""
        result = InvoiceValidator.validate_total(1000000)
        assert result.valid is True

    def test_total_cero(self):
        """Total cero es rechazado."""
        result = InvoiceValidator.validate_total(0)
        assert result.valid is False
        assert "mayor a cero" in result.error.lower()

    def test_total_negativo(self):
        """Total negativo es rechazado."""
        result = InvoiceValidator.validate_total(-1000)
        assert result.valid is False


# ============================================================================
# FILE VALIDATOR TESTS
# ============================================================================

class TestFileValidator:
    """Tests para validación de archivos."""

    def test_file_size_valido(self):
        """Tamaño de archivo válido."""
        result = FileValidator.validate_file_size(5 * 1024 * 1024)  # 5MB
        assert result.valid is True

    def test_file_size_muy_grande(self):
        """Archivo muy grande es rechazado."""
        result = FileValidator.validate_file_size(50 * 1024 * 1024)  # 50MB
        assert result.valid is False
        assert "10MB" in result.error

    def test_voice_duration_valida(self):
        """Duración de audio válida."""
        result = FileValidator.validate_voice_duration(60)  # 1 minuto
        assert result.valid is True

    def test_voice_duration_muy_larga(self):
        """Audio muy largo es rechazado."""
        result = FileValidator.validate_voice_duration(600)  # 10 minutos
        assert result.valid is False
        assert "5 minutos" in result.error


# ============================================================================
# VALIDATION SERVICE TESTS
# ============================================================================

class TestValidationService:
    """Tests para el servicio unificado de validación."""

    def test_service_sin_config(self):
        """Servicio sin configuración de tenant."""
        service = ValidationService()
        result = service.validate_cedula("12345678")
        assert result.valid is True

    def test_service_con_config_tenant(self):
        """Servicio con configuración de tenant."""
        config = {"cedula_min": 8, "cedula_max": 10}
        service = ValidationService(config)

        # Con 6 dígitos falla (mínimo es 8)
        result = service.validate_cedula("123456")
        assert result.valid is False

    def test_service_validate_nombre(self):
        """Validar nombre via servicio."""
        service = ValidationService()
        result = service.validate_nombre("Juan Pérez")
        assert result.valid is True

    def test_service_validate_precio(self):
        """Validar precio via servicio."""
        service = ValidationService()
        result = service.validate_precio(500000)
        assert result.valid is True

    def test_service_parse_precio(self):
        """Parsear precio via servicio."""
        service = ValidationService()
        success, value, error = service.parse_precio("$500.000")
        assert success is True
        assert value == 500000


# ============================================================================
# CONVENIENCE FUNCTIONS TESTS
# ============================================================================

class TestConvenienceFunctions:
    """Tests para funciones de conveniencia."""

    def test_validar_cedula_funcion(self):
        """Función validar_cedula funciona."""
        is_valid, error = validar_cedula("12345678")
        assert is_valid is True
        assert error == ""

    def test_validar_cedula_invalida(self):
        """Función validar_cedula con cédula inválida."""
        is_valid, error = validar_cedula("123")
        assert is_valid is False
        assert len(error) > 0

    def test_validar_nombre_funcion(self):
        """Función validar_nombre funciona."""
        is_valid, error = validar_nombre("Juan Pérez")
        assert is_valid is True
        assert error == ""

    def test_validar_precio_funcion(self):
        """Función validar_precio funciona."""
        is_valid, error = validar_precio(500000)
        assert is_valid is True
        assert error == ""

    def test_validar_cantidad_funcion(self):
        """Función validar_cantidad funciona."""
        is_valid, error = validar_cantidad(5)
        assert is_valid is True
        assert error == ""

    def test_validar_email_funcion(self):
        """Función validar_email funciona."""
        is_valid, error = validar_email("test@example.com")
        assert is_valid is True
        assert error == ""

    def test_parsear_precio_funcion(self):
        """Función parsear_precio funciona."""
        success, value, error = parsear_precio("$500.000")
        assert success is True
        assert value == 500000


# ============================================================================
# VALIDATION LIMITS TESTS
# ============================================================================

class TestValidationLimits:
    """Tests para los límites de validación."""

    def test_limits_son_positivos(self):
        """Todos los límites son positivos."""
        assert ValidationLimits.CEDULA_MIN_LENGTH > 0
        assert ValidationLimits.CEDULA_MAX_LENGTH > 0
        assert ValidationLimits.NOMBRE_MIN_LENGTH > 0
        assert ValidationLimits.NOMBRE_MAX_LENGTH > 0
        assert ValidationLimits.PRECIO_MAX > 0
        assert ValidationLimits.CANTIDAD_MAX > 0

    def test_min_menor_que_max(self):
        """Los mínimos son menores que los máximos."""
        assert ValidationLimits.CEDULA_MIN_LENGTH < ValidationLimits.CEDULA_MAX_LENGTH
        assert ValidationLimits.NOMBRE_MIN_LENGTH < ValidationLimits.NOMBRE_MAX_LENGTH
        assert ValidationLimits.CANTIDAD_MIN < ValidationLimits.CANTIDAD_MAX

    def test_limite_items_factura(self):
        """Límite de items por factura es razonable."""
        assert ValidationLimits.MAX_ITEMS_PER_INVOICE == 50

    def test_limite_archivo(self):
        """Límite de archivo es razonable."""
        assert ValidationLimits.MAX_FILE_SIZE_MB == 10
