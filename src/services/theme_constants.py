"""
Constantes de Tema para Facturas

Define colores, fuentes y textos para las plantillas de factura.
Preparado para soportar múltiples temas/tenants en el futuro.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ThemeColors:
    """Paleta de colores para un tema de factura."""
    primary: str           # Color principal (dorado)
    primary_dark: str      # Color principal oscuro
    primary_light: str     # Color principal claro (fondos)
    header_bg: str         # Fondo del header
    border: str            # Color de bordes
    text_dark: str         # Texto oscuro
    text_medium: str       # Texto medio
    text_light: str        # Texto claro
    footer_bg: str         # Fondo del footer
    footer_bg_dark: str    # Fondo footer oscuro
    white: str             # Blanco
    card_bg: str           # Fondo de cards


@dataclass(frozen=True)
class ThemeFonts:
    """Fuentes para un tema de factura."""
    primary: str           # Fuente principal
    size_xs: str           # Tamaño extra pequeño
    size_sm: str           # Tamaño pequeño
    size_base: str         # Tamaño base
    size_lg: str           # Tamaño grande
    size_xl: str           # Tamaño extra grande
    size_2xl: str          # Tamaño 2x grande


@dataclass(frozen=True)
class CompanyInfo:
    """Información de la empresa emisora."""
    nombre: str
    contacto: str
    direccion: str
    pais: str
    email: str
    telefono: Optional[str] = None
    logo_url: Optional[str] = None


@dataclass(frozen=True)
class InvoiceTexts:
    """Textos fijos de la factura."""
    titulo: str
    factura_label: str
    cliente_label: str
    items_label: str
    gracias: str
    terminos: str


# ============================================================================
# TEMA POR DEFECTO: PARADISE GROUP (Joyería - Dorado elegante)
# ============================================================================

PARADISE_GROUP_COLORS = ThemeColors(
    primary="#c9a227",
    primary_dark="#a8851f",
    primary_light="#fef8e0",
    header_bg="#fef9e7",
    border="#d4ac0d",
    text_dark="#2d3748",
    text_medium="#4a5568",
    text_light="#a0aec0",
    footer_bg="#1a1a2e",
    footer_bg_dark="#16213e",
    white="#ffffff",
    card_bg="#fefbf3"
)

PARADISE_GROUP_FONTS = ThemeFonts(
    primary="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
    size_xs="11px",
    size_sm="12px",
    size_base="14px",
    size_lg="18px",
    size_xl="28px",
    size_2xl="42px"
)

PARADISE_GROUP_COMPANY = CompanyInfo(
    nombre="PARADISE GROUP",
    contacto="Ryan Deivis",
    direccion="Calle 555, Cartagena",
    pais="Colombia",
    email="ryandeivis@icloud.com",
    telefono=None,
    logo_url=None
)

PARADISE_GROUP_TEXTS = InvoiceTexts(
    titulo="FACTURA DE VENTA",
    factura_label="Factura N:",
    cliente_label="CLIENTE",
    items_label="Descripcion",
    gracias="GRACIAS POR SU COMPRA",
    terminos="Terminos y condiciones aplican. Conserve esta factura como comprobante de su compra."
)


# ============================================================================
# TEMA FACTORY - Para soportar múltiples tenants en el futuro
# ============================================================================

class ThemeFactory:
    """Factory para obtener temas por nombre/tenant."""

    _themes = {
        "paradise_group": {
            "colors": PARADISE_GROUP_COLORS,
            "fonts": PARADISE_GROUP_FONTS,
            "company": PARADISE_GROUP_COMPANY,
            "texts": PARADISE_GROUP_TEXTS
        }
    }

    _default = "paradise_group"

    @classmethod
    def get_theme(cls, name: str = None):
        """
        Obtiene un tema por nombre.

        Args:
            name: Nombre del tema (o None para default)

        Returns:
            Dict con colors, fonts, company, texts
        """
        theme_name = name or cls._default
        return cls._themes.get(theme_name, cls._themes[cls._default])

    @classmethod
    def get_colors(cls, name: str = None) -> ThemeColors:
        """Obtiene los colores del tema."""
        return cls.get_theme(name)["colors"]

    @classmethod
    def get_fonts(cls, name: str = None) -> ThemeFonts:
        """Obtiene las fuentes del tema."""
        return cls.get_theme(name)["fonts"]

    @classmethod
    def get_company(cls, name: str = None) -> CompanyInfo:
        """Obtiene la info de la empresa del tema."""
        return cls.get_theme(name)["company"]

    @classmethod
    def get_texts(cls, name: str = None) -> InvoiceTexts:
        """Obtiene los textos del tema."""
        return cls.get_theme(name)["texts"]

    @classmethod
    def register_theme(
        cls,
        name: str,
        colors: ThemeColors,
        fonts: ThemeFonts,
        company: CompanyInfo,
        texts: InvoiceTexts
    ):
        """
        Registra un nuevo tema (para SaaS multi-tenant).

        Args:
            name: Nombre único del tema
            colors: Paleta de colores
            fonts: Fuentes
            company: Info de empresa
            texts: Textos
        """
        cls._themes[name] = {
            "colors": colors,
            "fonts": fonts,
            "company": company,
            "texts": texts
        }


# Alias para acceso rápido
DEFAULT_COLORS = PARADISE_GROUP_COLORS
DEFAULT_FONTS = PARADISE_GROUP_FONTS
DEFAULT_COMPANY = PARADISE_GROUP_COMPANY
DEFAULT_TEXTS = PARADISE_GROUP_TEXTS