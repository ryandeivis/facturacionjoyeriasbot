"""
Factories para Invoice e Items

Proporciona factories para crear facturas con items realistas de joyería.
"""

import factory
from factory import Faker, LazyAttribute, Sequence, SubFactory
import uuid
from datetime import datetime
from typing import List, Dict, Any

from src.database.models import Invoice
from config.constants import InvoiceStatus
from tests.factories.base import BaseFactory, DictFactory


class InvoiceItemFactory(DictFactory):
    """
    Factory para crear items de factura (diccionarios).

    Ejemplos:
        # Item básico
        item = InvoiceItemFactory()

        # Item específico
        item = InvoiceItemFactory(descripcion="Anillo de compromiso", precio=2500000)

        # Múltiples items
        items = InvoiceItemFactory.create_batch(3)
    """

    class Meta:
        model = dict

    descripcion = LazyAttribute(lambda _: _random_jewelry_description())
    cantidad = 1
    precio = LazyAttribute(lambda _: _random_jewelry_price())
    subtotal = LazyAttribute(lambda o: o.cantidad * o.precio)

    class Params:
        """Variantes de items."""

        # Joya de oro
        oro = factory.Trait(
            descripcion=LazyAttribute(lambda _: f"Anillo de oro 18k {factory.Faker._get_faker().word()}"),
            precio=LazyAttribute(lambda _: factory.Faker._get_faker().random_int(min=500000, max=3000000))
        )

        # Joya de plata
        plata = factory.Trait(
            descripcion=LazyAttribute(lambda _: f"Collar de plata 925 {factory.Faker._get_faker().word()}"),
            precio=LazyAttribute(lambda _: factory.Faker._get_faker().random_int(min=50000, max=500000))
        )

        # Piedra preciosa
        diamante = factory.Trait(
            descripcion=LazyAttribute(lambda _: f"Diamante {factory.Faker._get_faker().random_element(['0.5ct', '1ct', '1.5ct', '2ct'])}"),
            precio=LazyAttribute(lambda _: factory.Faker._get_faker().random_int(min=2000000, max=15000000))
        )


class InvoiceFactory(BaseFactory):
    """
    Factory para crear facturas.

    Ejemplos:
        # Factura básica (borrador)
        invoice = InvoiceFactory()

        # Factura finalizada
        invoice = InvoiceFactory(finalizada=True)

        # Factura con total específico
        invoice = InvoiceFactory(total=1500000)

        # Factura pagada
        invoice = InvoiceFactory(pagada=True)
    """

    class Meta:
        model = Invoice

    id = LazyAttribute(lambda _: str(uuid.uuid4()))

    # Multi-tenancy
    organization_id = LazyAttribute(lambda _: str(uuid.uuid4()))

    # Número de factura
    numero_factura = Sequence(lambda n: f"FAC-{str(n).zfill(6)}")

    # Datos del cliente
    cliente_nombre = Faker("name", locale="es_CO")
    cliente_direccion = Faker("address", locale="es_CO")
    cliente_ciudad = LazyAttribute(lambda _: _random_colombian_city())
    cliente_email = Faker("email")
    cliente_telefono = LazyAttribute(lambda _: f"+5731{factory.Faker._get_faker().random_number(digits=8, fix_len=True)}")
    cliente_cedula = Sequence(lambda n: str(1000000000 + n))

    # Items - genera 1-3 items por defecto
    items = LazyAttribute(lambda _: [InvoiceItemFactory() for _ in range(factory.Faker._get_faker().random_int(min=1, max=3))])

    # Totales calculados
    subtotal = LazyAttribute(lambda o: sum(item.get("subtotal", 0) for item in o.items))
    descuento = 0.0
    impuesto = LazyAttribute(lambda o: o.subtotal * 0.19)
    total = LazyAttribute(lambda o: o.subtotal - o.descuento + o.impuesto)

    # Estado
    estado = InvoiceStatus.BORRADOR.value

    # Vendedor
    vendedor_id = Sequence(lambda n: n + 1)

    # Fecha de pago
    fecha_pago = None

    # Input original
    input_type = "TEXTO"
    input_raw = None

    # Procesamiento n8n
    n8n_processed = False
    n8n_response = None

    class Params:
        """
        Parámetros para variantes comunes.

        Uso:
            pendiente = InvoiceFactory(pendiente=True)
            pagada = InvoiceFactory(pagada=True)
            anulada = InvoiceFactory(anulada=True)
        """
        # Factura pendiente (lista para pago)
        pendiente = factory.Trait(
            estado=InvoiceStatus.PENDIENTE.value
        )

        # Alias para compatibilidad con tests existentes
        finalizada = factory.Trait(
            estado=InvoiceStatus.PENDIENTE.value
        )

        pagada = factory.Trait(
            estado=InvoiceStatus.PAGADA.value,
            fecha_pago=LazyAttribute(lambda _: datetime.utcnow())
        )

        anulada = factory.Trait(
            estado=InvoiceStatus.ANULADA.value
        )

        # Procesada por n8n
        procesada_n8n = factory.Trait(
            n8n_processed=True,
            n8n_response=factory.LazyFunction(lambda: {
                "success": True,
                "items_extracted": 2,
                "confidence": 0.95,
            })
        )

        # Input de voz
        input_voz = factory.Trait(
            input_type="VOZ",
            input_raw="/tmp/audio_12345.ogg"
        )

        # Input de foto
        input_foto = factory.Trait(
            input_type="FOTO",
            input_raw="/tmp/photo_12345.jpg"
        )

        # Factura con descuento
        con_descuento = factory.Trait(
            descuento=LazyAttribute(lambda o: o.subtotal * 0.1)  # 10% descuento
        )

    @classmethod
    def create_with_items(cls, num_items: int = 3, **kwargs) -> "Invoice":
        """
        Crea una factura con número específico de items.

        Args:
            num_items: Número de items a crear
            **kwargs: Atributos adicionales

        Returns:
            Factura creada con items
        """
        items = [InvoiceItemFactory() for _ in range(num_items)]
        return cls.create(items=items, **kwargs)

    @classmethod
    def create_for_organization(
        cls,
        organization_id: str,
        count: int = 1,
        **kwargs
    ) -> List["Invoice"]:
        """
        Crea múltiples facturas para una organización.

        Args:
            organization_id: ID de la organización
            count: Número de facturas
            **kwargs: Atributos adicionales

        Returns:
            Lista de facturas creadas
        """
        return cls.create_batch(count, organization_id=organization_id, **kwargs)


class InvoiceDictFactory(DictFactory):
    """
    Factory para crear diccionarios de factura (sin persistencia).

    Útil para tests de API o validación.

    Ejemplo:
        data = InvoiceDictFactory()
        response = client.post("/invoices", json=data)
    """

    class Meta:
        model = dict

    cliente_nombre = Faker("name", locale="es_CO")
    cliente_direccion = Faker("address", locale="es_CO")
    cliente_ciudad = LazyAttribute(lambda _: _random_colombian_city())
    cliente_email = Faker("email")
    cliente_telefono = LazyAttribute(lambda _: f"+5731{factory.Faker._get_faker().random_number(digits=8, fix_len=True)}")
    cliente_cedula = Sequence(lambda n: str(1000000000 + n))

    items = LazyAttribute(lambda _: [
        {"descripcion": "Anillo de oro 18k", "cantidad": 1, "precio": 850000},
        {"descripcion": "Cadena de plata 925", "cantidad": 1, "precio": 120000},
    ])


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _random_jewelry_description() -> str:
    """Genera una descripción aleatoria de joyería."""
    import random

    tipos = ["Anillo", "Collar", "Pulsera", "Aretes", "Dije", "Cadena", "Brazalete"]
    materiales = ["oro 18k", "oro 14k", "plata 925", "oro rosa", "platino"]
    estilos = ["clásico", "moderno", "vintage", "minimalista", "elegante"]
    piedras = ["con diamante", "con esmeralda", "con rubí", "con zafiro", "liso", ""]

    tipo = random.choice(tipos)
    material = random.choice(materiales)
    estilo = random.choice(estilos)
    piedra = random.choice(piedras)

    desc = f"{tipo} de {material} {estilo}"
    if piedra:
        desc += f" {piedra}"

    return desc


def _random_jewelry_price() -> int:
    """Genera un precio aleatorio de joyería."""
    import random

    # Rangos de precio más comunes
    ranges = [
        (50000, 200000),     # Joyería básica
        (200000, 500000),    # Joyería media
        (500000, 1500000),   # Joyería alta
        (1500000, 5000000),  # Joyería premium
    ]

    # Peso hacia precios más bajos
    weights = [40, 35, 20, 5]
    selected_range = random.choices(ranges, weights=weights)[0]

    return random.randint(*selected_range)


def _random_colombian_city() -> str:
    """Retorna una ciudad colombiana aleatoria."""
    import random

    cities = [
        "Bogota", "Medellin", "Cali", "Barranquilla", "Cartagena",
        "Bucaramanga", "Cucuta", "Pereira", "Santa Marta", "Manizales",
        "Ibague", "Villavicencio", "Armenia", "Pasto", "Neiva"
    ]
    return random.choice(cities)
