# Arquitectura del Sistema

Documentación técnica de la arquitectura de Jewelry Invoice Bot.

## Tabla de Contenidos

- [Visión General](#visión-general)
- [Arquitectura SaaS Multi-tenant](#arquitectura-saas-multi-tenant)
- [Capas de la Aplicación](#capas-de-la-aplicación)
- [Flujo de Datos](#flujo-de-datos)
- [Componentes Principales](#componentes-principales)
- [Patrones de Diseño](#patrones-de-diseño)
- [Decisiones Técnicas (ADRs)](#decisiones-técnicas-adrs)

---

## Visión General

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENTES                                       │
│                                                                             │
│    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                │
│    │   Telegram   │    │   REST API   │    │   n8n        │                │
│    │   (Usuarios) │    │   (Sistemas) │    │   (Webhooks) │                │
│    └──────┬───────┘    └──────┬───────┘    └──────┬───────┘                │
└───────────┼───────────────────┼───────────────────┼─────────────────────────┘
            │                   │                   │
            ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CAPA DE PRESENTACIÓN                                │
│                                                                             │
│    ┌──────────────────────┐    ┌──────────────────────┐                    │
│    │     Bot Telegram     │    │      FastAPI         │                    │
│    │  - Handlers          │    │  - /api/v1/*         │                    │
│    │  - Callbacks         │    │  - /health           │                    │
│    │  - Middleware        │    │  - /metrics          │                    │
│    └──────────┬───────────┘    └──────────┬───────────┘                    │
└───────────────┼────────────────────────────┼────────────────────────────────┘
                │                            │
                ▼                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CAPA DE SERVICIOS                                   │
│                                                                             │
│    ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐          │
│    │  Invoice   │  │   Auth     │  │    n8n     │  │   PDF      │          │
│    │  Service   │  │  Service   │  │  Service   │  │  Service   │          │
│    └────────────┘  └────────────┘  └────────────┘  └────────────┘          │
└─────────────────────────────────────────────────────────────────────────────┘
                │                            │
                ▼                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CAPA DE DATOS                                       │
│                                                                             │
│    ┌────────────────┐    ┌────────────────┐    ┌────────────────┐          │
│    │   PostgreSQL   │    │     Redis      │    │   n8n Server   │          │
│    │   (Persistente)│    │    (Cache)     │    │   (Workflows)  │          │
│    └────────────────┘    └────────────────┘    └────────────────┘          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Arquitectura SaaS Multi-tenant

### Modelo de Aislamiento

Utilizamos **aislamiento a nivel de fila** (Row-Level Isolation) con `organization_id`:

```
┌─────────────────────────────────────────────────────────────────┐
│                      BASE DE DATOS                              │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    organizations                         │   │
│  │  id          │ name              │ plan    │ is_active  │   │
│  │──────────────┼───────────────────┼─────────┼────────────│   │
│  │  org-001     │ Joyería El Dorado │ pro     │ true       │   │
│  │  org-002     │ Brillantes Caribe │ basic   │ true       │   │
│  │  org-003     │ Oro Express       │ enterprise │ true    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│              ┌───────────────┼───────────────┐                  │
│              ▼               ▼               ▼                  │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐   │
│  │    users        │ │    invoices     │ │   audit_logs    │   │
│  │ organization_id │ │ organization_id │ │ organization_id │   │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Flujo de Tenant

```
Request → Middleware Tenant → Extrae org_id → Context → Query Filtrado
                                    │
                                    ▼
                          ┌─────────────────┐
                          │  TenantContext  │
                          │  - org_id       │
                          │  - user_id      │
                          │  - plan_limits  │
                          └─────────────────┘
```

### Código del Middleware

```python
# src/bot/middleware/tenant.py
class TenantMiddleware:
    async def __call__(self, handler, event, data):
        # Extraer organization_id del usuario
        org_id = await self._get_org_from_user(event.from_user.id)

        # Establecer contexto
        tenant_context.set(org_id)

        # Continuar con el handler
        return await handler(event, data)
```

---

## Capas de la Aplicación

### 1. Capa de Presentación (`src/api/`, `src/bot/`)

Responsabilidades:
- Recibir requests HTTP/Telegram
- Validar entrada (Pydantic)
- Transformar respuestas
- Manejo de errores

```
src/
├── api/
│   ├── app.py           # FastAPI app
│   ├── health.py        # Health endpoints
│   ├── invoices.py      # CRUD facturas
│   └── organizations.py # CRUD organizaciones
│
└── bot/
    ├── main.py          # Application entry
    ├── handlers/        # Comandos Telegram
    │   ├── start.py
    │   ├── invoice.py
    │   └── callbacks.py
    └── middleware/      # Auth, Tenant, Rate Limit
```

### 2. Capa de Servicios (`src/services/`)

Responsabilidades:
- Lógica de negocio
- Orquestación de operaciones
- Integración con externos (n8n)

```
src/services/
├── invoice_service.py   # Crear, editar, exportar facturas
├── n8n_service.py       # Comunicación con n8n
├── pdf_service.py       # Generación de PDFs
└── text_parser.py       # Parseo de texto a items
```

### 3. Capa de Datos (`src/database/`)

Responsabilidades:
- Modelos SQLAlchemy
- Queries optimizados
- Conexión y pool

```
src/database/
├── connection.py        # Engine y SessionLocal
├── models.py            # Modelos ORM
├── mixins.py            # Mixins reutilizables
└── queries/
    ├── base.py          # BaseQuery
    ├── invoice_queries.py
    └── user_queries.py
```

### 4. Capa de Utilidades (`src/utils/`)

Responsabilidades:
- Funcionalidades transversales
- No específicas de negocio

```
src/utils/
├── logger.py            # Logging estructurado
├── metrics.py           # Métricas Prometheus
├── crypto.py            # Encriptación
└── rate_limiter.py      # Rate limiting
```

---

## Flujo de Datos

### Crear Factura (Bot)

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ Usuario  │────▶│   Bot    │────▶│   n8n    │────▶│  OpenAI  │
│ Telegram │     │ Handler  │     │ Workflow │     │  GPT-4o  │
└──────────┘     └────┬─────┘     └────┬─────┘     └──────────┘
                      │                │
                      │                │ Items extraídos
                      │                ▼
                      │          ┌──────────┐
                      │          │  Invoice │
                      │◀─────────│  Service │
                      │          └────┬─────┘
                      │               │
                      │               ▼
                      │          ┌──────────┐
                      │          │ Database │
                      │          │ (INSERT) │
                      │          └──────────┘
                      │
                      ▼
                 ┌──────────┐
                 │   PDF    │
                 │ Generado │
                 └──────────┘
```

### Crear Factura (API)

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Client  │────▶│  FastAPI │────▶│  Invoice │────▶│ Database │
│  HTTP    │     │ Endpoint │     │  Service │     │  (Query) │
└──────────┘     └────┬─────┘     └──────────┘     └──────────┘
                      │
                      │ JSON Response
                      ▼
                 ┌──────────┐
                 │ Response │
                 │ Pydantic │
                 └──────────┘
```

---

## Componentes Principales

### Base de Datos

```
┌─────────────────────────────────────────────────────────────┐
│                      POSTGRESQL                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  organizations        users              invoices           │
│  ├── id (PK)          ├── id (PK)        ├── id (PK)       │
│  ├── name             ├── org_id (FK)    ├── org_id (FK)   │
│  ├── plan             ├── cedula         ├── numero        │
│  ├── invoice_prefix   ├── password       ├── cliente_*     │
│  └── is_active        ├── role           ├── items (JSON)  │
│                       └── telegram_id    ├── totales       │
│                                          └── estado        │
│                                                             │
│  invoice_items        audit_logs         metric_events     │
│  ├── id (PK)          ├── id (PK)        ├── id (PK)       │
│  ├── invoice_id (FK)  ├── org_id (FK)    ├── org_id (FK)   │
│  ├── descripcion      ├── user_id        ├── event_type    │
│  ├── cantidad         ├── action         ├── value         │
│  └── precio           └── timestamp      └── timestamp     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Índices Optimizados

```sql
-- Queries frecuentes
CREATE INDEX ix_invoices_org_created ON invoices(organization_id, created_at);
CREATE INDEX ix_invoices_org_deleted ON invoices(organization_id, is_deleted);
CREATE INDEX ix_users_org_cedula ON users(organization_id, cedula);
CREATE INDEX ix_audit_org_timestamp ON audit_logs(organization_id, timestamp);
```

### Cache (Redis)

```
┌─────────────────────────────────────────────────────────────┐
│                        REDIS                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Key Pattern                    │ TTL      │ Uso           │
│  ───────────────────────────────┼──────────┼─────────────  │
│  tenant:{org_id}:config         │ 30 min   │ Config tenant │
│  user:{user_id}:session         │ 15 min   │ Sesión auth   │
│  rate:{user_id}:{endpoint}      │ 1 min    │ Rate limiting │
│  invoice:{id}:pdf               │ 5 min    │ Cache PDF     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Patrones de Diseño

### 1. Repository Pattern

```python
# src/database/queries/invoice_queries.py
class InvoiceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, invoice_id: str) -> Invoice | None:
        stmt = select(Invoice).where(Invoice.id == invoice_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_org(
        self, org_id: str, limit: int = 50
    ) -> list[Invoice]:
        stmt = (
            select(Invoice)
            .where(Invoice.organization_id == org_id)
            .order_by(Invoice.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
```

### 2. Factory Pattern (Tests)

```python
# tests/factories/invoice.py
class InvoiceFactory(factory.Factory):
    class Meta:
        model = Invoice

    id = factory.LazyFunction(lambda: str(uuid4()))
    numero_factura = factory.Sequence(lambda n: f"FAC-{n:05d}")
    organization_id = factory.LazyFunction(lambda: str(uuid4()))
    cliente_nombre = factory.Faker("name", locale="es_CO")
    estado = "PENDIENTE"
```

### 3. Circuit Breaker

```python
# src/database/connection.py
class DatabaseCircuitBreaker:
    def __init__(self, failure_threshold: int = 5):
        self.failures = 0
        self.threshold = failure_threshold
        self.state = "CLOSED"

    async def execute(self, operation):
        if self.state == "OPEN":
            raise CircuitOpenError("Database unavailable")

        try:
            result = await operation()
            self.failures = 0
            return result
        except Exception:
            self.failures += 1
            if self.failures >= self.threshold:
                self.state = "OPEN"
            raise
```

### 4. Middleware Chain

```python
# src/bot/main.py
app = Application.builder().token(TOKEN).build()

# Middleware chain (orden importa)
app.add_handler(TypeHandler(Update, tenant_middleware), group=-3)
app.add_handler(TypeHandler(Update, auth_middleware), group=-2)
app.add_handler(TypeHandler(Update, rate_limit_middleware), group=-1)

# Handlers
app.add_handler(CommandHandler("start", start_handler))
app.add_handler(CommandHandler("factura", factura_handler))
```

---

## Decisiones Técnicas (ADRs)

### ADR-001: PostgreSQL sobre MongoDB

**Contexto**: Necesitamos persistencia de datos para facturas multi-tenant.

**Decisión**: PostgreSQL con SQLAlchemy 2.0.

**Razones**:
- Transacciones ACID para datos financieros
- Soporte nativo para JSON (items de factura)
- Índices compuestos para queries multi-tenant
- Madurez y estabilidad

### ADR-002: Redis para Rate Limiting

**Contexto**: Rate limiting debe funcionar en múltiples instancias.

**Decisión**: Redis con algoritmo sliding window.

**Razones**:
- Operaciones atómicas (INCR, EXPIRE)
- Compartido entre instancias
- Bajo latencia (~1ms)

### ADR-003: n8n para Procesamiento IA

**Contexto**: Necesitamos procesar texto, voz y fotos con IA.

**Decisión**: Delegar a n8n via webhooks.

**Razones**:
- Separación de responsabilidades
- Fácil cambio de modelos IA
- Visual debugging de workflows
- No bloquea el bot

### ADR-004: Row-Level Multi-tenancy

**Contexto**: Múltiples organizaciones en una BD.

**Decisión**: Aislamiento por `organization_id` en cada tabla.

**Razones**:
- Menor costo operativo (una BD)
- Queries simples con filtro
- Escalable hasta ~1000 tenants
- Fácil backup/restore

---

## Referencias

- [Clean Architecture - Robert C. Martin](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Multi-tenant SaaS Patterns](https://docs.microsoft.com/en-us/azure/architecture/guide/multitenant/overview)
- [python-telegram-bot Architecture](https://github.com/python-telegram-bot/python-telegram-bot/wiki/Architecture)
