"""
Servicio de Generación de HTML para Facturas

Genera HTML profesional para facturas de joyería.
El HTML generado es enviado a n8n para conversión a PDF.

Características:
- CSS-only (sin JavaScript) para compatibilidad iOS
- Fully responsive (mobile-first)
- Optimizado para iOS Safari y dispositivos táctiles
- Soporte multi-tenant (organization branding futuro)

Flujo:
1. Bot genera HTML con este servicio
2. Bot envía HTML a n8n/pdf webhook
3. n8n convierte HTML → PDF via Google Docs
4. n8n retorna PDF al bot
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass

from config.settings import settings
from src.utils.logger import get_logger

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

    # Vendedor
    vendedor_nombre: Optional[str] = None
    vendedor_cedula: Optional[str] = None

    # Extras
    notas: Optional[str] = None
    organization_id: Optional[str] = None

    def __post_init__(self):
        if self.items is None:
            self.items = []


class HTMLGeneratorService:
    """
    Servicio para generar HTML de facturas.

    Genera HTML profesional listo para conversión a PDF.
    Compatible con iOS Safari (CSS-only, sin JavaScript).
    Responsive para móvil, tablet y desktop.
    """

    # Color primario (dorado joyería)
    PRIMARY_COLOR = "#c9a227"
    PRIMARY_DARK = "#a8851f"
    PRIMARY_LIGHT = "#d4b44a"

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
        """Formatea número como moneda COP"""
        return f"${amount:,.0f}".replace(",", ".")

    def _get_styles(self) -> str:
        """
        Genera estilos CSS optimizados para iOS y responsive.

        Características:
        - CSS-only (sin JavaScript)
        - iOS Safari compatible
        - Mobile-first responsive
        - Touch-friendly
        """
        return f'''
        /* ============================================
           VARIABLES Y RESET
           ============================================ */
        :root {{
            --primary: {self.PRIMARY_COLOR};
            --primary-dark: {self.PRIMARY_DARK};
            --primary-light: {self.PRIMARY_LIGHT};
            --text-dark: #1f2937;
            --text-medium: #4b5563;
            --text-light: #9ca3af;
            --bg-white: #ffffff;
            --bg-gray: #f9fafb;
            --bg-light: #f3f4f6;
            --border-light: #e5e7eb;
            --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
            --shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
            --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1);
            --radius: 0.5rem;
            --radius-lg: 1rem;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        /* ============================================
           BASE - iOS OPTIMIZADO
           ============================================ */
        html {{
            scroll-behavior: smooth;
            -webkit-overflow-scrolling: touch;
            overflow-x: hidden;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: var(--bg-gray);
            color: var(--text-dark);
            line-height: 1.6;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
            overflow-x: hidden;
            width: 100%;
            max-width: 100vw;
            /* iOS: habilitar :active */
            -webkit-tap-highlight-color: transparent;
            padding: 16px;
        }}

        /* ============================================
           CONTAINER PRINCIPAL
           ============================================ */
        .invoice-container {{
            max-width: 800px;
            margin: 0 auto;
            background: var(--bg-white);
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow-lg);
            overflow: hidden;
        }}

        /* ============================================
           HEADER
           ============================================ */
        .header {{
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
            color: var(--bg-white);
            padding: 24px;
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            flex-wrap: wrap;
            gap: 16px;
        }}

        .logo h1 {{
            font-size: clamp(1.5rem, 4vw, 2rem);
            font-weight: 700;
            margin: 0;
            letter-spacing: 0.05em;
        }}

        .logo p {{
            font-size: 0.875rem;
            opacity: 0.9;
            margin: 4px 0 0;
        }}

        .invoice-info {{
            text-align: right;
        }}

        .invoice-info h2 {{
            font-size: clamp(1.25rem, 3vw, 1.5rem);
            font-weight: 600;
            margin: 0 0 8px;
        }}

        .invoice-info p {{
            margin: 4px 0;
            font-size: 0.875rem;
            opacity: 0.9;
        }}

        .invoice-info strong {{
            opacity: 1;
        }}

        /* ============================================
           SECCIONES
           ============================================ */
        .section {{
            padding: 20px 24px;
            border-bottom: 1px solid var(--border-light);
        }}

        .section:last-of-type {{
            border-bottom: none;
        }}

        .section-title {{
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--primary);
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 2px solid var(--bg-light);
        }}

        /* ============================================
           CLIENTE INFO
           ============================================ */
        .client-info {{
            display: grid;
            gap: 6px;
        }}

        .client-info p {{
            margin: 0;
            color: var(--text-medium);
            font-size: 0.9375rem;
        }}

        .client-info p strong {{
            color: var(--text-dark);
            font-size: 1.0625rem;
        }}

        .client-info .client-detail {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .client-info .icon {{
            width: 16px;
            height: 16px;
            color: var(--primary);
            flex-shrink: 0;
        }}

        /* ============================================
           TABLA DE ITEMS - RESPONSIVE
           ============================================ */
        .items-wrapper {{
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            margin: 0 -24px;
            padding: 0 24px;
        }}

        .items-table {{
            width: 100%;
            border-collapse: collapse;
            min-width: 500px;
        }}

        .items-table th {{
            background: var(--bg-light);
            padding: 12px 10px;
            text-align: left;
            font-weight: 600;
            font-size: 0.8125rem;
            color: var(--text-dark);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            border-bottom: 2px solid var(--primary);
            white-space: nowrap;
        }}

        .items-table th:nth-child(1) {{ width: 8%; text-align: center; }}
        .items-table th:nth-child(2) {{ width: 42%; }}
        .items-table th:nth-child(3) {{ width: 12%; text-align: center; }}
        .items-table th:nth-child(4) {{ width: 19%; text-align: right; }}
        .items-table th:nth-child(5) {{ width: 19%; text-align: right; }}

        .items-table td {{
            padding: 14px 10px;
            border-bottom: 1px solid var(--border-light);
            font-size: 0.9375rem;
            color: var(--text-medium);
            vertical-align: top;
        }}

        .items-table td:nth-child(1) {{ text-align: center; color: var(--text-light); }}
        .items-table td:nth-child(3) {{ text-align: center; }}
        .items-table td:nth-child(4) {{ text-align: right; }}
        .items-table td:nth-child(5) {{ text-align: right; font-weight: 600; color: var(--text-dark); }}

        .items-table tbody tr {{
            transition: background 0.15s ease;
            -webkit-tap-highlight-color: rgba(201, 162, 39, 0.1);
        }}

        /* iOS: efecto táctil */
        @media (hover: none) and (pointer: coarse) {{
            .items-table tbody tr:active {{
                background: var(--bg-light);
            }}
        }}

        .items-table tbody tr:hover {{
            background: var(--bg-gray);
        }}

        .item-name {{
            font-weight: 500;
            color: var(--text-dark);
        }}

        .item-desc {{
            font-size: 0.8125rem;
            color: var(--text-light);
            margin-top: 2px;
        }}

        /* ============================================
           TOTALES
           ============================================ */
        .totals {{
            padding: 20px 24px;
            background: var(--bg-gray);
        }}

        .totals-table {{
            margin-left: auto;
            width: 100%;
            max-width: 300px;
        }}

        .totals-table td {{
            padding: 8px 0;
            font-size: 0.9375rem;
        }}

        .totals-table td:first-child {{
            color: var(--text-medium);
        }}

        .totals-table td:last-child {{
            text-align: right;
            font-weight: 500;
            color: var(--text-dark);
        }}

        .totals-table .total-row td {{
            padding-top: 12px;
            font-size: 1.25rem;
            font-weight: 700;
            border-top: 2px solid var(--primary);
        }}

        .totals-table .total-row td:last-child {{
            color: var(--primary);
        }}

        .totals-table .discount td {{
            color: #10b981;
        }}

        /* ============================================
           NOTAS
           ============================================ */
        .notes {{
            background: var(--bg-light);
            padding: 16px;
            border-radius: var(--radius);
            color: var(--text-medium);
            font-size: 0.875rem;
            font-style: italic;
            border-left: 3px solid var(--primary);
        }}

        /* ============================================
           FOOTER
           ============================================ */
        .footer {{
            padding: 20px 24px;
            background: var(--bg-light);
            text-align: center;
        }}

        .footer p {{
            margin: 4px 0;
            font-size: 0.8125rem;
            color: var(--text-light);
        }}

        .footer .vendedor {{
            font-size: 0.875rem;
            color: var(--text-medium);
            font-weight: 500;
        }}

        /* ============================================
           RESPONSIVE - TABLET (768px)
           ============================================ */
        @media (max-width: 768px) {{
            body {{
                padding: 12px;
            }}

            .header {{
                padding: 20px;
                flex-direction: column;
                text-align: center;
            }}

            .invoice-info {{
                text-align: center;
                width: 100%;
            }}

            .section {{
                padding: 16px 20px;
            }}

            .items-wrapper {{
                margin: 0 -20px;
                padding: 0 20px;
            }}

            .totals {{
                padding: 16px 20px;
            }}

            .totals-table {{
                max-width: 100%;
            }}
        }}

        /* ============================================
           RESPONSIVE - MÓVIL (480px)
           ============================================ */
        @media (max-width: 480px) {{
            body {{
                padding: 8px;
            }}

            .header {{
                padding: 16px;
            }}

            .logo h1 {{
                font-size: 1.5rem;
            }}

            .section {{
                padding: 14px 16px;
            }}

            .section-title {{
                font-size: 0.6875rem;
            }}

            .items-wrapper {{
                margin: 0 -16px;
                padding: 0 16px;
            }}

            .items-table th,
            .items-table td {{
                padding: 10px 6px;
                font-size: 0.8125rem;
            }}

            .totals {{
                padding: 14px 16px;
            }}

            .totals-table td {{
                font-size: 0.875rem;
            }}

            .totals-table .total-row td {{
                font-size: 1.125rem;
            }}

            .footer {{
                padding: 16px;
            }}
        }}

        /* ============================================
           RESPONSIVE - MÓVIL PEQUEÑO (360px)
           ============================================ */
        @media (max-width: 360px) {{
            body {{
                padding: 4px;
            }}

            .header {{
                padding: 12px;
            }}

            .section {{
                padding: 12px;
            }}

            .items-wrapper {{
                margin: 0 -12px;
                padding: 0 12px;
            }}

            .items-table {{
                min-width: 400px;
            }}

            .items-table th,
            .items-table td {{
                padding: 8px 4px;
                font-size: 0.75rem;
            }}

            .totals {{
                padding: 12px;
            }}

            .footer {{
                padding: 12px;
            }}

            .footer p {{
                font-size: 0.75rem;
            }}
        }}

        /* ============================================
           PRINT STYLES
           ============================================ */
        @media print {{
            body {{
                background: white;
                padding: 0;
            }}

            .invoice-container {{
                box-shadow: none;
                border-radius: 0;
            }}

            .items-table tbody tr:hover {{
                background: transparent;
            }}
        }}
        '''

    def _render_items_rows(self, items: List[Dict[str, Any]]) -> str:
        """Genera filas HTML de items"""
        rows = []
        for idx, item in enumerate(items, 1):
            nombre = item.get("nombre", item.get("descripcion", "Producto"))
            descripcion = item.get("descripcion", "")
            cantidad = item.get("cantidad", 1)
            precio = item.get("precio", 0)
            item_total = cantidad * precio

            # Descripción solo si es diferente al nombre
            desc_html = ""
            if descripcion and descripcion != nombre:
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

        return "\n".join(rows)

    def _render_html(self, invoice: InvoiceData) -> str:
        """Renderiza el HTML completo de la factura"""

        items_rows = self._render_items_rows(invoice.items)
        styles = self._get_styles()

        # Secciones opcionales del cliente
        cliente_detalles = []
        if invoice.cliente_direccion:
            cliente_detalles.append(f'<p class="client-detail"><span class="icon">📍</span> {invoice.cliente_direccion}</p>')
        if invoice.cliente_ciudad:
            cliente_detalles.append(f'<p class="client-detail"><span class="icon">🏙️</span> {invoice.cliente_ciudad}</p>')
        if invoice.cliente_telefono:
            cliente_detalles.append(f'<p class="client-detail"><span class="icon">📱</span> {invoice.cliente_telefono}</p>')
        if invoice.cliente_email:
            cliente_detalles.append(f'<p class="client-detail"><span class="icon">✉️</span> {invoice.cliente_email}</p>')
        if invoice.cliente_cedula:
            cliente_detalles.append(f'<p class="client-detail"><span class="icon">🪪</span> CC/NIT: {invoice.cliente_cedula}</p>')

        cliente_detalles_html = "\n".join(cliente_detalles)

        # Vencimiento
        vencimiento_html = ""
        if invoice.fecha_vencimiento:
            vencimiento_html = f'<p><strong>Vence:</strong> {invoice.fecha_vencimiento}</p>'

        # Descuento
        descuento_html = ""
        if invoice.descuento > 0:
            descuento_html = f'''
            <tr class="discount">
                <td>Descuento:</td>
                <td>-{self._format_currency(invoice.descuento)}</td>
            </tr>
            '''

        # Notas
        notas_html = ""
        if invoice.notas:
            notas_html = f'''
            <div class="section">
                <div class="section-title">Notas</div>
                <div class="notes">{invoice.notas}</div>
            </div>
            '''

        # Vendedor
        vendedor_cedula_html = f" ({invoice.vendedor_cedula})" if invoice.vendedor_cedula else ""
        vendedor_nombre = invoice.vendedor_nombre or "N/A"

        tax_percent = int(self.tax_rate * 100)

        html = f'''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes">
    <meta name="format-detection" content="telephone=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <title>Factura {invoice.numero_factura}</title>
    <style>
        {styles}
    </style>
</head>
<body>
    <div class="invoice-container">
        <div class="header">
            <div class="logo">
                <h1>JOYERIA</h1>
                <p>Sistema de Facturacion</p>
            </div>
            <div class="invoice-info">
                <h2>FACTURA</h2>
                <p><strong>No.</strong> {invoice.numero_factura}</p>
                <p><strong>Fecha:</strong> {invoice.fecha_emision}</p>
                {vencimiento_html}
            </div>
        </div>

        <div class="section">
            <div class="section-title">Cliente</div>
            <div class="client-info">
                <p><strong>{invoice.cliente_nombre}</strong></p>
                {cliente_detalles_html}
            </div>
        </div>

        <div class="section">
            <div class="section-title">Detalle de Productos</div>
            <div class="items-wrapper">
                <table class="items-table">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Descripcion</th>
                            <th>Cant.</th>
                            <th>P. Unit.</th>
                            <th>Total</th>
                        </tr>
                    </thead>
                    <tbody>
                        {items_rows}
                    </tbody>
                </table>
            </div>
        </div>

        <div class="totals">
            <table class="totals-table">
                <tr>
                    <td>Subtotal:</td>
                    <td>{self._format_currency(invoice.subtotal)}</td>
                </tr>
                {descuento_html}
                <tr>
                    <td>IVA ({tax_percent}%):</td>
                    <td>{self._format_currency(invoice.impuesto)}</td>
                </tr>
                <tr class="total-row">
                    <td>TOTAL:</td>
                    <td>{self._format_currency(invoice.total)}</td>
                </tr>
            </table>
        </div>

        {notas_html}

        <div class="footer">
            <p class="vendedor">Vendedor: {vendedor_nombre}{vendedor_cedula_html}</p>
            <p>Documento generado automaticamente</p>
            <p>Jewelry Invoice Bot</p>
        </div>
    </div>
</body>
</html>'''

        logger.info(f"HTML generado para factura {invoice.numero_factura}")
        return html


# Instancia global (singleton)
html_generator = HTMLGeneratorService()