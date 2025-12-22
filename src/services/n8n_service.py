"""
Servicio de Integración con n8n

Maneja la comunicación con webhooks de n8n para:
- Transcripción de audio (Whisper)
- OCR de imágenes (Vision AI)
- Extracción de datos con IA
"""

import httpx
import base64
from pathlib import Path
from typing import Optional
from datetime import datetime

from config.settings import settings
from src.utils.logger import get_logger
from src.models.invoice import N8NResponse

logger = get_logger(__name__)


class N8NService:
    """Servicio para comunicación con n8n webhooks"""

    def __init__(self):
        self.webhook_url = settings.N8N_WEBHOOK_URL
        self.timeout = settings.N8N_TIMEOUT_SECONDS

    async def send_text_input(
        self,
        text: str,
        vendedor_cedula: str
    ) -> N8NResponse:
        """
        Envía texto a n8n para extracción de items.

        Args:
            text: Texto con descripción de productos
            vendedor_cedula: Cédula del vendedor

        Returns:
            Respuesta de n8n con items extraídos
        """
        payload = {
            "type": "text",
            "content": text,
            "vendedor_cedula": vendedor_cedula,
            "timestamp": datetime.utcnow().isoformat()
        }
        return await self._send_to_webhook(payload)

    async def send_voice_input(
        self,
        audio_path: str,
        vendedor_cedula: str
    ) -> N8NResponse:
        """
        Envía audio a n8n para transcripción con Whisper.

        Args:
            audio_path: Ruta al archivo de audio
            vendedor_cedula: Cédula del vendedor

        Returns:
            Respuesta de n8n con transcripción e items
        """
        try:
            # Leer archivo y convertir a base64
            audio_data = Path(audio_path).read_bytes()
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')

            payload = {
                "type": "voice",
                "content": audio_base64,
                "content_type": "audio/ogg",
                "vendedor_cedula": vendedor_cedula,
                "timestamp": datetime.utcnow().isoformat()
            }
            return await self._send_to_webhook(payload)

        except FileNotFoundError:
            logger.error(f"Archivo de audio no encontrado: {audio_path}")
            return N8NResponse(
                success=False,
                error="Archivo de audio no encontrado"
            )

    async def send_photo_input(
        self,
        photo_path: str,
        vendedor_cedula: str
    ) -> N8NResponse:
        """
        Envía foto a n8n para OCR/Vision AI.

        Args:
            photo_path: Ruta a la imagen
            vendedor_cedula: Cédula del vendedor

        Returns:
            Respuesta de n8n con texto extraído e items
        """
        try:
            # Leer archivo y convertir a base64
            photo_data = Path(photo_path).read_bytes()
            photo_base64 = base64.b64encode(photo_data).decode('utf-8')

            payload = {
                "type": "photo",
                "content": photo_base64,
                "content_type": "image/jpeg",
                "vendedor_cedula": vendedor_cedula,
                "timestamp": datetime.utcnow().isoformat()
            }
            return await self._send_to_webhook(payload)

        except FileNotFoundError:
            logger.error(f"Archivo de imagen no encontrado: {photo_path}")
            return N8NResponse(
                success=False,
                error="Archivo de imagen no encontrado"
            )

    async def _send_to_webhook(self, payload: dict) -> N8NResponse:
        """
        Envía payload al webhook de n8n.

        Args:
            payload: Datos a enviar

        Returns:
            Respuesta procesada de n8n
        """
        if not self.webhook_url:
            logger.warning("N8N_WEBHOOK_URL no está configurado")
            return N8NResponse(
                success=False,
                error="Webhook URL no configurado. Configure N8N_WEBHOOK_URL en .env"
            )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info(f"Enviando a n8n: type={payload.get('type')}")

                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )

                if response.status_code == 200:
                    data = response.json()

                    # Validar estructura de respuesta
                    if isinstance(data, dict):
                        items = data.get('items', [])
                        logger.info(f"Respuesta n8n exitosa: {len(items)} items")

                        return N8NResponse(
                            success=data.get('success', True),
                            items=items,
                            transcripcion=data.get('transcripcion'),
                            confianza=data.get('confianza', 0.0),
                            error=data.get('error')
                        )
                    else:
                        logger.warning(f"Respuesta n8n inesperada: {type(data)}")
                        return N8NResponse(
                            success=False,
                            error="Respuesta de n8n no válida"
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
            logger.error(f"No se pudo conectar a n8n: {self.webhook_url}")
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


# Instancia global del servicio
n8n_service = N8NService()