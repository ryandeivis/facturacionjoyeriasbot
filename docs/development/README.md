# Guía de Desarrollo

Guía completa para desarrolladores que trabajan en Jewelry Invoice Bot.

## Tabla de Contenidos

- [Setup Local](#setup-local)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Flujo de Trabajo](#flujo-de-trabajo)
- [Testing](#testing)
- [Linting y Formateo](#linting-y-formateo)
- [Type Checking](#type-checking)
- [Base de Datos](#base-de-datos)
- [Debugging](#debugging)
- [IDE Setup](#ide-setup)
- [Herramientas Útiles](#herramientas-útiles)

---

## Setup Local

### Requisitos

- Python 3.11+
- Docker y Docker Compose
- Git
- (Recomendado) VS Code o PyCharm

### Instalación

```bash
# 1. Clonar repositorio
git clone https://github.com/ryandeivis/facturacionjoyeriasbot.git
cd facturacionjoyeriasbot

# 2. Crear entorno virtual
python -m venv venv

# Activar (Linux/Mac)
source venv/bin/activate

# Activar (Windows)
.\venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus valores

# 5. Iniciar servicios de desarrollo
docker-compose up -d db redis

# 6. Ejecutar migraciones
alembic upgrade head

# 7. Verificar instalación
python -c "from src.bot.main import main; print('OK')"
```

### Iniciar Bot en Desarrollo

```bash
# Opción 1: Directamente
python -m src.bot.main

# Opción 2: Con auto-reload (watchdog)
watchmedo auto-restart --patterns="*.py" --recursive -- python -m src.bot.main

# Opción 3: Solo API (sin bot)
uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
```

---

## Estructura del Proyecto

```
jewelry_invoice_bot/
│
├── src/                      # Código fuente principal
│   ├── __init__.py
│   ├── api/                  # API REST (FastAPI)
│   │   ├── app.py            # Aplicación FastAPI
│   │   ├── health.py         # Endpoints de salud
│   │   ├── invoices.py       # CRUD facturas
│   │   └── organizations.py  # CRUD organizaciones
│   │
│   ├── bot/                  # Bot de Telegram
│   │   ├── main.py           # Entry point del bot
│   │   ├── handlers/         # Comandos y callbacks
│   │   │   ├── start.py      # /start
│   │   │   ├── invoice.py    # /factura, flujo de creación
│   │   │   ├── callbacks.py  # Botones inline
│   │   │   └── utils.py      # Helpers
│   │   └── middleware/       # Procesamiento previo
│   │       ├── auth.py       # Autenticación
│   │       ├── tenant.py     # Multi-tenant
│   │       └── rate_limit.py # Rate limiting
│   │
│   ├── core/                 # Núcleo de la aplicación
│   │   └── context.py        # Contexto de tenant
│   │
│   ├── database/             # Capa de datos
│   │   ├── connection.py     # Engine y sesiones
│   │   ├── models.py         # Modelos SQLAlchemy
│   │   ├── mixins.py         # Mixins reutilizables
│   │   └── queries/          # Queries organizadas
│   │       ├── base.py
│   │       ├── invoice_queries.py
│   │       └── user_queries.py
│   │
│   ├── metrics/              # Métricas de negocio
│   │   └── business.py       # Métricas SaaS
│   │
│   ├── models/               # Schemas Pydantic
│   │   ├── invoice.py
│   │   └── user.py
│   │
│   ├── services/             # Lógica de negocio
│   │   ├── invoice_service.py
│   │   ├── n8n_service.py
│   │   └── pdf_service.py
│   │
│   └── utils/                # Utilidades
│       ├── logger.py         # Logging estructurado
│       ├── metrics.py        # Métricas Prometheus
│       ├── crypto.py         # Encriptación
│       └── rate_limiter.py   # Rate limiting
│
├── config/                   # Configuración
│   ├── settings.py           # Settings principales
│   ├── environments.py       # Por entorno
│   └── constants.py          # Constantes
│
├── tests/                    # Tests
│   ├── conftest.py           # Fixtures globales
│   ├── factories/            # Factory Boy
│   ├── unit/                 # Tests unitarios
│   ├── integration/          # Tests de integración
│   └── load/                 # Tests de carga (Locust)
│
├── docs/                     # Documentación
│   ├── api/                  # API Reference
│   ├── architecture/         # Arquitectura
│   ├── deployment/           # Despliegue
│   └── development/          # Esta guía
│
├── n8n/                      # Workflows n8n
│   └── README.md
│
├── scripts/                  # Scripts de utilidad
│   └── typecheck.py          # Type checking
│
├── docker-compose.yml        # Orquestación Docker
├── Dockerfile                # Imagen Docker
├── requirements.txt          # Dependencias Python
├── pyproject.toml            # Configuración de herramientas
├── alembic.ini               # Configuración Alembic
└── .env.example              # Template de variables
```

---

## Flujo de Trabajo

### 1. Crear Branch

```bash
# Actualizar main
git checkout main
git pull origin main

# Crear feature branch
git checkout -b feat/nombre-feature

# O fix branch
git checkout -b fix/descripcion-bug
```

### 2. Desarrollar

```bash
# Hacer cambios
# ...

# Ejecutar tests frecuentemente
pytest tests/unit/ -v

# Verificar linting
ruff check src/

# Verificar tipos
python scripts/typecheck.py
```

### 3. Commit

```bash
# Agregar cambios
git add .

# Commit con mensaje convencional
git commit -m "feat(invoice): agregar validación de items duplicados"
```

### 4. Push y PR

```bash
# Push
git push origin feat/nombre-feature

# Crear PR en GitHub
# - Llenar template
# - Esperar CI
# - Solicitar review
```

---

## Testing

### Ejecutar Tests

```bash
# Todos los tests
pytest

# Solo unitarios
pytest tests/unit/ -v

# Solo integración
pytest tests/integration/ -v

# Test específico
pytest tests/unit/test_invoice_service.py -v

# Test por nombre
pytest -k "test_create_invoice" -v
```

### Coverage

```bash
# Generar reporte
pytest --cov=src --cov-report=html

# Ver reporte en terminal
pytest --cov=src --cov-report=term-missing

# Abrir reporte HTML
open htmlcov/index.html  # Mac
start htmlcov/index.html # Windows
xdg-open htmlcov/index.html # Linux
```

### Factories

Usamos `factory-boy` para generar datos de prueba:

```python
from tests.factories import InvoiceFactory, UserFactory

# Crear instancia
invoice = InvoiceFactory()

# Con atributos específicos
invoice = InvoiceFactory(
    estado="PAGADA",
    cliente_nombre="Juan Pérez"
)

# Crear múltiples
invoices = InvoiceFactory.create_batch(10)

# Solo construir (sin guardar)
invoice_data = InvoiceFactory.build()
```

### Fixtures Disponibles

```python
# conftest.py

@pytest.fixture
def db_session():
    """Sesión de base de datos para tests."""
    ...

@pytest.fixture
def test_client():
    """Cliente HTTP para tests de API."""
    ...

@pytest.fixture
def mock_telegram_update():
    """Update de Telegram mockeado."""
    ...

@pytest.fixture
def authenticated_user():
    """Usuario autenticado para tests."""
    ...
```

### Load Testing

```bash
# Iniciar Locust (modo UI)
locust -f tests/load/locustfile.py --host=http://localhost:8000

# Abrir http://localhost:8089

# Modo headless (CI)
locust -f tests/load/locustfile.py \
    --headless \
    -u 50 -r 5 -t 5m \
    --host=http://localhost:8000 \
    --html=reports/load_test.html
```

---

## Linting y Formateo

### Ruff (Linting + Formateo)

```bash
# Verificar estilo
ruff check src/

# Verificar con fix automático
ruff check src/ --fix

# Formatear código
ruff format src/

# Verificar formateo (sin cambiar)
ruff format src/ --check
```

### Configuración (pyproject.toml)

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]
ignore = ["E501"]  # Line too long (handled by formatter)

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

### Pre-commit Hook

```bash
# Instalar
pip install pre-commit
pre-commit install

# Ejecutar manualmente
pre-commit run --all-files
```

---

## Type Checking

### MyPy

```bash
# Verificación básica
python scripts/typecheck.py

# Modo estricto
python scripts/typecheck.py --mode=strict

# Generar reporte
python scripts/typecheck.py --mode=report
```

### Configuración (pyproject.toml)

```toml
[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false
```

### Tips de Tipado

```python
# Imports de typing
from typing import Optional, List, Dict, Any
from collections.abc import Sequence

# Optional vs | None (Python 3.10+)
def get_user(id: int) -> User | None:
    ...

# Generics
def process_items(items: list[Item]) -> dict[str, Any]:
    ...

# TypedDict para diccionarios estructurados
class InvoiceDict(TypedDict):
    id: str
    numero: str
    total: float

# Protocol para duck typing
class Repository(Protocol):
    async def get(self, id: str) -> Model | None: ...
    async def save(self, model: Model) -> None: ...
```

---

## Base de Datos

### Crear Migración

```bash
# Auto-generar desde modelos
alembic revision --autogenerate -m "descripcion del cambio"

# Migración vacía (manual)
alembic revision -m "descripcion"
```

### Aplicar Migraciones

```bash
# Aplicar todas las pendientes
alembic upgrade head

# Aplicar una específica
alembic upgrade abc123

# Rollback una versión
alembic downgrade -1

# Ver estado actual
alembic current

# Ver historial
alembic history
```

### Shell de Base de Datos

```bash
# Conectar a PostgreSQL
docker-compose exec db psql -U postgres -d jewelry_db

# Comandos útiles en psql
\dt          # Listar tablas
\d invoices  # Describir tabla
\di          # Listar índices
\q           # Salir
```

### Queries de Desarrollo

```sql
-- Ver facturas recientes
SELECT id, numero_factura, estado, created_at
FROM invoices
ORDER BY created_at DESC
LIMIT 10;

-- Contar por organización
SELECT organization_id, COUNT(*) as total
FROM invoices
GROUP BY organization_id;

-- Ver usuarios por rol
SELECT role, COUNT(*) FROM users GROUP BY role;
```

---

## Debugging

### Logging

```python
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Niveles
logger.debug("Detalle para debugging")
logger.info("Operación completada")
logger.warning("Situación inesperada")
logger.error("Error que requiere atención")

# Con contexto
logger.info(
    "Invoice created",
    extra={
        "invoice_id": invoice.id,
        "organization_id": org_id,
    }
)
```

### Debugger (pdb)

```python
# Insertar breakpoint
import pdb; pdb.set_trace()

# Python 3.7+
breakpoint()

# Comandos pdb
# n - next line
# s - step into
# c - continue
# p var - print variable
# l - list code
# q - quit
```

### VS Code Debugging

```json
// .vscode/launch.json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Bot",
            "type": "python",
            "request": "launch",
            "module": "src.bot.main",
            "env": {
                "ENVIRONMENT": "development"
            }
        },
        {
            "name": "API",
            "type": "python",
            "request": "launch",
            "module": "uvicorn",
            "args": ["src.api.app:app", "--reload"],
            "env": {
                "ENVIRONMENT": "development"
            }
        },
        {
            "name": "Tests",
            "type": "python",
            "request": "launch",
            "module": "pytest",
            "args": ["-v", "${file}"]
        }
    ]
}
```

---

## IDE Setup

### VS Code

**Extensiones recomendadas:**

```json
// .vscode/extensions.json
{
    "recommendations": [
        "ms-python.python",
        "ms-python.vscode-pylance",
        "charliermarsh.ruff",
        "ms-python.mypy-type-checker",
        "tamasfe.even-better-toml",
        "redhat.vscode-yaml"
    ]
}
```

**Settings:**

```json
// .vscode/settings.json
{
    "python.defaultInterpreterPath": "./venv/bin/python",
    "[python]": {
        "editor.formatOnSave": true,
        "editor.defaultFormatter": "charliermarsh.ruff",
        "editor.codeActionsOnSave": {
            "source.fixAll.ruff": "explicit",
            "source.organizeImports.ruff": "explicit"
        }
    },
    "python.analysis.typeCheckingMode": "strict",
    "mypy-type-checker.args": ["--config-file=pyproject.toml"]
}
```

### PyCharm

1. **Interpreter**: Configurar el venv del proyecto
2. **Ruff**: Instalar plugin "Ruff" desde Marketplace
3. **MyPy**: Settings → Tools → Python Integrated Tools → MyPy
4. **Docker**: Configurar Docker integration

---

## Herramientas Útiles

### Comandos Frecuentes

```bash
# Alias útiles (.bashrc / .zshrc)
alias pytest='python -m pytest'
alias lint='ruff check src/ && ruff format src/ --check'
alias typecheck='python scripts/typecheck.py'
alias test='pytest tests/unit/ -v'
alias testcov='pytest --cov=src --cov-report=html && open htmlcov/index.html'

# Todo junto antes de commit
alias precommit='lint && typecheck && test'
```

### Scripts de Desarrollo

```bash
# Resetear base de datos
docker-compose down -v
docker-compose up -d db
sleep 5
alembic upgrade head

# Ver logs en tiempo real
docker-compose logs -f bot

# Entrar al contenedor
docker-compose exec bot bash

# Ejecutar comando en contenedor
docker-compose exec bot python -c "print('hola')"
```

### Monitoreo Local

```bash
# Ver recursos de contenedores
docker stats

# Ver procesos del bot
docker-compose top bot

# Ver conexiones de red
docker-compose exec db netstat -an | grep 5432
```

---

## Recursos

### Documentación Oficial

- [Python Telegram Bot](https://docs.python-telegram-bot.org/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/)
- [Pydantic](https://docs.pydantic.dev/)
- [Alembic](https://alembic.sqlalchemy.org/)

### Guías Internas

- [API Reference](../api/README.md)
- [Arquitectura](../architecture/README.md)
- [Despliegue](../deployment/README.md)
- [n8n Workflows](../../n8n/README.md)

---

## Preguntas Frecuentes

### ¿Cómo agrego un nuevo comando al bot?

1. Crear handler en `src/bot/handlers/`
2. Registrar en `src/bot/main.py`
3. Agregar tests en `tests/unit/`

### ¿Cómo agrego un nuevo endpoint a la API?

1. Crear archivo en `src/api/` o agregar a existente
2. Registrar router en `src/api/app.py`
3. Agregar tests en `tests/integration/`

### ¿Cómo agrego una nueva tabla?

1. Crear modelo en `src/database/models.py`
2. Generar migración: `alembic revision --autogenerate -m "add tabla"`
3. Aplicar: `alembic upgrade head`
4. Crear queries en `src/database/queries/`

### ¿Cómo cambio la configuración por entorno?

1. Modificar `config/environments.py`
2. Agregar variable a `.env.example`
3. Documentar en `docs/deployment/README.md`
