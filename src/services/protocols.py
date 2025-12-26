"""
Protocolos (Interfaces) de Services

Define interfaces abstractas para los servicios del sistema.
Permite:
- Testing con mocks
- Dependency injection
- Implementaciones alternativas

Python usa typing.Protocol para duck typing estructural.
"""

from typing import Protocol, Dict, Any, List, Optional, runtime_checkable
from src.models.invoice import N8NResponse, N8NPDFResponse


@runtime_checkable
class TextParserProtocol(Protocol):
    """
    Protocolo para servicios de parsing de texto.

    Cualquier clase que implemente parse() con esta firma
    es compatible con este protocolo.
    """

    def parse(self, text: str) -> N8NResponse:
        """
        Parsea texto y extrae items de factura.

        Args:
            text: Texto con descripción de productos

        Returns:
            N8NResponse con items extraídos
        """
        ...


@runtime_checkable
class N8NServiceProtocol(Protocol):
    """
    Protocolo para servicios de integración con n8n.

    Define la interfaz pública del N8NService.
    """

    async def send_text_input(
        self,
        text: str,
        vendedor_cedula: str,
        organization_id: Optional[str] = None
    ) -> N8NResponse:
        """Envía texto para extracción."""
        ...

    async def send_voice_input(
        self,
        audio_path: str,
        vendedor_cedula: str,
        organization_id: Optional[str] = None
    ) -> N8NResponse:
        """Envía audio para transcripción y extracción."""
        ...

    async def send_photo_input(
        self,
        photo_path: str,
        vendedor_cedula: str,
        organization_id: Optional[str] = None
    ) -> N8NResponse:
        """Envía foto para OCR y extracción."""
        ...

    async def generate_pdf(
        self,
        invoice_data: Dict[str, Any],
        organization_id: str
    ) -> N8NPDFResponse:
        """Genera PDF de factura."""
        ...


@runtime_checkable
class HTMLGeneratorProtocol(Protocol):
    """
    Protocolo para servicios de generación de HTML.
    """

    def generate(self, data: Dict[str, Any]) -> str:
        """
        Genera HTML de factura desde diccionario.

        Args:
            data: Datos de la factura

        Returns:
            String HTML completo
        """
        ...


@runtime_checkable
class InvoiceFormatterProtocol(Protocol):
    """
    Protocolo para servicios de formateo de facturas.
    """

    @staticmethod
    def format_items_summary(items: List[Dict]) -> str:
        """Formatea lista de items para mostrar."""
        ...

    @staticmethod
    def format_cliente_summary(cliente: Dict) -> str:
        """Formatea datos del cliente."""
        ...

    @staticmethod
    def format_invoice_preview(
        items: List[Dict],
        cliente: Dict = None,
        subtotal: float = 0,
        impuesto: float = 0,
        total: float = 0
    ) -> str:
        """Formatea vista previa completa."""
        ...


@runtime_checkable
class ItemEditorProtocol(Protocol):
    """
    Protocolo para servicios de edición de items.
    """

    @staticmethod
    def update_item_field(
        items: List[Dict],
        item_index: int,
        field: str,
        value: Any
    ) -> Any:
        """Actualiza un campo de un item."""
        ...

    @staticmethod
    def add_item(
        items: List[Dict],
        nombre: str,
        cantidad: int,
        precio: float,
        descripcion: str = None,
        max_items: int = 6
    ) -> Any:
        """Agrega un nuevo item."""
        ...

    @staticmethod
    def delete_item(items: List[Dict], item_index: int) -> Any:
        """Elimina un item."""
        ...

    @staticmethod
    def calculate_totals(items: List[Dict]) -> Dict[str, float]:
        """Calcula totales."""
        ...