"""
Servicio de Integración con n8n

Maneja la comunicación con webhooks de n8n para:
- Extracción de datos con IA (texto/audio/foto)
- Generación de PDF de facturas

Arquitectura Híbrida:
- Bot Python maneja: autenticación, menú, edición conversacional, datos cliente
- n8n maneja: procesamiento IA (Whisper, Vision, GPT), generación PDF

Flujo:
1. Bot → n8n/extract: Envía input (texto/audio/foto)
2. n8n → Bot: Retorna items extraídos
3. Bot: Maneja edición y datos cliente
4. Bot → n8n/pdf: Envía datos finales
5. n8n → Bot: Retorna PDF generado

Características de resiliencia:
- Retry automático con backoff exponencial
- Circuit breaker para evitar cascadas de fallos
- Timeouts configurables
"""

import httpx
import base64
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

from config.settings import settings
from src.utils.logger import get_logger
from src.models.invoice import N8NResponse, N8NPDFResponse
from src.services.http_client import ResilientHTTPClient, CircuitBreakerOpen

logger = get_logger(__name__)


class N8NInputType(str, Enum):
    """Tipos de input soportados por n8n"""
    TEXT = "text"
    VOICE = "voice"
    PHOTO = "photo"


class N8NService:
    """
    Servicio para comunicación con n8n webhooks.

    Implementa el patrón de arquitectura híbrida donde:
    - El bot maneja la UX/UI y conversación
    - n8n maneja el procesamiento pesado (IA, PDF)

    Características:
    - Retry automático con backoff exponencial
    - Circuit breaker para evitar cascadas de fallos
    - Timeouts configurables por operación
    """

    def __init__(self):
        self.extract_webhook_url = settings.N8N_WEBHOOK_URL
        self.pdf_webhook_url = settings.N8N_PDF_WEBHOOK_URL
        self.timeout = settings.N8N_TIMEOUT_SECONDS

        # Cliente HTTP resiliente con retry y circuit breaker
        self.http_client = ResilientHTTPClient(
            base_timeout=self.timeout,
            max_retries=3,
            circuit_breaker_threshold=5,
            circuit_breaker_recovery=60
        )

    # =========================================================================
    # MÉTODOS DE EXTRACCIÓN (Webhook 1: /extract)
    # =========================================================================

    async def send_text_input(
        self,
        text: str,
        vendedor_cedula: str,
        organization_id: Optional[str] = None
    ) -> N8NResponse:
        """
        Envía texto a n8n para extracción de items con IA.

        Args:
            text: Texto con descripción de productos
            vendedor_cedula: Cédula del vendedor
            organization_id: ID de organización (multi-tenant)

        Returns:
            N8NResponse con items extraídos y totales
        """
        payload = self._build_extract_payload(
            input_type=N8NInputType.TEXT,
            content=text,
            vendedor_cedula=vendedor_cedula,
            organization_id=organization_id
        )
        return await self._send_extract_request(payload)

    async def send_voice_input(
        self,
        audio_path: str,
        vendedor_cedula: str,
        organization_id: Optional[str] = None
    ) -> N8NResponse:
        """
        Envía audio a n8n para transcripción (Whisper) y extracción.

        Args:
            audio_path: Ruta al archivo de audio (.ogg, .mp3, etc)
            vendedor_cedula: Cédula del vendedor
            organization_id: ID de organización (multi-tenant)

        Returns:
            N8NResponse con transcripción, items extraídos y totales
        """
        try:
            audio_data = Path(audio_path).read_bytes()
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')

            payload = self._build_extract_payload(
                input_type=N8NInputType.VOICE,
                content=audio_base64,
                vendedor_cedula=vendedor_cedula,
                organization_id=organization_id,
                content_type="audio/ogg"
            )
            return await self._send_extract_request(payload)

        except FileNotFoundError:
            logger.error(f"Archivo de audio no encontrado: {audio_path}")
            return N8NResponse(
                success=False,
                error="Archivo de audio no encontrado"
            )

    async def send_photo_input(
        self,
        photo_path: str,
        vendedor_cedula: str,
        organization_id: Optional[str] = None
    ) -> N8NResponse:
        """
        Envía foto a n8n para OCR/Vision AI y extracción.

        Args:
            photo_path: Ruta a la imagen (.jpg, .png)
            vendedor_cedula: Cédula del vendedor
            organization_id: ID de organización (multi-tenant)

        Returns:
            N8NResponse con texto extraído, items y totales
        """
        try:
            photo_data = Path(photo_path).read_bytes()
            photo_base64 = base64.b64encode(photo_data).decode('utf-8')

            payload = self._build_extract_payload(
                input_type=N8NInputType.PHOTO,
                content=photo_base64,
                vendedor_cedula=vendedor_cedula,
                organization_id=organization_id,
                content_type="image/jpeg"
            )
            return await self._send_extract_request(payload)

        except FileNotFoundError:
            logger.error(f"Archivo de imagen no encontrado: {photo_path}")
            return N8NResponse(
                success=False,
                error="Archivo de imagen no encontrado"
            )

    # =========================================================================
    # MÉTODOS DE GENERACIÓN PDF (Webhook 2: /pdf)
    # =========================================================================

    async def generate_pdf(
        self,
        invoice_data: Dict[str, Any],
        organization_id: str
    ) -> N8NPDFResponse:
        """
        Envía datos de factura a n8n para generar PDF.

        El bot genera HTML localmente para el usuario.
        n8n genera PDF con formato texto para archivo formal.

        Args:
            invoice_data: Diccionario con datos de la factura
            organization_id: ID de organización

        Returns:
            N8NPDFResponse con URL del PDF
        """
        numero_factura = invoice_data.get("numero_factura", "BORRADOR")
        payload = {
            "tipo_evento": "generar_pdf",
            "numero_factura": numero_factura,
            "fecha_emision": invoice_data.get("fecha_emision"),
            "fecha_vencimiento": invoice_data.get("fecha_vencimiento"),
            "cliente_nombre": invoice_data.get("cliente_nombre"),
            "cliente_direccion": invoice_data.get("cliente_direccion"),
            "cliente_ciudad": invoice_data.get("cliente_ciudad"),
            "cliente_email": invoice_data.get("cliente_email"),
            "cliente_telefono": invoice_data.get("cliente_telefono"),
            "cliente_cedula": invoice_data.get("cliente_cedula"),
            "items": invoice_data.get("items", []),
            "subtotal": invoice_data.get("subtotal", 0),
            "descuento": invoice_data.get("descuento", 0),
            "impuesto": invoice_data.get("impuesto", 0),
            "total": invoice_data.get("total", 0),
            "vendedor_nombre": invoice_data.get("vendedor_nombre"),
            "vendedor_cedula": invoice_data.get("vendedor_cedula"),
            "notas": invoice_data.get("notas"),
            "organization_id": organization_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        return await self._send_pdf_request(payload)

    async def send_pdf_to_telegram(
        self,
        chat_id: int,
        pdf_base64: str,
        filename: str,
        caption: Optional[str] = None
    ) -> bool:
        """
        Envía PDF generado a Telegram via n8n.

        Args:
            chat_id: ID del chat de Telegram
            pdf_base64: PDF en formato base64
            filename: Nombre del archivo
            caption: Texto opcional del mensaje

        Returns:
            True si se envió correctamente
        """
        payload = {
            "tipo_evento": "enviar_pdf",
            "chat_id": chat_id,
            "pdf_base64": pdf_base64,
            "filename": filename,
            "caption": caption,
            "timestamp": datetime.utcnow().isoformat()
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.pdf_webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Error enviando PDF a Telegram: {e}")
            return False

    # =========================================================================
    # MÉTODOS PRIVADOS
    # =========================================================================

    def _build_extract_payload(
        self,
        input_type: N8NInputType,
        content: str,
        vendedor_cedula: str,
        organization_id: Optional[str] = None,
        content_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Construye el payload para el webhook de extracción."""
        payload = {
            "type": input_type.value,
            "content": content,
            "vendedor_cedula": vendedor_cedula,
            "timestamp": datetime.utcnow().isoformat()
        }

        if organization_id:
            payload["organization_id"] = organization_id

        if content_type:
            payload["content_type"] = content_type

        return payload

    async def _send_extract_request(self, payload: Dict[str, Any]) -> N8NResponse:
        """
        Envía request al webhook de extracción.

        Args:
            payload: Datos a enviar

        Returns:
            N8NResponse con datos extraídos
        """
        if not self.extract_webhook_url:
            logger.warning("N8N_WEBHOOK_URL no está configurado")
            return N8NResponse(
                success=False,
                error="Webhook de extracción no configurado. Configure N8N_WEBHOOK_URL en .env"
            )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info(f"Enviando a n8n/extract: type={payload.get('type')}")

                response = await client.post(
                    self.extract_webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )

                if response.status_code == 200:
                    response_text = response.text
                    if not response_text or response_text.strip() == '':
                        logger.error("n8n retornó respuesta vacía - verificar credenciales OpenAI en n8n")
                        return N8NResponse(
                            success=False,
                            error="n8n retornó respuesta vacía. Verificar que el workflow esté activo y OpenAI configurado."
                        )
                    try:
                        data = response.json()
                        return self._parse_extract_response(data)
                    except Exception as json_err:
                        logger.error(f"Error parseando JSON de n8n: {json_err}. Respuesta: {response_text[:200]}")
                        return N8NResponse(
                            success=False,
                            error=f"Error parseando respuesta de n8n: {str(json_err)[:100]}"
                        )
                else:
                    logger.error(f"Error n8n HTTP {response.status_code}: {response.text}")
                    return N8NResponse(
                        success=False,
                        error=f"Error HTTP {response.status_code}"
                    )

        except httpx.TimeoutException:
            logger.error("Timeout esperando respuesta de n8n")
            return N8NResponse(
                success=False,
                error="Timeout - el procesamiento tomó demasiado tiempo"
            )
        except httpx.ConnectError:
            logger.error(f"No se pudo conectar a n8n: {self.extract_webhook_url}")
            return N8NResponse(
                success=False,
                error="No se pudo conectar a n8n. Verifica que esté corriendo."
            )
        except Exception as e:
            logger.error(f"Error comunicando con n8n: {e}")
            return N8NResponse(
                success=False,
                error=str(e)
            )

    def _parse_extract_response(self, data: Any) -> N8NResponse:
        """
        Parsea la respuesta del webhook de extracción.

        Args:
            data: Respuesta JSON de n8n

        Returns:
            N8NResponse estructurado
        """
        if not isinstance(data, dict):
            logger.warning(f"Respuesta n8n inesperada: {type(data)}")
            return N8NResponse(
                success=False,
                error="Respuesta de n8n no válida"
            )

        items = data.get('items', [])
        logger.info(f"Respuesta n8n exitosa: {len(items)} items")

        return N8NResponse(
            success=data.get('success', len(items) > 0),
            items=items,
            cliente=data.get('cliente'),
            totales=data.get('totales'),
            factura=data.get('factura'),
            transcripcion=data.get('transcripcion'),
            input_type=data.get('input_type'),
            notas=data.get('notas'),
            confianza=data.get('confianza', 0.0),
            error=data.get('error')
        )

    async def _send_pdf_request(self, payload: Dict[str, Any]) -> N8NPDFResponse:
        """
        Envía request al webhook de generación de PDF.

        Args:
            payload: Datos de la factura

        Returns:
            N8NPDFResponse con PDF generado
        """
        if not self.pdf_webhook_url:
            logger.warning("N8N_PDF_WEBHOOK_URL no está configurado")
            return N8NPDFResponse(
                success=False,
                error="Webhook de PDF no configurado. Configure N8N_PDF_WEBHOOK_URL en .env"
            )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info(f"Enviando a n8n/pdf: factura={payload.get('numero_factura')}")

                response = await client.post(
                    self.pdf_webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )

                if response.status_code == 200:
                    data = response.json()
                    return N8NPDFResponse(
                        success=data.get('success', True),
                        pdf_url=data.get('pdf_url'),
                        pdf_view_url=data.get('pdf_view_url'),
                        pdf_file_id=data.get('pdf_file_id'),
                        pdf_base64=data.get('pdf_base64'),
                        html=data.get('html'),
                        filename=data.get('filename'),
                        numero_factura=data.get('numero_factura'),
                        error=data.get('error')
                    )
                else:
                    logger.error(f"Error n8n PDF HTTP {response.status_code}")
                    return N8NPDFResponse(
                        success=False,
                        error=f"Error HTTP {response.status_code}"
                    )

        except httpx.TimeoutException:
            logger.error("Timeout generando PDF en n8n")
            return N8NPDFResponse(
                success=False,
                error="Timeout generando PDF"
            )
        except httpx.ConnectError:
            logger.error(f"No se pudo conectar a n8n PDF: {self.pdf_webhook_url}")
            return N8NPDFResponse(
                success=False,
                error="No se pudo conectar a n8n para generar PDF"
            )
        except Exception as e:
            logger.error(f"Error generando PDF: {e}")
            return N8NPDFResponse(
                success=False,
                error=str(e)
            )


    # =========================================================================
    # MÉTODOS DE DIAGNÓSTICO
    # =========================================================================

    def get_health_status(self) -> Dict[str, Any]:
        """
        Retorna estado de salud del servicio.

        Returns:
            Dict con estado del circuit breaker y configuración
        """
        return {
            "extract_webhook_configured": bool(self.extract_webhook_url),
            "pdf_webhook_configured": bool(self.pdf_webhook_url),
            "timeout_seconds": self.timeout,
            "circuit_breaker": self.http_client.get_circuit_status()
        }

    async def health_check(self) -> Dict[str, Any]:
        """
        Verifica conectividad con n8n.

        Returns:
            Dict con resultado del health check
        """
        result = {
            "extract_webhook": {"status": "unknown"},
            "pdf_webhook": {"status": "unknown"}
        }

        # Verificar extract webhook
        if self.extract_webhook_url:
            try:
                response = await self.http_client.get(
                    self.extract_webhook_url.replace("/webhook/", "/webhook-test/"),
                    timeout=5.0
                )
                result["extract_webhook"] = {
                    "status": "ok" if response.status_code < 400 else "error",
                    "status_code": response.status_code
                }
            except CircuitBreakerOpen:
                result["extract_webhook"] = {"status": "circuit_open"}
            except Exception as e:
                result["extract_webhook"] = {"status": "error", "error": str(e)}

        # Verificar PDF webhook
        if self.pdf_webhook_url:
            try:
                response = await self.http_client.get(
                    self.pdf_webhook_url.replace("/webhook/", "/webhook-test/"),
                    timeout=5.0
                )
                result["pdf_webhook"] = {
                    "status": "ok" if response.status_code < 400 else "error",
                    "status_code": response.status_code
                }
            except CircuitBreakerOpen:
                result["pdf_webhook"] = {"status": "circuit_open"}
            except Exception as e:
                result["pdf_webhook"] = {"status": "error", "error": str(e)}

        return result


# Instancia global del servicio (singleton)
n8n_service = N8NService()