"""
Factory para MetricEvent

Proporciona factory para crear eventos de métricas de negocio.
"""

import factory
from factory import Faker, LazyAttribute, Sequence
import uuid
from datetime import datetime, timedelta
import random

from src.database.models import MetricEvent
from tests.factories.base import BaseFactory


class MetricEventFactory(BaseFactory):
    """
    Factory para crear eventos de métricas.

    Ejemplos:
        # Evento básico
        event = MetricEventFactory()

        # Evento de factura creada
        event = MetricEventFactory(event_type="invoice.created", value=500000)

        # Evento fallido
        event = MetricEventFactory(success=False)

        # Múltiples eventos
        events = MetricEventFactory.create_batch(10)
    """

    class Meta:
        model = MetricEvent

    id = Sequence(lambda n: n + 1)

    # Tipo de evento
    event_type = "invoice.created"

    # Multi-tenancy
    organization_id = LazyAttribute(lambda _: str(uuid.uuid4()))

    # Usuario
    user_id = Sequence(lambda n: n + 1)

    # Valor numérico
    value = LazyAttribute(lambda _: float(random.randint(100000, 5000000)))

    # Resultado
    success = True

    # Duración
    duration_ms = LazyAttribute(lambda _: float(random.randint(10, 500)))

    # Metadata
    event_metadata = factory.LazyFunction(lambda: {})

    # Timestamp
    created_at = LazyAttribute(lambda _: datetime.utcnow())

    class Params:
        """
        Variantes comunes de eventos de métricas.
        """

        # Evento de creación de factura
        invoice_created = factory.Trait(
            event_type="invoice.created",
            event_metadata=factory.LazyFunction(lambda: {
                "items_count": random.randint(1, 5),
                "input_type": random.choice(["TEXTO", "VOZ", "FOTO"]),
            })
        )

        # Evento de factura pagada
        invoice_paid = factory.Trait(
            event_type="invoice.paid",
            event_metadata=factory.LazyFunction(lambda: {
                "payment_method": random.choice(["cash", "transfer", "card"]),
            })
        )

        # Evento de extracción IA
        ai_extraction = factory.Trait(
            event_type="ai.extraction",
            value=LazyAttribute(lambda _: float(random.randint(1, 10))),  # Items extraídos
            event_metadata=factory.LazyFunction(lambda: {
                "confidence": round(random.uniform(0.7, 1.0), 2),
                "model": "gpt-4",
            })
        )

        # Evento de interacción con bot
        bot_interaction = factory.Trait(
            event_type="bot.message",
            value=1.0,
            event_metadata=factory.LazyFunction(lambda: {
                "command": random.choice(["/start", "/help", "/nueva", "/lista"]),
            })
        )

        # Evento de API
        api_request = factory.Trait(
            event_type="api.request",
            value=1.0,
            event_metadata=factory.LazyFunction(lambda: {
                "endpoint": random.choice(["/invoices", "/users", "/metrics"]),
                "method": random.choice(["GET", "POST", "PUT"]),
            })
        )

        # Evento fallido
        failed = factory.Trait(
            success=False,
            event_metadata=factory.LazyFunction(lambda: {
                "error": "ValidationError",
                "message": "Invalid input data",
            })
        )

        # Evento lento (para alertas de performance)
        slow = factory.Trait(
            duration_ms=LazyAttribute(lambda _: float(random.randint(1000, 5000)))
        )

    @classmethod
    def create_time_series(
        cls,
        organization_id: str,
        event_type: str = "invoice.created",
        days: int = 30,
        events_per_day: int = 10,
        **kwargs
    ):
        """
        Crea una serie temporal de eventos para testing de gráficos.

        Args:
            organization_id: ID de la organización
            event_type: Tipo de evento
            days: Número de días hacia atrás
            events_per_day: Eventos promedio por día
            **kwargs: Atributos adicionales

        Returns:
            Lista de eventos creados
        """
        events = []
        now = datetime.utcnow()

        for day in range(days):
            date = now - timedelta(days=day)
            # Variación en número de eventos por día
            num_events = events_per_day + random.randint(-3, 3)
            num_events = max(1, num_events)

            for _ in range(num_events):
                # Hora aleatoria del día
                hour = random.randint(8, 22)
                minute = random.randint(0, 59)
                event_time = date.replace(hour=hour, minute=minute)

                event = cls.create(
                    organization_id=organization_id,
                    event_type=event_type,
                    created_at=event_time,
                    **kwargs
                )
                events.append(event)

        return events

    @classmethod
    def create_for_dashboard(cls, organization_id: str, **kwargs):
        """
        Crea un conjunto de eventos típicos para un dashboard de demo.

        Args:
            organization_id: ID de la organización
            **kwargs: Atributos adicionales

        Returns:
            Dict con eventos por tipo
        """
        return {
            "invoices": cls.create_batch(
                50,
                organization_id=organization_id,
                event_type="invoice.created",
                **kwargs
            ),
            "payments": cls.create_batch(
                30,
                organization_id=organization_id,
                event_type="invoice.paid",
                **kwargs
            ),
            "ai_extractions": cls.create_batch(
                40,
                organization_id=organization_id,
                event_type="ai.extraction",
                **kwargs
            ),
            "bot_interactions": cls.create_batch(
                100,
                organization_id=organization_id,
                event_type="bot.message",
                **kwargs
            ),
        }
