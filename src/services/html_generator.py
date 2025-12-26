"""
Servicio de Generacion de HTML para Facturas

Genera HTML profesional para facturas de joyeria PARADISE GROUP.
El HTML generado es enviado a n8n para conversion a PDF.

Plantilla basada en diseno oficial de PARADISE GROUP:
- Header con logo y datos del emisor
- Seccion de datos del cliente
- Tabla de items (hasta 6 productos)
- Totales con Subtotal, Descuento, IVA, Total
- Footer con agradecimiento

Arquitectura:
- Usa ThemeFactory para colores/fuentes configurables por tenant
- Soporta multiples plantillas para SaaS multi-tenant
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass

from config.settings import settings
from src.utils.logger import get_logger
from src.services.theme_constants import (
    ThemeFactory,
    DEFAULT_COLORS,
    DEFAULT_COMPANY,
    DEFAULT_TEXTS
)

logger = get_logger(__name__)


@dataclass
class InvoiceData:
    """Datos estructurados para generar factura HTML"""
    numero_factura: str
    fecha_emision: str
    fecha_vencimiento: Optional[str] = None

    # Cliente
    cliente_nombre: str = "Cliente"
    cliente_direccion: Optional[str] = None
    cliente_ciudad: Optional[str] = None
    cliente_pais: Optional[str] = None
    cliente_email: Optional[str] = None
    cliente_telefono: Optional[str] = None
    cliente_cedula: Optional[str] = None

    # Items
    items: List[Dict[str, Any]] = None

    # Totales
    subtotal: float = 0.0
    descuento: float = 0.0
    impuesto: float = 0.0
    total: float = 0.0

    # Vendedor/Emisor
    vendedor_nombre: Optional[str] = None
    vendedor_cedula: Optional[str] = None

    # Datos del emisor (PARADISE GROUP)
    emisor_nombre: str = "PARADISE GROUP"
    emisor_contacto: str = "Ryan Deivis"
    emisor_direccion: str = "Calle 555, Cartagena"
    emisor_pais: str = "Colombia"
    emisor_email: str = "ryandeivis@icloud.com"

    # Extras
    notas: Optional[str] = None
    organization_id: Optional[str] = None

    def __post_init__(self):
        if self.items is None:
            self.items = []


class HTMLGeneratorService:
    """
    Servicio para generar HTML de facturas PARADISE GROUP.

    Genera HTML profesional listo para conversion a PDF.
    Diseno basado en la plantilla oficial de Google Docs.
    """

    # Colores originales (dorado joyeria)
    PRIMARY_COLOR = "#c9a227"   # Dorado principal
    PRIMARY_DARK = "#a8851f"    # Dorado oscuro
    HEADER_BG = "#fef9e7"       # Fondo claro dorado
    BORDER_COLOR = "#d4ac0d"    # Borde dorado

    def __init__(self):
        self.tax_rate = settings.TAX_RATE

    def generate(self, data: Dict[str, Any]) -> str:
        """
        Genera HTML de factura desde diccionario de datos.

        Args:
            data: Diccionario con datos de la factura

        Returns:
            String HTML completo de la factura
        """
        invoice = self._parse_invoice_data(data)
        return self._render_html(invoice)

    def generate_from_invoice(self, invoice_data: InvoiceData) -> str:
        """
        Genera HTML desde objeto InvoiceData.

        Args:
            invoice_data: Objeto InvoiceData estructurado

        Returns:
            String HTML completo de la factura
        """
        return self._render_html(invoice_data)

    def _parse_invoice_data(self, data: Dict[str, Any]) -> InvoiceData:
        """Convierte diccionario a InvoiceData"""
        return InvoiceData(
            numero_factura=data.get("numero_factura", "BORRADOR"),
            fecha_emision=data.get("fecha_emision", datetime.now().strftime("%Y-%m-%d")),
            fecha_vencimiento=data.get("fecha_vencimiento"),
            cliente_nombre=data.get("cliente_nombre", "Cliente"),
            cliente_direccion=data.get("cliente_direccion"),
            cliente_ciudad=data.get("cliente_ciudad"),
            cliente_pais=data.get("cliente_pais", "Colombia"),
            cliente_email=data.get("cliente_email"),
            cliente_telefono=data.get("cliente_telefono"),
            cliente_cedula=data.get("cliente_cedula"),
            items=data.get("items", []),
            subtotal=data.get("subtotal", 0),
            descuento=data.get("descuento", 0),
            impuesto=data.get("impuesto", 0),
            total=data.get("total", 0),
            vendedor_nombre=data.get("vendedor_nombre"),
            vendedor_cedula=data.get("vendedor_cedula"),
            notas=data.get("notas"),
            organization_id=data.get("organization_id")
        )

    def _format_currency(self, amount: float) -> str:
        """Formatea numero como moneda COP"""
        return f"${amount:,.0f}".replace(",", ".")

    def _get_styles(self) -> str:
        """
        Genera estilos CSS para la plantilla PARADISE GROUP.
        Diseno moderno con cards, sombras y efectos elegantes.
        Colores dorados y fuente sans-serif.

        IMPORTANTE: Solo CSS puro, sin JavaScript.
        Incluye prefijos -webkit- para compatibilidad con iOS Safari.
        """
        return '''
        * {
            margin: 0;
            padding: 0;
            -webkit-box-sizing: border-box;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            font-size: 14px;
            color: #2d3748;
            /* Fallback color solido para iOS */
            background-color: #f5f3ed;
            /* Gradiente con prefijo webkit */
            background: -webkit-linear-gradient(315deg, #f8f6f0 0%, #ebe8e0 100%);
            background: linear-gradient(135deg, #f8f6f0 0%, #ebe8e0 100%);
            padding: 24px;
            min-height: 100vh;
            /* iOS text rendering */
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }

        .invoice-container {
            max-width: 900px;
            margin: 0 auto;
            background: #ffffff;
            /* Prefijos webkit para border-radius */
            -webkit-border-radius: 20px;
            border-radius: 20px;
            /* Prefijos webkit para box-shadow */
            -webkit-box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.15);
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.15);
            overflow: hidden;
        }

        /* Header - Hero Section */
        /* Fallback: color solido para iOS que no soporte background-clip */
        .company-name {
            text-align: center;
            font-size: 42px;
            font-weight: 800;
            /* Fallback color solido */
            color: #c9a227;
            /* Gradiente con clip - webkit primero para iOS */
            background: -webkit-linear-gradient(315deg, #c9a227 0%, #e8c84a 50%, #c9a227 100%);
            background: linear-gradient(135deg, #c9a227 0%, #e8c84a 50%, #c9a227 100%);
            -webkit-background-clip: text;
            background-clip: text;
            -webkit-text-fill-color: transparent;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            padding: 40px 30px 15px;
            letter-spacing: 4px;
            text-transform: uppercase;
        }

        .invoice-title {
            text-align: center;
            font-size: 13px;
            font-weight: 600;
            color: #ffffff;
            /* Fallback + webkit gradient para iOS */
            background-color: #c9a227;
            background: -webkit-linear-gradient(0deg, #c9a227 0%, #d4ac0d 50%, #c9a227 100%);
            background: linear-gradient(90deg, #c9a227 0%, #d4ac0d 50%, #c9a227 100%);
            padding: 12px 0;
            margin: 0 40px 30px;
            -webkit-border-radius: 30px;
            border-radius: 30px;
            letter-spacing: 3px;
            text-transform: uppercase;
            -webkit-box-shadow: 0 4px 15px rgba(201, 162, 39, 0.3);
            box-shadow: 0 4px 15px rgba(201, 162, 39, 0.3);
        }

        /* Content wrapper */
        .content-wrapper {
            padding: 0 40px 40px;
        }

        /* Seccion de facturado por e info factura */
        .header-section {
            display: -webkit-box;
            display: -webkit-flex;
            display: flex;
            -webkit-box-pack: justify;
            -webkit-justify-content: space-between;
            justify-content: space-between;
            gap: 24px;
            margin-bottom: 30px;
        }

        .emisor-info {
            -webkit-box-flex: 1;
            -webkit-flex: 1;
            flex: 1;
            /* Fallback + webkit gradient */
            background-color: #fafafa;
            background: -webkit-linear-gradient(305deg, #fefefe, #f8f8f8);
            background: linear-gradient(145deg, #fefefe, #f8f8f8);
            -webkit-border-radius: 16px;
            border-radius: 16px;
            padding: 24px;
            border-left: 4px solid #c9a227;
            -webkit-box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        }

        .emisor-info .label {
            font-weight: 700;
            font-size: 11px;
            color: #c9a227;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            margin-bottom: 12px;
            display: block;
        }

        .emisor-info p {
            margin: 6px 0;
            font-size: 13px;
            color: #4a5568;
            line-height: 1.5;
        }

        .factura-info {
            /* Fallback + webkit gradient */
            background-color: #fef8e0;
            background: -webkit-linear-gradient(305deg, #fffbeb, #fef3c7);
            background: linear-gradient(145deg, #fffbeb, #fef3c7);
            -webkit-border-radius: 16px;
            border-radius: 16px;
            padding: 20px 24px;
            -webkit-box-shadow: 0 4px 6px -1px rgba(201, 162, 39, 0.1);
            box-shadow: 0 4px 6px -1px rgba(201, 162, 39, 0.1);
        }

        .factura-info table {
            border-collapse: collapse;
        }

        .factura-info td {
            padding: 8px 12px;
            font-size: 13px;
        }

        .factura-info td:first-child {
            text-align: right;
            color: #92702c;
            font-weight: 600;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .factura-info td:last-child {
            font-weight: 500;
            color: #2d3748;
        }

        /* Tab-style section titles */
        .section-title {
            /* Fallback + webkit gradient */
            background-color: #c9a227;
            background: -webkit-linear-gradient(0deg, #c9a227 0%, #d4ac0d 100%);
            background: linear-gradient(90deg, #c9a227 0%, #d4ac0d 100%);
            color: #fff;
            display: inline-block;
            padding: 10px 28px;
            font-weight: 600;
            font-size: 12px;
            letter-spacing: 2px;
            text-transform: uppercase;
            -webkit-border-radius: 25px 25px 0 0;
            border-radius: 25px 25px 0 0;
            margin-bottom: 0;
            -webkit-box-shadow: 0 -4px 15px rgba(201, 162, 39, 0.2);
            box-shadow: 0 -4px 15px rgba(201, 162, 39, 0.2);
            position: relative;
            top: 1px;
        }

        /* Card para datos del cliente */
        .cliente-card {
            background: #fff;
            border: 1px solid #e8e1d0;
            -webkit-border-radius: 0 16px 16px 16px;
            border-radius: 0 16px 16px 16px;
            padding: 0;
            margin-bottom: 30px;
            overflow: hidden;
            -webkit-box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
        }

        .cliente-table {
            width: 100%;
            border-collapse: collapse;
        }

        .cliente-table td {
            padding: 14px 18px;
            font-size: 13px;
            border-bottom: 1px solid #f0ebe0;
        }

        .cliente-table tr:last-child td {
            border-bottom: none;
        }

        .cliente-table td:first-child,
        .cliente-table td:nth-child(3) {
            font-weight: 600;
            width: 15%;
            color: #92702c;
            /* Fallback + webkit gradient */
            background-color: #fefbf3;
            background: -webkit-linear-gradient(0deg, #fefbf3 0%, #fff 100%);
            background: linear-gradient(90deg, #fefbf3 0%, #fff 100%);
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .cliente-table td:nth-child(2),
        .cliente-table td:nth-child(4) {
            width: 35%;
            color: #2d3748;
        }

        /* Card para items */
        .items-card {
            background: #fff;
            -webkit-border-radius: 16px;
            border-radius: 16px;
            overflow: hidden;
            margin-bottom: 30px;
            -webkit-box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
            border: 1px solid #e8e1d0;
        }

        .items-table {
            width: 100%;
            border-collapse: collapse;
        }

        .items-table th {
            /* Fallback + webkit gradient */
            background-color: #faf8f0;
            background: -webkit-linear-gradient(270deg, #fefbf3 0%, #faf6eb 100%);
            background: linear-gradient(180deg, #fefbf3 0%, #faf6eb 100%);
            padding: 16px 14px;
            font-size: 11px;
            font-weight: 700;
            text-align: center;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #92702c;
            border-bottom: 2px solid #c9a227;
        }

        .items-table th:nth-child(1) { width: 6%; }
        .items-table th:nth-child(2) { width: 44%; text-align: left; padding-left: 20px; }
        .items-table th:nth-child(3) { width: 10%; }
        .items-table th:nth-child(4) { width: 20%; }
        .items-table th:nth-child(5) { width: 20%; }

        .items-table td {
            padding: 18px 14px;
            font-size: 13px;
            vertical-align: middle;
            border-bottom: 1px solid #f0ebe0;
            /* Transicion con webkit */
            -webkit-transition: background 0.2s ease;
            transition: background 0.2s ease;
        }

        /* Hover solo funciona en dispositivos con mouse, no afecta iOS touch */
        .items-table tbody tr:hover td {
            background: #fffdf5;
        }

        .items-table td:nth-child(1) {
            text-align: center;
            color: #a0aec0;
            font-weight: 500;
        }
        .items-table td:nth-child(2) { padding-left: 20px; }
        .items-table td:nth-child(3) { text-align: center; font-weight: 600; }
        .items-table td:nth-child(4) { text-align: right; color: #4a5568; }
        .items-table td:nth-child(5) {
            text-align: right;
            font-weight: 700;
            color: #2d3748;
        }

        .items-table tr:last-child td {
            border-bottom: none;
        }

        .items-table tr.empty-row td {
            height: 50px;
            background: #fefefe;
        }

        .items-table tr.empty-row:hover td {
            background: #fefefe;
        }

        .item-name {
            font-weight: 600;
            color: #2d3748;
            font-size: 14px;
        }

        .item-desc {
            font-size: 12px;
            color: #718096;
            margin-top: 6px;
            font-style: italic;
        }

        /* Totals card */
        .totals-section {
            display: -webkit-box;
            display: -webkit-flex;
            display: flex;
            -webkit-box-pack: end;
            -webkit-justify-content: flex-end;
            justify-content: flex-end;
            margin-bottom: 30px;
        }

        .totals-card {
            /* Fallback + webkit gradient */
            background-color: #fef8e0;
            background: -webkit-linear-gradient(305deg, #fffbeb, #fef3c7);
            background: linear-gradient(145deg, #fffbeb, #fef3c7);
            -webkit-border-radius: 16px;
            border-radius: 16px;
            padding: 24px;
            min-width: 320px;
            -webkit-box-shadow: 0 4px 15px rgba(201, 162, 39, 0.15);
            box-shadow: 0 4px 15px rgba(201, 162, 39, 0.15);
        }

        .totals-table {
            width: 100%;
            border-collapse: collapse;
        }

        .totals-table td {
            padding: 10px 4px;
            font-size: 14px;
        }

        .totals-table td:first-child {
            text-align: left;
            font-weight: 500;
            color: #92702c;
        }

        .totals-table td:last-child {
            text-align: right;
            color: #2d3748;
            font-weight: 500;
        }

        .totals-table tr.total-row {
            border-top: 2px solid #c9a227;
        }

        .totals-table tr.total-row td {
            padding-top: 18px;
            font-weight: 800;
            font-size: 18px;
        }

        .totals-table tr.total-row td:first-child {
            color: #c9a227;
        }

        .totals-table tr.total-row td:last-child {
            color: #c9a227;
        }

        /* Footer card */
        .footer {
            /* Fallback + webkit gradient */
            background-color: #1a1a2e;
            background: -webkit-linear-gradient(270deg, #1a1a2e 0%, #16213e 100%);
            background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
            text-align: center;
            padding: 35px 40px;
            margin-top: 0;
        }

        .footer .gracias {
            font-weight: 700;
            font-size: 18px;
            color: #c9a227;
            margin-bottom: 10px;
            letter-spacing: 3px;
            text-transform: uppercase;
        }

        .footer .terminos {
            font-size: 11px;
            color: #a0aec0;
            max-width: 400px;
            margin: 0 auto;
            line-height: 1.6;
        }

        /* Responsive - iOS y Android */
        @media (max-width: 768px) {
            body {
                padding: 12px;
            }

            .invoice-container {
                -webkit-border-radius: 16px;
                border-radius: 16px;
            }

            .company-name {
                font-size: 28px;
                padding: 30px 20px 10px;
            }

            .invoice-title {
                margin: 0 20px 20px;
                font-size: 11px;
            }

            .content-wrapper {
                padding: 0 20px 30px;
            }

            .header-section {
                -webkit-box-orient: vertical;
                -webkit-box-direction: normal;
                -webkit-flex-direction: column;
                flex-direction: column;
                gap: 16px;
            }

            .emisor-info,
            .factura-info {
                width: 100%;
            }

            .cliente-table td {
                display: block;
                width: 100% !important;
                padding: 10px 16px;
            }

            .cliente-table td:first-child,
            .cliente-table td:nth-child(3) {
                background: #fefbf3;
                padding-bottom: 4px;
            }

            .cliente-table td:nth-child(2),
            .cliente-table td:nth-child(4) {
                padding-top: 4px;
                padding-bottom: 14px;
            }

            .items-table {
                font-size: 12px;
            }

            .items-table th,
            .items-table td {
                padding: 12px 8px;
            }

            .totals-card {
                width: 100%;
                min-width: auto;
            }
        }

        /* Print styles */
        @media print {
            body {
                padding: 0;
                background: #fff;
            }
            .invoice-container {
                -webkit-box-shadow: none;
                box-shadow: none;
                -webkit-border-radius: 0;
                border-radius: 0;
            }
        }
        '''

    def _render_items_rows(self, items: List[Dict[str, Any]]) -> str:
        """Genera filas HTML de items (hasta 6 filas) con descripcion debajo del nombre"""
        rows = []

        # Generar filas de items existentes
        for idx, item in enumerate(items[:6], 1):
            nombre = item.get("nombre", item.get("descripcion", ""))
            descripcion = item.get("descripcion", "")
            if descripcion == nombre:
                descripcion = ""
            cantidad = item.get("cantidad", 1)
            precio = item.get("precio", 0)
            item_total = cantidad * precio

            # Descripcion debajo del nombre
            desc_html = ""
            if descripcion:
                desc_html = f'<div class="item-desc">{descripcion}</div>'

            row = f'''
            <tr>
                <td>{idx}</td>
                <td>
                    <div class="item-name">{nombre}</div>
                    {desc_html}
                </td>
                <td>{cantidad}</td>
                <td>{self._format_currency(precio)}</td>
                <td>{self._format_currency(item_total)}</td>
            </tr>
            '''
            rows.append(row)

        # Rellenar filas vacias hasta 6
        for idx in range(len(items) + 1, 7):
            row = f'''
            <tr class="empty-row">
                <td>{idx}</td>
                <td></td>
                <td></td>
                <td></td>
                <td></td>
            </tr>
            '''
            rows.append(row)

        return "\n".join(rows)

    def _render_html(self, invoice: InvoiceData) -> str:
        """Renderiza el HTML completo de la factura estilo PARADISE GROUP"""

        items_rows = self._render_items_rows(invoice.items)
        styles = self._get_styles()

        # Ciudad/Pais del cliente
        ciudad_pais = ""
        if invoice.cliente_ciudad:
            ciudad_pais = invoice.cliente_ciudad
            if invoice.cliente_pais:
                ciudad_pais += f", {invoice.cliente_pais}"
        elif invoice.cliente_pais:
            ciudad_pais = invoice.cliente_pais

        # Tasa de impuesto
        tax_percent = int(self.tax_rate * 100)

        html = f'''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Factura {invoice.numero_factura} - PARADISE GROUP</title>
    <style>
        {styles}
    </style>
</head>
<body>
    <div class="invoice-container">
        <!-- Titulo de la empresa -->
        <div class="company-name">PARADISE GROUP</div>

        <!-- Titulo factura - Tab pill -->
        <div class="invoice-title">FACTURA DE VENTA</div>

        <!-- Content wrapper para padding -->
        <div class="content-wrapper">
            <!-- Seccion header: Emisor e Info Factura como cards -->
            <div class="header-section">
                <div class="emisor-info">
                    <span class="label">FACTURADO POR</span>
                    <p>{invoice.emisor_contacto}</p>
                    <p>{invoice.emisor_direccion}</p>
                    <p>{invoice.emisor_pais}</p>
                    <p>{invoice.emisor_email}</p>
                </div>
                <div class="factura-info">
                    <table>
                        <tr>
                            <td>Factura N:</td>
                            <td>{invoice.numero_factura}</td>
                        </tr>
                        <tr>
                            <td>Fecha:</td>
                            <td>{invoice.fecha_emision}</td>
                        </tr>
                        <tr>
                            <td>Vence:</td>
                            <td>{invoice.fecha_vencimiento or "N/A"}</td>
                        </tr>
                    </table>
                </div>
            </div>

            <!-- Datos del cliente - Card con tab -->
            <div class="section-title">CLIENTE</div>
            <div class="cliente-card">
                <table class="cliente-table">
                    <tr>
                        <td>Nombre</td>
                        <td>{invoice.cliente_nombre or ""}</td>
                        <td>Cedula</td>
                        <td>{invoice.cliente_cedula or ""}</td>
                    </tr>
                    <tr>
                        <td>Telefono</td>
                        <td>{invoice.cliente_telefono or ""}</td>
                        <td>Email</td>
                        <td>{invoice.cliente_email or ""}</td>
                    </tr>
                    <tr>
                        <td>Direccion</td>
                        <td>{invoice.cliente_direccion or ""}</td>
                        <td>Ciudad</td>
                        <td>{ciudad_pais}</td>
                    </tr>
                </table>
            </div>

            <!-- Tabla de items - Card -->
            <div class="items-card">
                <table class="items-table">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Descripcion</th>
                            <th>Cant.</th>
                            <th>P. Unitario</th>
                            <th>Subtotal</th>
                        </tr>
                    </thead>
                    <tbody>
                        {items_rows}
                    </tbody>
                </table>
            </div>

            <!-- Totales - Card flotante -->
            <div class="totals-section">
                <div class="totals-card">
                    <table class="totals-table">
                        <tr>
                            <td>Subtotal</td>
                            <td>{self._format_currency(invoice.subtotal)}</td>
                        </tr>
                        <tr>
                            <td>Descuento</td>
                            <td>{self._format_currency(invoice.descuento)}</td>
                        </tr>
                        <tr>
                            <td>IVA ({tax_percent}%)</td>
                            <td>{self._format_currency(invoice.impuesto)}</td>
                        </tr>
                        <tr class="total-row">
                            <td>TOTAL A PAGAR</td>
                            <td>{self._format_currency(invoice.total)}</td>
                        </tr>
                    </table>
                </div>
            </div>
        </div>

        <!-- Footer - Dark elegant -->
        <div class="footer">
            <p class="gracias">GRACIAS POR SU COMPRA</p>
            <p class="terminos">Terminos y condiciones aplican. Conserve esta factura como comprobante de su compra.</p>
        </div>
    </div>
</body>
</html>'''

        logger.info(f"HTML generado para factura {invoice.numero_factura}")
        return html


# Instancia global (singleton)
html_generator = HTMLGeneratorService()