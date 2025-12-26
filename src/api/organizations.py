"""
Organizations API

Endpoints para gestión de organizaciones (tenants) en el sistema SaaS.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field, asdict

from src.utils.logger import get_logger
from src.bot.middleware.plan_limits import PlanTier, PLAN_CONFIGS

logger = get_logger(__name__)


# ============================================================================
# MODELS
# ============================================================================

@dataclass
class OrganizationCreate:
    """Datos para crear una organización."""
    name: str
    plan: str = "basic"
    owner_email: str = ""
    invoice_prefix: str = "FAC"
    settings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrganizationUpdate:
    """Datos para actualizar una organización."""
    name: Optional[str] = None
    plan: Optional[str] = None
    invoice_prefix: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


@dataclass
class OrganizationResponse:
    """Respuesta con datos de organización."""
    id: str
    name: str
    plan: str
    invoice_prefix: str
    is_active: bool
    users_count: int
    invoices_count: int
    created_at: str
    settings: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================================
# SERVICE
# ============================================================================

class OrganizationService:
    """Servicio para gestión de organizaciones."""

    async def list_organizations(
        self,
        limit: int = 50,
        offset: int = 0,
        include_inactive: bool = False
    ) -> List[Dict[str, Any]]:
        """Lista todas las organizaciones."""
        try:
            from src.database.connection import get_async_db
            from src.database.models import TenantConfig, User, Invoice
            from sqlalchemy import select, func

            async with get_async_db() as db:
                query = select(TenantConfig)
                if not include_inactive:
                    query = query.where(TenantConfig.is_active == True)

                query = query.order_by(TenantConfig.created_at.desc())
                query = query.limit(limit).offset(offset)

                result = await db.execute(query)
                configs = result.scalars().all()

                orgs = []
                for config in configs:
                    # Contar usuarios
                    users_result = await db.execute(
                        select(func.count(User.id)).where(
                            User.organization_id == config.organization_id,
                            User.is_deleted == False
                        )
                    )
                    users_count = users_result.scalar() or 0

                    # Contar facturas
                    invoices_result = await db.execute(
                        select(func.count(Invoice.id)).where(
                            Invoice.organization_id == config.organization_id,
                            Invoice.is_deleted == False
                        )
                    )
                    invoices_count = invoices_result.scalar() or 0

                    orgs.append({
                        "id": config.organization_id,
                        "name": config.organization_name,
                        "plan": config.plan,
                        "invoice_prefix": config.invoice_prefix,
                        "is_active": config.is_active,
                        "users_count": users_count,
                        "invoices_count": invoices_count,
                        "created_at": config.created_at.isoformat() + "Z"
                    })

                return orgs

        except Exception as e:
            logger.error(f"Error listando organizaciones: {e}")
            raise

    async def get_organization(self, org_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene una organización por ID."""
        try:
            from src.database.connection import get_async_db
            from src.database.models import TenantConfig, User, Invoice
            from sqlalchemy import select, func

            async with get_async_db() as db:
                result = await db.execute(
                    select(TenantConfig).where(
                        TenantConfig.organization_id == org_id
                    )
                )
                config = result.scalar_one_or_none()

                if not config:
                    return None

                # Contar usuarios
                users_result = await db.execute(
                    select(func.count(User.id)).where(
                        User.organization_id == org_id,
                        User.is_deleted == False
                    )
                )
                users_count = users_result.scalar() or 0

                # Contar facturas
                invoices_result = await db.execute(
                    select(func.count(Invoice.id)).where(
                        Invoice.organization_id == org_id,
                        Invoice.is_deleted == False
                    )
                )
                invoices_count = invoices_result.scalar() or 0

                # Obtener límites del plan
                plan_limits = PLAN_CONFIGS.get(
                    PlanTier(config.plan),
                    PLAN_CONFIGS[PlanTier.BASIC]
                )

                return {
                    "id": config.organization_id,
                    "name": config.organization_name,
                    "plan": config.plan,
                    "invoice_prefix": config.invoice_prefix,
                    "is_active": config.is_active,
                    "users_count": users_count,
                    "invoices_count": invoices_count,
                    "created_at": config.created_at.isoformat() + "Z",
                    "plan_limits": {
                        "invoices_per_month": plan_limits.invoices_per_month,
                        "users_per_org": plan_limits.users_per_org,
                        "max_items_per_invoice": plan_limits.max_items_per_invoice,
                        "features": {
                            "ai_extraction": plan_limits.ai_extraction,
                            "voice_input": plan_limits.voice_input,
                            "photo_input": plan_limits.photo_input,
                            "custom_templates": plan_limits.custom_templates,
                            "api_access": plan_limits.api_access,
                        }
                    }
                }

        except Exception as e:
            logger.error(f"Error obteniendo organización {org_id}: {e}")
            raise

    async def create_organization(self, data: OrganizationCreate) -> Dict[str, Any]:
        """Crea una nueva organización."""
        try:
            import uuid
            from src.database.connection import get_async_db
            from src.database.models import TenantConfig

            org_id = str(uuid.uuid4())

            async with get_async_db() as db:
                config = TenantConfig(
                    organization_id=org_id,
                    organization_name=data.name,
                    plan=data.plan,
                    invoice_prefix=data.invoice_prefix,
                    is_active=True
                )
                db.add(config)
                await db.commit()
                await db.refresh(config)

                logger.info(f"Organización creada: {org_id} ({data.name})")

                return {
                    "id": org_id,
                    "name": data.name,
                    "plan": data.plan,
                    "invoice_prefix": data.invoice_prefix,
                    "is_active": True,
                    "created_at": config.created_at.isoformat() + "Z"
                }

        except Exception as e:
            logger.error(f"Error creando organización: {e}")
            raise

    async def update_organization(
        self,
        org_id: str,
        data: OrganizationUpdate
    ) -> Optional[Dict[str, Any]]:
        """Actualiza una organización."""
        try:
            from src.database.connection import get_async_db
            from src.database.models import TenantConfig
            from sqlalchemy import select

            async with get_async_db() as db:
                result = await db.execute(
                    select(TenantConfig).where(
                        TenantConfig.organization_id == org_id
                    )
                )
                config = result.scalar_one_or_none()

                if not config:
                    return None

                # Actualizar campos
                if data.name is not None:
                    config.organization_name = data.name
                if data.plan is not None:
                    config.plan = data.plan
                if data.invoice_prefix is not None:
                    config.invoice_prefix = data.invoice_prefix
                if data.is_active is not None:
                    config.is_active = data.is_active

                await db.commit()
                await db.refresh(config)

                logger.info(f"Organización actualizada: {org_id}")

                return await self.get_organization(org_id)

        except Exception as e:
            logger.error(f"Error actualizando organización {org_id}: {e}")
            raise

    async def get_organization_stats(self, org_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene estadísticas de una organización."""
        try:
            from src.database.queries import get_invoice_stats_async
            from src.database.connection import get_async_db

            async with get_async_db() as db:
                stats = await get_invoice_stats_async(db, org_id)
                return {
                    "organization_id": org_id,
                    "invoices": stats,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }

        except Exception as e:
            logger.error(f"Error obteniendo stats de {org_id}: {e}")
            raise


# Instancia global
org_service = OrganizationService()


# ============================================================================
# FASTAPI ROUTER
# ============================================================================

try:
    from fastapi import APIRouter, HTTPException, Query
    from pydantic import BaseModel, Field

    class OrgCreateRequest(BaseModel):
        name: str = Field(..., min_length=1, max_length=100)
        plan: str = Field(default="basic", pattern="^(basic|pro|enterprise)$")
        invoice_prefix: str = Field(default="FAC", max_length=10)

    class OrgUpdateRequest(BaseModel):
        name: Optional[str] = Field(None, min_length=1, max_length=100)
        plan: Optional[str] = Field(None, pattern="^(basic|pro|enterprise)$")
        invoice_prefix: Optional[str] = Field(None, max_length=10)
        is_active: Optional[bool] = None

    organizations_router = APIRouter(prefix="/organizations", tags=["organizations"])

    @organizations_router.get("")
    async def list_orgs(
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        include_inactive: bool = Query(default=False)
    ):
        """Lista todas las organizaciones."""
        return await org_service.list_organizations(limit, offset, include_inactive)

    @organizations_router.get("/{org_id}")
    async def get_org(org_id: str):
        """Obtiene una organización por ID."""
        org = await org_service.get_organization(org_id)
        if not org:
            raise HTTPException(status_code=404, detail="Organización no encontrada")
        return org

    @organizations_router.post("")
    async def create_org(request: OrgCreateRequest):
        """Crea una nueva organización."""
        data = OrganizationCreate(
            name=request.name,
            plan=request.plan,
            invoice_prefix=request.invoice_prefix
        )
        return await org_service.create_organization(data)

    @organizations_router.patch("/{org_id}")
    async def update_org(org_id: str, request: OrgUpdateRequest):
        """Actualiza una organización."""
        data = OrganizationUpdate(
            name=request.name,
            plan=request.plan,
            invoice_prefix=request.invoice_prefix,
            is_active=request.is_active
        )
        org = await org_service.update_organization(org_id, data)
        if not org:
            raise HTTPException(status_code=404, detail="Organización no encontrada")
        return org

    @organizations_router.get("/{org_id}/stats")
    async def get_org_stats(org_id: str):
        """Obtiene estadísticas de una organización."""
        stats = await org_service.get_organization_stats(org_id)
        if not stats:
            raise HTTPException(status_code=404, detail="Organización no encontrada")
        return stats

except ImportError:
    organizations_router = None