# ==============================================================================
# Data Generators for Load Testing
# ==============================================================================
"""
Generadores de datos de prueba para load testing.

Genera datos realistas para:
- Facturas con items de joyería
- Clientes con datos colombianos
- Organizaciones/tiendas

Nota: Intentamos reutilizar las factories existentes (Mejora 17).
Si no están disponibles, usamos generadores simples.
"""

import random
import string
from typing import Dict, Any, List
from datetime import datetime


# ==============================================================================
# DATOS DE REFERENCIA (Joyería colombiana)
# ==============================================================================

NOMBRES = [
    "María", "Carlos", "Ana", "José", "Laura", "Pedro", "Carmen", "Luis",
    "Patricia", "Jorge", "Sandra", "Miguel", "Rosa", "Antonio", "Diana",
    "Fernando", "Lucía", "Rafael", "Mónica", "Andrés", "Valentina", "Camilo"
]

APELLIDOS = [
    "García", "Rodríguez", "Martínez", "López", "González", "Hernández",
    "Pérez", "Sánchez", "Ramírez", "Torres", "Flores", "Rivera", "Gómez",
    "Díaz", "Reyes", "Morales", "Cruz", "Ortiz", "Gutiérrez", "Vargas"
]

CIUDADES = [
    "Bogotá", "Medellín", "Cali", "Barranquilla", "Cartagena",
    "Bucaramanga", "Pereira", "Santa Marta", "Manizales", "Pasto"
]

DIRECCIONES = [
    "Calle {n} # {a}-{b}",
    "Carrera {n} # {a}-{b}",
    "Avenida {n} # {a}-{b}",
    "Diagonal {n} # {a}-{b}",
    "Transversal {n} # {a}-{b}",
]

# Productos de joyería
PRODUCTOS_JOYERIA = [
    # Anillos
    {"nombre": "Anillo de Compromiso Oro 18K", "precio_base": 2500000, "categoria": "anillos"},
    {"nombre": "Anillo Solitario Diamante 0.5ct", "precio_base": 4500000, "categoria": "anillos"},
    {"nombre": "Argolla Matrimonio Oro Blanco", "precio_base": 1800000, "categoria": "anillos"},
    {"nombre": "Anillo Esmeralda Colombiana", "precio_base": 3200000, "categoria": "anillos"},

    # Collares
    {"nombre": "Collar Cadena Oro 18K 50cm", "precio_base": 1200000, "categoria": "collares"},
    {"nombre": "Gargantilla Perlas Cultivadas", "precio_base": 850000, "categoria": "collares"},
    {"nombre": "Collar con Dije Corazón", "precio_base": 980000, "categoria": "collares"},
    {"nombre": "Cadena Plata 925 con Baño Oro", "precio_base": 320000, "categoria": "collares"},

    # Aretes
    {"nombre": "Aretes Topos Oro 18K", "precio_base": 450000, "categoria": "aretes"},
    {"nombre": "Aretes Argolla Plata 925", "precio_base": 180000, "categoria": "aretes"},
    {"nombre": "Aretes Diamante 0.25ct par", "precio_base": 2800000, "categoria": "aretes"},
    {"nombre": "Aretes Esmeralda Gota", "precio_base": 1500000, "categoria": "aretes"},

    # Pulseras
    {"nombre": "Pulsera Eslabones Oro 18K", "precio_base": 1800000, "categoria": "pulseras"},
    {"nombre": "Pulsera Tenis Diamantes 1ct", "precio_base": 6500000, "categoria": "pulseras"},
    {"nombre": "Brazalete Plata 925", "precio_base": 280000, "categoria": "pulseras"},
    {"nombre": "Pulsera Perlas Naturales", "precio_base": 650000, "categoria": "pulseras"},

    # Relojes
    {"nombre": "Reloj Oro 18K Caballero", "precio_base": 4200000, "categoria": "relojes"},
    {"nombre": "Reloj Plata Dama", "precio_base": 890000, "categoria": "relojes"},

    # Otros
    {"nombre": "Dije Cruz Oro 18K", "precio_base": 380000, "categoria": "dijes"},
    {"nombre": "Piercing Nariz Oro 14K", "precio_base": 120000, "categoria": "piercings"},
]

NOMBRES_TIENDAS = [
    "Joyería El Dorado", "Brillantes del Caribe", "Oro y Plata Express",
    "Casa de las Esmeraldas", "Joyas del Valle", "Diamantes Bogotá",
    "Perlas del Pacífico", "Tesoros de Colombia", "Elegancia en Oro"
]


# ==============================================================================
# GENERADORES
# ==============================================================================

def generate_cedula() -> str:
    """Genera una cédula colombiana ficticia."""
    return str(random.randint(10000000, 99999999))


def generate_telefono() -> str:
    """Genera un teléfono colombiano ficticio."""
    prefijos = ["300", "301", "302", "310", "311", "312", "320", "321"]
    return f"+57 {random.choice(prefijos)} {random.randint(1000000, 9999999)}"


def generate_email(nombre: str, apellido: str) -> str:
    """Genera un email basado en nombre."""
    dominios = ["gmail.com", "hotmail.com", "outlook.com", "yahoo.com"]
    nombre_clean = nombre.lower().replace(" ", "")
    apellido_clean = apellido.lower().replace(" ", "")
    return f"{nombre_clean}.{apellido_clean}{random.randint(1, 99)}@{random.choice(dominios)}"


def generate_direccion() -> str:
    """Genera una dirección colombiana ficticia."""
    template = random.choice(DIRECCIONES)
    return template.format(
        n=random.randint(1, 150),
        a=random.randint(1, 100),
        b=random.randint(1, 99)
    )


def generate_client_data() -> Dict[str, Any]:
    """
    Genera datos de cliente para factura.

    Returns:
        Dict con datos del cliente
    """
    nombre = random.choice(NOMBRES)
    apellido = random.choice(APELLIDOS)
    nombre_completo = f"{nombre} {apellido}"

    return {
        "cliente_nombre": nombre_completo,
        "cliente_cedula": generate_cedula(),
        "cliente_telefono": generate_telefono(),
        "cliente_email": generate_email(nombre, apellido),
        "cliente_direccion": generate_direccion(),
        "cliente_ciudad": random.choice(CIUDADES),
    }


def generate_invoice_item() -> Dict[str, Any]:
    """
    Genera un item de factura (producto de joyería).

    Returns:
        Dict con datos del item
    """
    producto = random.choice(PRODUCTOS_JOYERIA)

    # Variación de precio ±20%
    variacion = random.uniform(0.8, 1.2)
    precio = int(producto["precio_base"] * variacion)

    # Cantidad (usualmente 1 para joyería)
    cantidad = random.choices([1, 2, 3], weights=[85, 10, 5])[0]

    return {
        "descripcion": producto["nombre"],
        "cantidad": cantidad,
        "precio_unitario": precio,
        "subtotal": precio * cantidad,
        "categoria": producto["categoria"],
    }


def generate_invoice_data() -> Dict[str, Any]:
    """
    Genera datos completos de factura.

    Returns:
        Dict con todos los campos de una factura
    """
    # Datos del cliente
    client = generate_client_data()

    # Generar número de factura
    prefijo = random.choice(["FAC", "FV", "REC"])
    numero = random.randint(1000, 99999)
    numero_factura = f"{prefijo}-{numero:05d}"

    # Estado inicial
    estados = ["BORRADOR", "PENDIENTE"]
    estado = random.choice(estados)

    # Fecha
    now = datetime.utcnow()

    return {
        "numero_factura": numero_factura,
        **client,
        "items": [],  # Se agregan después
        "subtotal": 0,  # Se calcula
        "descuento": random.choice([0, 0, 0, 5, 10, 15]),  # % descuento
        "impuesto": 0,  # Se calcula (19% IVA)
        "total": 0,  # Se calcula
        "estado": estado,
        "notas": random.choice([
            "",
            "Cliente frecuente",
            "Pago en efectivo",
            "Incluye certificado de autenticidad",
            "Regalo - incluir empaque especial",
        ]),
    }


def generate_organization_data() -> Dict[str, Any]:
    """
    Genera datos de organización/tienda.

    Returns:
        Dict con datos de organización
    """
    nombre = random.choice(NOMBRES_TIENDAS)
    slug = nombre.lower().replace(" ", "-").replace("á", "a").replace("é", "e")

    return {
        "name": nombre,
        "slug": f"{slug}-{random.randint(100, 999)}",
        "plan": random.choice(["basic", "pro", "enterprise"]),
        "invoice_prefix": random.choice(["FAC", "FV", "REC", "JOY"]),
        "email": f"contacto@{slug.replace('-', '')}.com",
        "telefono": generate_telefono(),
        "direccion": generate_direccion(),
        "ciudad": random.choice(CIUDADES),
    }


# ==============================================================================
# TRY TO USE EXISTING FACTORIES (Mejora 17)
# ==============================================================================

try:
    from tests.factories import InvoiceDictFactory, UserDictFactory

    def generate_invoice_from_factory() -> Dict[str, Any]:
        """Usa factory existente si está disponible."""
        return InvoiceDictFactory.build()

except ImportError:
    # Factories no disponibles, usar generadores simples
    generate_invoice_from_factory = generate_invoice_data
