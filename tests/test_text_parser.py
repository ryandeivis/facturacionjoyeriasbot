"""
Tests para TextParserService

Prueba los diferentes formatos de entrada de texto para facturación.
"""
import pytest
from src.services.text_parser import TextParserService, ParsedItem


class TestTextParser:
    """Tests para el parser de texto"""

    @pytest.fixture
    def parser(self):
        return TextParserService()

    # =========== Tests de formatos básicos ===========

    def test_formato_numerado_completo(self, parser):
        """Test formato: 1. Producto - cantidad X - precio $XXX"""
        text = """
        1. Cadena plata - cantidad 2 - precio $200.000
        2. Anillo oro - cantidad 1 - precio $1.500.000
        """
        result = parser.parse(text)

        assert result.success
        assert len(result.items) == 2
        assert result.items[0]['nombre'] == 'Cadena Plata'
        assert result.items[0]['cantidad'] == 2
        assert result.items[0]['precio'] == 200000
        assert result.items[1]['precio'] == 1500000

    def test_formato_inline_con_precio(self, parser):
        """Test formato: Producto x2 $200000"""
        text = """
        Cadena plata x2 $200000
        Anillo oro $1500000
        """
        result = parser.parse(text)

        assert result.success
        assert len(result.items) == 2
        assert result.items[0]['cantidad'] == 2
        assert result.items[1]['cantidad'] == 1

    def test_formato_cantidad_primero(self, parser):
        """Test formato: 2 cadenas a 200000"""
        text = """
        3 cadenas a 200000
        1 anillo de 1500000
        """
        result = parser.parse(text)

        assert result.success
        assert len(result.items) == 2
        assert result.items[0]['cantidad'] == 3

    def test_formato_palabra_cantidad(self, parser):
        """Test formato: una cadena por 200000"""
        text = """
        una cadena por 200000
        dos aretes de 95000
        """
        result = parser.parse(text)

        assert result.success
        assert len(result.items) == 2
        assert result.items[0]['cantidad'] == 1
        assert result.items[1]['cantidad'] == 2

    def test_formato_simple(self, parser):
        """Test formato simple: Producto precio (sin $)"""
        text = "Cadena plata 200000"
        result = parser.parse(text)

        assert result.success
        assert len(result.items) >= 1
        assert result.items[0]['precio'] == 200000

    # =========== Tests de precios ===========

    def test_precio_con_puntos_miles(self, parser):
        """Test precio formato colombiano: 1.500.000"""
        text = "Anillo oro $1.500.000"
        result = parser.parse(text)

        assert result.success
        assert result.items[0]['precio'] == 1500000

    def test_precio_sin_formato(self, parser):
        """Test precio sin separadores: 1500000"""
        text = "Anillo oro $1500000"
        result = parser.parse(text)

        assert result.success
        assert result.items[0]['precio'] == 1500000

    def test_precio_con_signo_peso(self, parser):
        """Test precio con $: $1.500.000"""
        text = "Anillo oro $1.500.000"
        result = parser.parse(text)

        assert result.success
        assert result.items[0]['precio'] == 1500000

    # =========== Tests de totales ===========

    def test_calculo_totales(self, parser):
        """Test que los totales se calculen correctamente"""
        text = """
        Cadena plata x2 $200000
        Anillo oro $1500000
        """
        result = parser.parse(text)

        assert result.success
        # 2 * 200000 + 1 * 1500000 = 1900000
        assert result.totales['subtotal'] == 1900000
        assert result.totales['total'] == 1900000

    # =========== Tests de edge cases ===========

    def test_texto_vacio(self, parser):
        """Test con texto vacío"""
        result = parser.parse("")
        assert not result.success
        assert result.error is not None

    def test_texto_sin_productos(self, parser):
        """Test con texto que no contiene productos"""
        text = "Hola, buenos días, necesito información"
        result = parser.parse(text)
        assert not result.success

    def test_title_case(self, parser):
        """Test que los nombres se formateen en Title Case"""
        text = "CADENA PLATA $200000"
        result = parser.parse(text)

        assert result.success
        assert result.items[0]['nombre'] == 'Cadena Plata'

    def test_duplicados_removidos(self, parser):
        """Test que se remuevan items duplicados"""
        text = """
        Cadena plata $200000
        Cadena plata $200000
        """
        result = parser.parse(text)

        assert result.success
        assert len(result.items) == 1

    # =========== Tests de joyería ===========

    def test_productos_joyeria_tipicos(self, parser):
        """Test con productos típicos de joyería"""
        text = """
        Anillo de compromiso oro 18k $2500000
        Cadena plata 925 x2 $180000
        Aretes perlas $95000
        Pulsera oro rosa $350000
        """
        result = parser.parse(text)

        assert result.success
        assert len(result.items) == 4

    def test_producto_con_descripcion_larga(self, parser):
        """Test con descripciones largas de producto"""
        text = "Anillo solitario con diamante de medio quilate en oro blanco 18 kilates $3500000"
        result = parser.parse(text)

        assert result.success
        assert result.items[0]['precio'] == 3500000

    # =========== Tests de ParsedItem ===========

    def test_parsed_item_total(self):
        """Test cálculo de total en ParsedItem"""
        item = ParsedItem(nombre="Test", cantidad=3, precio=100000)
        assert item.total == 300000

    def test_parsed_item_to_dict(self):
        """Test conversión a diccionario"""
        item = ParsedItem(nombre="Cadena", descripcion="Plata 925", cantidad=2, precio=150000)
        d = item.to_dict()

        assert d['nombre'] == "Cadena"
        assert d['descripcion'] == "Plata 925"
        assert d['cantidad'] == 2
        assert d['precio'] == 150000
        assert d['total'] == 300000


class TestTextParserIntegration:
    """Tests de integración del parser"""

    @pytest.fixture
    def parser(self):
        return TextParserService()

    def test_respuesta_compatible_n8n(self, parser):
        """Test que la respuesta sea compatible con N8NResponse"""
        text = "Cadena plata $200000"
        result = parser.parse(text)

        # Verificar estructura de respuesta
        assert hasattr(result, 'success')
        assert hasattr(result, 'items')
        assert hasattr(result, 'totales')
        assert hasattr(result, 'error')

        # Verificar estructura de items
        assert isinstance(result.items, list)
        if result.items:
            item = result.items[0]
            assert 'nombre' in item
            assert 'cantidad' in item
            assert 'precio' in item
            assert 'total' in item

    def test_input_type_es_text(self, parser):
        """Test que input_type sea 'text'"""
        text = "Cadena plata $200000"
        result = parser.parse(text)

        assert result.success
        assert result.input_type == "text"

    def test_confianza_alta(self, parser):
        """Test que la confianza sea alta para regex exitoso"""
        text = "Cadena plata $200000"
        result = parser.parse(text)

        assert result.success
        assert result.confianza >= 0.9