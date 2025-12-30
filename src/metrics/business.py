"""
Business Metrics Service

Servicio de métricas de negocio para análisis SaaS.
Proporciona insights sobre organizaciones, productos y uso.

Fuentes de datos:
- Memoria: Para métricas en tiempo real (últimas 24h)
- Base de datos: Para análisis histórico (configurable)
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

from src.utils.logger import get_logger
from src.metrics.collectors import (
    MetricsCollector,
    get_metrics_collector,
    EventType,
    MetricCounter,
    is_db_persistence_enabled,
)
from src.metrics.aggregators import (
    MetricsAggregator,
    get_metrics_aggregator,
    AggregationPeriod,
)

logger = get_logger(__name__)


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class InvoiceMetrics:
    """Métricas de facturación."""

    total_created: int = 0
    total_paid: int = 0
    total_pending: int = 0
    total_cancelled: int = 0

    total_amount: float = 0.0
    paid_amount: float = 0.0
    pending_amount: float = 0.0

    avg_invoice_amount: float = 0.0
    avg_time_to_payment_hours: Optional[float] = None

    conversion_rate: float = 0.0  # borrador -> pagada

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_created": self.total_created,
            "total_paid": self.total_paid,
            "total_pending": self.total_pending,
            "total_cancelled": self.total_cancelled,
            "total_amount": round(self.total_amount, 2),
            "paid_amount": round(self.paid_amount, 2),
            "pending_amount": round(self.pending_amount, 2),
            "avg_invoice_amount": round(self.avg_invoice_amount, 2),
            "avg_time_to_payment_hours": (
                round(self.avg_time_to_payment_hours, 2)
                if self.avg_time_to_payment_hours else None
            ),
            "conversion_rate": round(self.conversion_rate, 4),
        }


@dataclass
class BotMetrics:
    """Métricas de uso del bot."""

    total_messages: int = 0
    total_commands: int = 0
    total_photos: int = 0
    total_voice: int = 0

    # Por tipo de comando
    commands_usage: Dict[str, int] = field(default_factory=dict)

    # IA
    ai_extractions_total: int = 0
    ai_extractions_success: int = 0
    ai_success_rate: float = 0.0

    # Tiempos
    avg_response_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_messages": self.total_messages,
            "total_commands": self.total_commands,
            "total_photos": self.total_photos,
            "total_voice": self.total_voice,
            "commands_usage": self.commands_usage,
            "ai_extractions_total": self.ai_extractions_total,
            "ai_extractions_success": self.ai_extractions_success,
            "ai_success_rate": round(self.ai_success_rate, 4),
            "avg_response_time_ms": round(self.avg_response_time_ms, 2),
        }


@dataclass
class OrganizationMetrics:
    """Métricas completas de una organización."""

    organization_id: str
    period_start: datetime
    period_end: datetime

    # Usuarios
    active_users: int = 0
    total_users: int = 0

    # Facturación
    invoices: InvoiceMetrics = field(default_factory=InvoiceMetrics)

    # Bot
    bot: BotMetrics = field(default_factory=BotMetrics)

    # Engagement
    days_active: int = 0
    last_activity: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "organization_id": self.organization_id,
            "period": {
                "start": self.period_start.isoformat(),
                "end": self.period_end.isoformat(),
            },
            "users": {
                "active": self.active_users,
                "total": self.total_users,
            },
            "invoices": self.invoices.to_dict(),
            "bot": self.bot.to_dict(),
            "engagement": {
                "days_active": self.days_active,
                "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            },
        }


@dataclass
class CustomerStats:
    """Estadísticas de un cliente específico."""

    customer_cedula: str
    customer_name: str = ""
    total_purchases: int = 0
    total_spent: float = 0.0
    avg_purchase_amount: float = 0.0
    first_purchase: Optional[datetime] = None
    last_purchase: Optional[datetime] = None
    favorite_material: Optional[str] = None
    favorite_category: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "customer_cedula": self.customer_cedula,
            "customer_name": self.customer_name,
            "total_purchases": self.total_purchases,
            "total_spent": round(self.total_spent, 2),
            "avg_purchase_amount": round(self.avg_purchase_amount, 2),
            "first_purchase": self.first_purchase.isoformat() if self.first_purchase else None,
            "last_purchase": self.last_purchase.isoformat() if self.last_purchase else None,
            "favorite_material": self.favorite_material,
            "favorite_category": self.favorite_category,
        }


@dataclass
class SellerPerformance:
    """Rendimiento de un vendedor."""

    user_id: int
    user_name: str = ""
    total_sales: int = 0
    total_amount: float = 0.0
    avg_sale_amount: float = 0.0
    items_sold: int = 0
    new_customers: int = 0
    returning_customers: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "total_sales": self.total_sales,
            "total_amount": round(self.total_amount, 2),
            "avg_sale_amount": round(self.avg_sale_amount, 2),
            "items_sold": self.items_sold,
            "new_customers": self.new_customers,
            "returning_customers": self.returning_customers,
        }


@dataclass
class TopProduct:
    """Producto más vendido."""

    descripcion: str
    cantidad_vendida: int = 0
    total_ingresos: float = 0.0
    material: Optional[str] = None
    tipo_prenda: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "descripcion": self.descripcion,
            "cantidad_vendida": self.cantidad_vendida,
            "total_ingresos": round(self.total_ingresos, 2),
            "material": self.material,
            "tipo_prenda": self.tipo_prenda,
        }


@dataclass
class JewelryMetrics:
    """Métricas específicas de joyería."""

    period_start: datetime
    period_end: datetime

    # Clientes
    new_customers: int = 0
    returning_customers: int = 0
    total_customers_served: int = 0

    # Productos
    total_items_sold: int = 0
    top_products: List["TopProduct"] = field(default_factory=list)

    # Por material
    sales_by_material: Dict[str, float] = field(default_factory=dict)
    quantity_by_material: Dict[str, int] = field(default_factory=dict)

    # Por categoría
    sales_by_category: Dict[str, float] = field(default_factory=dict)
    quantity_by_category: Dict[str, int] = field(default_factory=dict)

    # Vendedores
    seller_performance: List["SellerPerformance"] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "period": {
                "start": self.period_start.isoformat(),
                "end": self.period_end.isoformat(),
            },
            "customers": {
                "new": self.new_customers,
                "returning": self.returning_customers,
                "total_served": self.total_customers_served,
            },
            "products": {
                "total_items_sold": self.total_items_sold,
                "top_products": [p.to_dict() for p in self.top_products],
            },
            "by_material": {
                "sales": self.sales_by_material,
                "quantity": self.quantity_by_material,
            },
            "by_category": {
                "sales": self.sales_by_category,
                "quantity": self.quantity_by_category,
            },
            "sellers": [s.to_dict() for s in self.seller_performance],
        }


@dataclass
class ProductMetrics:
    """Métricas globales del producto SaaS."""

    period_start: datetime
    period_end: datetime

    # Organizaciones
    total_organizations: int = 0
    active_organizations: int = 0
    new_organizations: int = 0
    churned_organizations: int = 0

    # Por plan
    organizations_by_plan: Dict[str, int] = field(default_factory=dict)

    # Ingresos (estimado por uso)
    total_invoices_processed: int = 0
    total_invoice_amount: float = 0.0

    # Features
    feature_usage: Dict[str, int] = field(default_factory=dict)

    # Salud
    avg_org_health_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "period": {
                "start": self.period_start.isoformat(),
                "end": self.period_end.isoformat(),
            },
            "organizations": {
                "total": self.total_organizations,
                "active": self.active_organizations,
                "new": self.new_organizations,
                "churned": self.churned_organizations,
                "by_plan": self.organizations_by_plan,
            },
            "invoices": {
                "total_processed": self.total_invoices_processed,
                "total_amount": round(self.total_invoice_amount, 2),
            },
            "features": self.feature_usage,
            "health": {
                "avg_org_score": round(self.avg_org_health_score, 2),
            },
        }


@dataclass
class UsageMetrics:
    """Métricas de uso del sistema."""

    period_start: datetime
    period_end: datetime

    # API
    total_api_requests: int = 0
    api_errors: int = 0
    api_error_rate: float = 0.0
    avg_api_latency_ms: float = 0.0

    # Bot
    total_bot_interactions: int = 0
    bot_errors: int = 0

    # Por hora del día
    usage_by_hour: Dict[int, int] = field(default_factory=dict)

    # Por día de la semana
    usage_by_day: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "period": {
                "start": self.period_start.isoformat(),
                "end": self.period_end.isoformat(),
            },
            "api": {
                "total_requests": self.total_api_requests,
                "errors": self.api_errors,
                "error_rate": round(self.api_error_rate, 4),
                "avg_latency_ms": round(self.avg_api_latency_ms, 2),
            },
            "bot": {
                "total_interactions": self.total_bot_interactions,
                "errors": self.bot_errors,
            },
            "patterns": {
                "by_hour": self.usage_by_hour,
                "by_day": self.usage_by_day,
            },
        }


# ============================================================================
# BUSINESS METRICS SERVICE
# ============================================================================

class DataSource(str, Enum):
    """Fuente de datos para métricas."""
    MEMORY = "memory"       # Datos en memoria (tiempo real, últimas 24h)
    DATABASE = "database"   # Datos históricos en BD
    AUTO = "auto"           # Automático según el período


class BusinessMetricsService:
    """
    Servicio de métricas de negocio.

    Proporciona análisis de alto nivel sobre:
    - Rendimiento por organización (tenant)
    - Salud del producto SaaS
    - Patrones de uso

    Soporta dos fuentes de datos:
    - Memoria: Para métricas en tiempo real
    - Base de datos: Para análisis histórico
    """

    def __init__(
        self,
        collector: Optional[MetricsCollector] = None,
        aggregator: Optional[MetricsAggregator] = None,
    ):
        self._collector = collector or get_metrics_collector()
        self._aggregator = aggregator or get_metrics_aggregator()
        logger.info("BusinessMetricsService inicializado")

    def _should_use_database(
        self,
        since: Optional[datetime],
        source: DataSource = DataSource.AUTO,
    ) -> bool:
        """
        Determina si debe usar la base de datos.

        Args:
            since: Inicio del período
            source: Fuente preferida

        Returns:
            True si debe usar BD
        """
        if source == DataSource.DATABASE:
            return is_db_persistence_enabled()
        if source == DataSource.MEMORY:
            return False

        # AUTO: Usar BD si el período es mayor a 24h
        if since is None:
            return False

        hours_ago = (datetime.utcnow() - since).total_seconds() / 3600
        return hours_ago > 24 and is_db_persistence_enabled()

    async def get_organization_metrics(
        self,
        organization_id: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        source: DataSource = DataSource.AUTO,
    ) -> OrganizationMetrics:
        """
        Obtiene métricas completas de una organización.

        Args:
            organization_id: ID de la organización
            since: Inicio del período (default: últimos 30 días)
            until: Fin del período (default: ahora)
            source: Fuente de datos (AUTO, MEMORY, DATABASE)

        Returns:
            Métricas de la organización
        """
        if until is None:
            until = datetime.utcnow()
        if since is None:
            since = until - timedelta(days=30)

        metrics = OrganizationMetrics(
            organization_id=organization_id,
            period_start=since,
            period_end=until,
        )

        use_db = self._should_use_database(since, source)

        if use_db:
            # Obtener desde base de datos
            db_summary = self._collector.get_organization_summary_from_db(
                organization_id=organization_id,
                since=since,
            )

            if db_summary:
                # Procesar datos de BD
                invoices_data = db_summary.get("invoices", {})
                metrics.invoices.total_created = invoices_data.get("created", 0)
                metrics.invoices.total_amount = invoices_data.get("total_amount", 0.0)
                metrics.invoices.total_paid = invoices_data.get("paid", 0)
                metrics.invoices.paid_amount = invoices_data.get("paid_amount", 0.0)

                if metrics.invoices.total_created > 0:
                    metrics.invoices.avg_invoice_amount = (
                        metrics.invoices.total_amount / metrics.invoices.total_created
                    )
                    metrics.invoices.conversion_rate = (
                        metrics.invoices.total_paid / metrics.invoices.total_created
                    )

                bot_data = db_summary.get("bot", {})
                metrics.bot.total_photos = bot_data.get("photos", 0)
                metrics.bot.total_voice = bot_data.get("voice", 0)
                metrics.bot.ai_success_rate = bot_data.get("photos_success_rate", 0.0)

                ai_data = db_summary.get("ai", {})
                metrics.bot.ai_extractions_total = ai_data.get("extractions", 0)
                metrics.bot.ai_success_rate = ai_data.get("success_rate", 0.0)
                metrics.bot.avg_response_time_ms = ai_data.get("avg_duration_ms", 0.0)

                last_activity = db_summary.get("last_activity")
                if last_activity:
                    metrics.last_activity = datetime.fromisoformat(last_activity)
        else:
            # Obtener desde memoria
            counters = await self._collector.get_organization_counters(organization_id)

            # Métricas de facturación
            if EventType.INVOICE_CREATED.value in counters:
                counter = counters[EventType.INVOICE_CREATED.value]
                metrics.invoices.total_created = counter.count
                metrics.invoices.total_amount = counter.total_value
                if counter.count > 0:
                    metrics.invoices.avg_invoice_amount = counter.total_value / counter.count

            if EventType.INVOICE_PAID.value in counters:
                counter = counters[EventType.INVOICE_PAID.value]
                metrics.invoices.total_paid = counter.count
                metrics.invoices.paid_amount = counter.total_value

            # Calcular tasa de conversión
            if metrics.invoices.total_created > 0:
                metrics.invoices.conversion_rate = (
                    metrics.invoices.total_paid / metrics.invoices.total_created
                )

            # Métricas del bot
            for event_type, attr in [
                (EventType.BOT_MESSAGE, "total_messages"),
                (EventType.BOT_COMMAND, "total_commands"),
                (EventType.BOT_PHOTO, "total_photos"),
                (EventType.BOT_VOICE, "total_voice"),
            ]:
                if event_type.value in counters:
                    setattr(metrics.bot, attr, counters[event_type.value].count)

            # IA
            if EventType.AI_EXTRACTION.value in counters:
                counter = counters[EventType.AI_EXTRACTION.value]
                metrics.bot.ai_extractions_total = counter.count
                metrics.bot.ai_extractions_success = counter.success_count
                metrics.bot.ai_success_rate = counter.success_rate
                metrics.bot.avg_response_time_ms = counter.avg_duration_ms

            # Obtener última actividad
            events = await self._collector.get_events(
                organization_id=organization_id,
                limit=1
            )
            if events:
                metrics.last_activity = events[0].timestamp

        return metrics

    async def get_product_metrics(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> ProductMetrics:
        """
        Obtiene métricas globales del producto.

        Args:
            since: Inicio del período
            until: Fin del período

        Returns:
            Métricas del producto
        """
        if until is None:
            until = datetime.utcnow()
        if since is None:
            since = until - timedelta(days=30)

        metrics = ProductMetrics(
            period_start=since,
            period_end=until,
        )

        # Contadores globales
        global_counters = await self._collector.get_global_counters()

        # Facturas procesadas
        if EventType.INVOICE_CREATED.value in global_counters:
            counter = global_counters[EventType.INVOICE_CREATED.value]
            metrics.total_invoices_processed = counter.count
            metrics.total_invoice_amount = counter.total_value

        # Uso de features
        feature_events = [
            (EventType.BOT_PHOTO, "photo_extraction"),
            (EventType.BOT_VOICE, "voice_input"),
            (EventType.AI_EXTRACTION, "ai_extraction"),
        ]

        for event_type, feature_name in feature_events:
            if event_type.value in global_counters:
                metrics.feature_usage[feature_name] = global_counters[event_type.value].count

        return metrics

    async def get_usage_metrics(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> UsageMetrics:
        """
        Obtiene métricas de uso del sistema.

        Args:
            since: Inicio del período
            until: Fin del período

        Returns:
            Métricas de uso
        """
        if until is None:
            until = datetime.utcnow()
        if since is None:
            since = until - timedelta(days=7)

        metrics = UsageMetrics(
            period_start=since,
            period_end=until,
        )

        global_counters = await self._collector.get_global_counters()

        # API
        if EventType.API_REQUEST.value in global_counters:
            counter = global_counters[EventType.API_REQUEST.value]
            metrics.total_api_requests = counter.count
            metrics.avg_api_latency_ms = counter.avg_duration_ms

        if EventType.API_ERROR.value in global_counters:
            metrics.api_errors = global_counters[EventType.API_ERROR.value].count

        if metrics.total_api_requests > 0:
            metrics.api_error_rate = metrics.api_errors / metrics.total_api_requests

        # Bot
        bot_events = [EventType.BOT_MESSAGE, EventType.BOT_COMMAND, EventType.BOT_PHOTO, EventType.BOT_VOICE]
        for event_type in bot_events:
            if event_type.value in global_counters:
                metrics.total_bot_interactions += global_counters[event_type.value].count

        if EventType.BOT_ERROR.value in global_counters:
            metrics.bot_errors = global_counters[EventType.BOT_ERROR.value].count

        # Patrones por hora y día
        events = await self._collector.get_events(since=since, limit=10000)

        for event in events:
            hour = event.timestamp.hour
            metrics.usage_by_hour[hour] = metrics.usage_by_hour.get(hour, 0) + 1

            day_name = event.timestamp.strftime("%A")
            metrics.usage_by_day[day_name] = metrics.usage_by_day.get(day_name, 0) + 1

        return metrics

    async def get_organization_health_score(self, organization_id: str) -> float:
        """
        Calcula un score de salud para la organización.

        El score considera:
        - Actividad reciente
        - Tasa de éxito de operaciones
        - Uso de features

        Returns:
            Score de 0 a 100
        """
        metrics = await self.get_organization_metrics(
            organization_id,
            since=datetime.utcnow() - timedelta(days=7)
        )

        score = 0.0
        max_score = 100.0

        # Actividad reciente (40 puntos)
        if metrics.last_activity:
            days_since_activity = (datetime.utcnow() - metrics.last_activity).days
            if days_since_activity == 0:
                score += 40
            elif days_since_activity <= 1:
                score += 35
            elif days_since_activity <= 3:
                score += 25
            elif days_since_activity <= 7:
                score += 10

        # Tasa de conversión de facturas (30 puntos)
        if metrics.invoices.conversion_rate >= 0.8:
            score += 30
        elif metrics.invoices.conversion_rate >= 0.5:
            score += 20
        elif metrics.invoices.conversion_rate > 0:
            score += 10

        # Éxito de IA (20 puntos)
        if metrics.bot.ai_success_rate >= 0.9:
            score += 20
        elif metrics.bot.ai_success_rate >= 0.7:
            score += 15
        elif metrics.bot.ai_success_rate > 0:
            score += 5

        # Uso de features (10 puntos)
        features_used = 0
        if metrics.bot.total_photos > 0:
            features_used += 1
        if metrics.bot.total_voice > 0:
            features_used += 1
        if metrics.bot.ai_extractions_total > 0:
            features_used += 1

        score += min(features_used * 3.33, 10)

        return min(score, max_score)

    async def get_at_risk_organizations(
        self,
        threshold_days: int = 7,
        min_health_score: float = 50.0,
    ) -> List[Dict[str, Any]]:
        """
        Identifica organizaciones en riesgo de churn.

        Args:
            threshold_days: Días sin actividad para considerar en riesgo
            min_health_score: Score mínimo de salud

        Returns:
            Lista de organizaciones en riesgo
        """
        # Obtener todas las organizaciones con métricas
        summary = await self._collector.get_summary()

        at_risk: list[Dict[str, Any]] = []

        # Esto requeriría acceso a la lista de organizaciones desde la DB
        # Por ahora retornamos lista vacía - se integrará con el repo de orgs
        logger.info(f"Buscando organizaciones en riesgo (threshold: {threshold_days} días)")

        return at_risk

    async def get_summary(self) -> Dict[str, Any]:
        """Obtiene resumen general de métricas de negocio."""
        product = await self.get_product_metrics()
        usage = await self.get_usage_metrics()
        collector_summary = await self._collector.get_summary()

        return {
            "product": product.to_dict(),
            "usage": usage.to_dict(),
            "collector": collector_summary,
            "generated_at": datetime.utcnow().isoformat(),
        }

    # =========================================================================
    # MÉTRICAS DE JOYERÍA
    # =========================================================================

    async def get_jewelry_metrics(
        self,
        organization_id: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> JewelryMetrics:
        """
        Obtiene métricas específicas del negocio de joyería.

        Args:
            organization_id: ID de la organización
            since: Inicio del período (default: últimos 30 días)
            until: Fin del período (default: ahora)

        Returns:
            Métricas de joyería
        """
        if until is None:
            until = datetime.utcnow()
        if since is None:
            since = until - timedelta(days=30)

        metrics = JewelryMetrics(
            period_start=since,
            period_end=until,
        )

        counters = await self._collector.get_organization_counters(organization_id)

        # Clientes
        if EventType.CUSTOMER_NEW.value in counters:
            metrics.new_customers = counters[EventType.CUSTOMER_NEW.value].count
        if EventType.CUSTOMER_RETURNING.value in counters:
            metrics.returning_customers = counters[EventType.CUSTOMER_RETURNING.value].count
        metrics.total_customers_served = metrics.new_customers + metrics.returning_customers

        # Productos vendidos
        if EventType.PRODUCT_SOLD.value in counters:
            metrics.total_items_sold = counters[EventType.PRODUCT_SOLD.value].count

        # Ventas por material
        events = await self._collector.get_events(
            event_type=EventType.SALE_BY_MATERIAL,
            organization_id=organization_id,
            since=since,
            limit=10000,
        )
        for event in events:
            material = event.metadata.get("material", "Sin especificar")
            cantidad = event.metadata.get("cantidad", 1)
            # event.metadata contiene el valor en total_value a través del collector
            # pero aquí calculamos desde los eventos
            metrics.sales_by_material[material] = (
                metrics.sales_by_material.get(material, 0.0) + (event.metadata.get("subtotal", 0) or 0)
            )
            metrics.quantity_by_material[material] = (
                metrics.quantity_by_material.get(material, 0) + cantidad
            )

        # Ventas por categoría
        events = await self._collector.get_events(
            event_type=EventType.SALE_BY_CATEGORY,
            organization_id=organization_id,
            since=since,
            limit=10000,
        )
        for event in events:
            categoria = event.metadata.get("tipo_prenda", "Sin especificar")
            cantidad = event.metadata.get("cantidad", 1)
            metrics.sales_by_category[categoria] = (
                metrics.sales_by_category.get(categoria, 0.0) + (event.metadata.get("subtotal", 0) or 0)
            )
            metrics.quantity_by_category[categoria] = (
                metrics.quantity_by_category.get(categoria, 0) + cantidad
            )

        # Top productos
        top_products = await self.get_top_products(organization_id, since, until, limit=10)
        metrics.top_products = top_products

        # Rendimiento de vendedores
        seller_perf = await self.get_seller_performance(organization_id, since, until)
        metrics.seller_performance = seller_perf

        return metrics

    async def get_top_products(
        self,
        organization_id: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 10,
    ) -> List[TopProduct]:
        """
        Obtiene los productos más vendidos.

        Args:
            organization_id: ID de la organización
            since: Inicio del período
            until: Fin del período
            limit: Número máximo de productos a retornar

        Returns:
            Lista de productos más vendidos
        """
        if until is None:
            until = datetime.utcnow()
        if since is None:
            since = until - timedelta(days=30)

        events = await self._collector.get_events(
            event_type=EventType.PRODUCT_SOLD,
            organization_id=organization_id,
            since=since,
            limit=10000,
        )

        # Agregar por descripción
        products: Dict[str, TopProduct] = {}
        for event in events:
            descripcion = event.metadata.get("descripcion", "Sin descripción")
            cantidad = event.metadata.get("cantidad", 1)

            if descripcion not in products:
                products[descripcion] = TopProduct(
                    descripcion=descripcion,
                    material=event.metadata.get("material"),
                    tipo_prenda=event.metadata.get("tipo_prenda"),
                )

            products[descripcion].cantidad_vendida += cantidad
            # El valor está en el event data a través del collector
            subtotal = event.metadata.get("precio_unitario", 0) * cantidad
            products[descripcion].total_ingresos += subtotal

        # Ordenar por cantidad vendida
        sorted_products = sorted(
            products.values(),
            key=lambda p: p.cantidad_vendida,
            reverse=True
        )

        return sorted_products[:limit]

    async def get_customer_stats(
        self,
        organization_id: str,
        customer_cedula: str,
    ) -> CustomerStats:
        """
        Obtiene estadísticas de un cliente específico.

        Args:
            organization_id: ID de la organización
            customer_cedula: Cédula del cliente

        Returns:
            Estadísticas del cliente
        """
        stats = CustomerStats(customer_cedula=customer_cedula)

        # Buscar eventos de venta completada donde el cliente participó
        events = await self._collector.get_events(
            event_type=EventType.SALE_COMPLETED,
            organization_id=organization_id,
            limit=10000,
        )

        customer_events = [
            e for e in events
            if e.metadata.get("customer_cedula") == customer_cedula
        ]

        if not customer_events:
            return stats

        stats.total_purchases = len(customer_events)

        # Calcular totales
        for event in customer_events:
            # El valor de la venta está en el metadata o como value del evento
            # Usamos el patrón del collector donde value = total_amount
            pass

        # Obtener primera y última compra
        sorted_events = sorted(customer_events, key=lambda e: e.timestamp)
        if sorted_events:
            stats.first_purchase = sorted_events[0].timestamp
            stats.last_purchase = sorted_events[-1].timestamp

        # Buscar productos comprados para determinar favoritos
        product_events = await self._collector.get_events(
            event_type=EventType.PRODUCT_SOLD,
            organization_id=organization_id,
            limit=10000,
        )

        # Filtrar por facturas de este cliente
        customer_invoice_ids = {
            e.metadata.get("invoice_id")
            for e in customer_events
            if e.metadata.get("invoice_id")
        }

        materials: Dict[str, int] = {}
        categories: Dict[str, int] = {}
        total_spent = 0.0

        for event in product_events:
            if event.metadata.get("invoice_id") in customer_invoice_ids:
                material = event.metadata.get("material")
                categoria = event.metadata.get("tipo_prenda")
                cantidad = event.metadata.get("cantidad", 1)
                precio = event.metadata.get("precio_unitario", 0)
                total_spent += precio * cantidad

                if material:
                    materials[material] = materials.get(material, 0) + cantidad
                if categoria:
                    categories[categoria] = categories.get(categoria, 0) + cantidad

        stats.total_spent = total_spent
        if stats.total_purchases > 0:
            stats.avg_purchase_amount = total_spent / stats.total_purchases

        # Material y categoría favoritos
        if materials:
            stats.favorite_material = max(materials, key=materials.get)
        if categories:
            stats.favorite_category = max(categories, key=categories.get)

        return stats

    async def get_seller_performance(
        self,
        organization_id: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> List[SellerPerformance]:
        """
        Obtiene el rendimiento de los vendedores.

        Args:
            organization_id: ID de la organización
            since: Inicio del período
            until: Fin del período

        Returns:
            Lista de rendimiento por vendedor
        """
        if until is None:
            until = datetime.utcnow()
        if since is None:
            since = until - timedelta(days=30)

        # Obtener eventos de ventas de vendedores
        events = await self._collector.get_events(
            event_type=EventType.SELLER_SALE,
            organization_id=organization_id,
            since=since,
            limit=10000,
        )

        sellers: Dict[int, SellerPerformance] = {}

        for event in events:
            user_id = event.user_id
            if not user_id:
                continue

            if user_id not in sellers:
                sellers[user_id] = SellerPerformance(user_id=user_id)

            sellers[user_id].total_sales += 1
            sellers[user_id].items_sold += event.metadata.get("items_count", 0)
            # El monto total está en value o metadata
            # Por el patrón del collector, usamos metadata

        # Agregar clientes nuevos y recurrentes por vendedor
        new_customer_events = await self._collector.get_events(
            event_type=EventType.CUSTOMER_NEW,
            organization_id=organization_id,
            since=since,
            limit=10000,
        )
        for event in new_customer_events:
            user_id = event.user_id
            if user_id and user_id in sellers:
                sellers[user_id].new_customers += 1

        returning_customer_events = await self._collector.get_events(
            event_type=EventType.CUSTOMER_RETURNING,
            organization_id=organization_id,
            since=since,
            limit=10000,
        )
        for event in returning_customer_events:
            user_id = event.user_id
            if user_id and user_id in sellers:
                sellers[user_id].returning_customers += 1

        # Calcular promedios
        for seller in sellers.values():
            if seller.total_sales > 0:
                seller.avg_sale_amount = seller.total_amount / seller.total_sales

        # Ordenar por ventas totales
        sorted_sellers = sorted(
            sellers.values(),
            key=lambda s: s.total_sales,
            reverse=True
        )

        return sorted_sellers

    async def get_sales_by_material(
        self,
        organization_id: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Obtiene ventas agrupadas por material.

        Args:
            organization_id: ID de la organización
            since: Inicio del período
            until: Fin del período

        Returns:
            Diccionario con ventas por material
        """
        if until is None:
            until = datetime.utcnow()
        if since is None:
            since = until - timedelta(days=30)

        events = await self._collector.get_events(
            event_type=EventType.SALE_BY_MATERIAL,
            organization_id=organization_id,
            since=since,
            limit=10000,
        )

        materials: Dict[str, Dict[str, Any]] = {}
        for event in events:
            material = event.metadata.get("material", "Sin especificar")
            cantidad = event.metadata.get("cantidad", 1)
            peso = event.metadata.get("peso_gramos", 0) or 0

            if material not in materials:
                materials[material] = {
                    "cantidad": 0,
                    "peso_total_gramos": 0.0,
                    "ventas": 0,
                }

            materials[material]["cantidad"] += cantidad
            materials[material]["peso_total_gramos"] += peso
            materials[material]["ventas"] += 1

        return materials

    async def get_sales_by_category(
        self,
        organization_id: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Obtiene ventas agrupadas por categoría/tipo de prenda.

        Args:
            organization_id: ID de la organización
            since: Inicio del período
            until: Fin del período

        Returns:
            Diccionario con ventas por categoría
        """
        if until is None:
            until = datetime.utcnow()
        if since is None:
            since = until - timedelta(days=30)

        events = await self._collector.get_events(
            event_type=EventType.SALE_BY_CATEGORY,
            organization_id=organization_id,
            since=since,
            limit=10000,
        )

        categories: Dict[str, Dict[str, Any]] = {}
        for event in events:
            categoria = event.metadata.get("tipo_prenda", "Sin especificar")
            cantidad = event.metadata.get("cantidad", 1)

            if categoria not in categories:
                categories[categoria] = {
                    "cantidad": 0,
                    "ventas": 0,
                }

            categories[categoria]["cantidad"] += cantidad
            categories[categoria]["ventas"] += 1

        return categories

    def get_daily_time_series(
        self,
        organization_id: Optional[str] = None,
        event_type: Optional[str] = None,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Obtiene series temporales diarias desde la BD.

        Ideal para gráficos de líneas o barras.

        Args:
            organization_id: Filtrar por organización
            event_type: Filtrar por tipo de evento
            days: Número de días hacia atrás

        Returns:
            Lista de datos por día: [{date, count, total_value, success_rate}]
        """
        if not is_db_persistence_enabled():
            logger.warning("Persistencia BD deshabilitada, retornando lista vacía")
            return []

        return self._collector.get_daily_stats_from_db(
            organization_id=organization_id,
            event_type=event_type,
            days=days,
        )

    def get_historical_events(
        self,
        organization_id: Optional[str] = None,
        event_type: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Obtiene eventos históricos desde la BD.

        Args:
            organization_id: Filtrar por organización
            event_type: Filtrar por tipo de evento
            since: Desde esta fecha
            limit: Máximo de eventos

        Returns:
            Lista de eventos
        """
        if not is_db_persistence_enabled():
            logger.warning("Persistencia BD deshabilitada, retornando lista vacía")
            return []

        return self._collector.get_events_from_db(
            organization_id=organization_id,
            event_type=event_type,
            since=since,
            limit=limit,
        )


# ============================================================================
# SINGLETON
# ============================================================================

_business_metrics_service: Optional[BusinessMetricsService] = None


def get_business_metrics_service() -> BusinessMetricsService:
    """Obtiene la instancia singleton del servicio."""
    global _business_metrics_service
    if _business_metrics_service is None:
        _business_metrics_service = BusinessMetricsService()
    return _business_metrics_service
