# Jewelry Invoice Bot

[![CI](https://github.com/ryandeivis/facturacionjoyeriasbot/actions/workflows/ci.yml/badge.svg)](https://github.com/ryandeivis/facturacionjoyeriasbot/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

Bot de Telegram para facturación de joyerías con arquitectura **SaaS Multi-tenant**, integración con **n8n** para procesamiento de IA, y API REST completa.

## Características

- **Bot de Telegram** - Interfaz conversacional para crear facturas
- **Multi-tenant SaaS** - Múltiples organizaciones aisladas
- **Procesamiento IA** - Extracción de items desde texto, voz o fotos (via n8n + OpenAI)
- **Generación PDF** - Facturas profesionales con diseño personalizable
- **API REST** - Endpoints documentados con Swagger/OpenAPI
- **Rate Limiting** - Protección distribuida con Redis
- **Métricas** - Dashboard de métricas de negocio

## Stack Tecnológico

| Componente | Tecnología |
|------------|------------|
| Bot | Python 3.11+ / python-telegram-bot |
| API | FastAPI / Uvicorn |
| Base de Datos | PostgreSQL 15 / SQLAlchemy 2.0 |
| Cache | Redis 7 |
| Automatización | n8n (workflows) |
| IA | OpenAI GPT-4o / Whisper |
| Contenedores | Docker / Docker Compose |

## Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                        TELEGRAM USERS                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     TELEGRAM BOT (Python)                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  Handlers   │  │ Middleware  │  │     Services            │  │
│  │  - /start   │  │ - Auth      │  │  - Invoice Creator      │  │
│  │  - /factura │  │ - Tenant    │  │  - PDF Generator        │  │
│  │  - /lista   │  │ - Rate Limit│  │  - n8n Integration      │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
         │                    │                      │
         ▼                    ▼                      ▼
┌─────────────┐      ┌─────────────┐        ┌─────────────┐
│  PostgreSQL │      │    Redis    │        │     n8n     │
│  (Data)     │      │  (Cache)    │        │  (AI/PDF)   │
└─────────────┘      └─────────────┘        └─────────────┘
```

## Quick Start

### Requisitos

- Python 3.11+
- Docker y Docker Compose
- Token de Bot de Telegram
- (Opcional) n8n para procesamiento IA

### 1. Clonar el repositorio

```bash
git clone https://github.com/ryandeivis/facturacionjoyeriasbot.git
cd facturacionjoyeriasbot
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con tus credenciales
```

Variables requeridas:
```env
TELEGRAM_BOT_TOKEN=tu_token_aqui
DB_PASSWORD=password_seguro
SECRET_KEY=clave_secreta_32_chars
```

### 3. Iniciar con Docker

```bash
# Desarrollo
docker-compose up -d

# Con Redis y n8n
docker-compose --profile full up -d
```

### 4. Ejecutar migraciones

```bash
docker-compose --profile migrate up migrations
```

### 5. Verificar instalación

```bash
# Health check
curl http://localhost:8000/health

# Swagger UI
open http://localhost:8000/docs
```

## Estructura del Proyecto

```
jewelry_invoice_bot/
├── src/
│   ├── api/              # Endpoints REST (FastAPI)
│   ├── bot/              # Bot de Telegram
│   │   ├── handlers/     # Comandos y callbacks
│   │   └── middleware/   # Auth, tenant, rate limit
│   ├── core/             # Contexto y configuración
│   ├── database/         # Modelos y queries
│   ├── metrics/          # Métricas de negocio
│   ├── models/           # Schemas Pydantic
│   ├── services/         # Lógica de negocio
│   └── utils/            # Utilidades comunes
├── config/               # Configuración por entorno
├── tests/                # Tests (unit, integration, load)
├── docs/                 # Documentación
├── n8n/                  # Workflows n8n
└── docker-compose.yml    # Orquestación de servicios
```

## Documentación

| Documento | Descripción |
|-----------|-------------|
| [API Reference](docs/api/README.md) | Documentación completa de la API REST |
| [n8n Workflows](n8n/README.md) | Configuración de workflows de IA |
| [Load Testing](tests/load/README.md) | Pruebas de carga con Locust |
| [Architecture](docs/architecture/README.md) | Arquitectura y decisiones técnicas |
| [Deployment](docs/deployment/README.md) | Guía de despliegue a producción |
| [Development](docs/development/README.md) | Guía para desarrolladores |

## Comandos del Bot

| Comando | Descripción |
|---------|-------------|
| `/start` | Iniciar bot y autenticación |
| `/factura` | Crear nueva factura |
| `/lista` | Listar facturas recientes |
| `/buscar` | Buscar factura por número |
| `/ayuda` | Mostrar ayuda |

## API Endpoints

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/health` | Estado del sistema |
| GET | `/api/v1/invoices` | Listar facturas |
| POST | `/api/v1/invoices` | Crear factura |
| GET | `/api/v1/invoices/{id}` | Obtener factura |
| PATCH | `/api/v1/invoices/{id}/status` | Actualizar estado |
| GET | `/api/v1/organizations` | Listar organizaciones |

Ver documentación completa en [docs/api/README.md](docs/api/README.md).

## Testing

```bash
# Tests unitarios
pytest tests/unit/ -v

# Tests de integración
pytest tests/integration/ -v

# Coverage
pytest --cov=src --cov-report=html

# Load testing
locust -f tests/load/locustfile.py --host=http://localhost:8000
```

## Desarrollo

```bash
# Instalar dependencias
pip install -r requirements.txt

# Linting
ruff check src/

# Type checking
python scripts/typecheck.py --mode=strict

# Formateo
ruff format src/
```

## Roadmap

Mejoras opcionales pendientes para futuras versiones:

| #  | Mejora               | Descripción                              | Prioridad |
|----|----------------------|------------------------------------------|-----------|
| 2  | Regenerar SECRET_KEY | Rotar clave secreta si hubo exposición   | Baja      |
| 14 | Centralizar Logs     | Integrar con ELK, Datadog o CloudWatch   | Media     |
| 18 | Staging Environment  | Crear ambiente de staging completo       | Media     |

Ver [PLAN_20_MEJORAS_PRODUCCION.md](PLAN_20_MEJORAS_PRODUCCION.md) para detalles.

## Contribución

Ver [CONTRIBUTING.md](CONTRIBUTING.md) para guías de contribución.

## Changelog

Ver [CHANGELOG.md](CHANGELOG.md) para historial de cambios.

## Licencia

Este proyecto está bajo la licencia MIT. Ver [LICENSE](LICENSE) para más detalles.

## Contacto

- **Repositorio**: [github.com/ryandeivis/facturacionjoyeriasbot](https://github.com/ryandeivis/facturacionjoyeriasbot)
- **Issues**: [GitHub Issues](https://github.com/ryandeivis/facturacionjoyeriasbot/issues)
