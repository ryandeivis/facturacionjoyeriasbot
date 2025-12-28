# Guía de Contribución

Gracias por tu interés en contribuir a Jewelry Invoice Bot. Esta guía te ayudará a entender cómo participar en el proyecto.

## Tabla de Contenidos

- [Código de Conducta](#código-de-conducta)
- [Cómo Contribuir](#cómo-contribuir)
- [Setup de Desarrollo](#setup-de-desarrollo)
- [Estándares de Código](#estándares-de-código)
- [Convención de Commits](#convención-de-commits)
- [Pull Requests](#pull-requests)
- [Reportar Bugs](#reportar-bugs)
- [Solicitar Features](#solicitar-features)

---

## Código de Conducta

Este proyecto sigue un código de conducta basado en respeto mutuo. Esperamos que todos los contribuidores:

- Sean respetuosos y profesionales
- Acepten críticas constructivas
- Se enfoquen en lo mejor para la comunidad
- Muestren empatía hacia otros miembros

---

## Cómo Contribuir

### 1. Fork del Repositorio

```bash
# Fork en GitHub, luego clonar
git clone https://github.com/TU_USUARIO/facturacionjoyeriasbot.git
cd facturacionjoyeriasbot
```

### 2. Crear Branch

```bash
# Desde main actualizado
git checkout main
git pull origin main

# Crear branch descriptivo
git checkout -b feat/nueva-funcionalidad
# o
git checkout -b fix/descripcion-del-bug
```

### 3. Hacer Cambios

- Seguir los [estándares de código](#estándares-de-código)
- Escribir tests para nuevas funcionalidades
- Actualizar documentación si es necesario

### 4. Commit y Push

```bash
git add .
git commit -m "feat: descripción corta del cambio"
git push origin feat/nueva-funcionalidad
```

### 5. Crear Pull Request

- Ir a GitHub y crear PR hacia `main`
- Llenar el template de PR
- Esperar revisión

---

## Setup de Desarrollo

### Requisitos

- Python 3.11+
- Docker y Docker Compose
- Git

### Instalación Local

```bash
# Clonar repositorio
git clone https://github.com/ryandeivis/facturacionjoyeriasbot.git
cd facturacionjoyeriasbot

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o
.\venv\Scripts\activate   # Windows

# Instalar dependencias
pip install -r requirements.txt

# Copiar configuración
cp .env.example .env
# Editar .env con tus valores

# Iniciar servicios (DB, Redis)
docker-compose up -d db redis

# Ejecutar migraciones
alembic upgrade head

# Iniciar bot (desarrollo)
python -m src.bot.main
```

### Ejecutar Tests

```bash
# Todos los tests
pytest

# Tests unitarios
pytest tests/unit/ -v

# Tests de integración
pytest tests/integration/ -v

# Con coverage
pytest --cov=src --cov-report=html

# Abrir reporte
open htmlcov/index.html
```

---

## Estándares de Código

### Arquitectura

Este proyecto sigue principios de **Clean Code** y arquitectura **modular**:

```
src/
├── api/          # Capa de presentación (REST)
├── bot/          # Capa de presentación (Telegram)
├── services/     # Capa de lógica de negocio
├── database/     # Capa de datos
└── utils/        # Utilidades transversales
```

### Principios

1. **Single Responsibility** - Cada clase/función hace una sola cosa
2. **Dependency Injection** - Dependencias inyectadas, no hardcodeadas
3. **Type Hints** - Todo el código tipado con MyPy estricto
4. **Tests First** - Escribir tests antes o junto con el código

### Linting y Formateo

```bash
# Verificar estilo (Ruff)
ruff check src/

# Formatear código
ruff format src/

# Type checking (MyPy)
python scripts/typecheck.py --mode=strict

# Todo junto
ruff check src/ && ruff format src/ && python scripts/typecheck.py
```

### Reglas de Estilo

| Regla | Valor |
|-------|-------|
| Largo máximo de línea | 100 caracteres |
| Indentación | 4 espacios |
| Quotes | Dobles (`"`) |
| Trailing commas | Sí |
| Imports | Ordenados (isort) |

### Documentación de Código

```python
def create_invoice(
    client_data: ClientData,
    items: list[InvoiceItem],
    *,
    discount: float = 0.0,
) -> Invoice:
    """
    Crea una nueva factura.

    Args:
        client_data: Datos del cliente.
        items: Lista de items de la factura.
        discount: Porcentaje de descuento (0-100).

    Returns:
        Invoice creada con número generado.

    Raises:
        ValidationError: Si los datos son inválidos.
        QuotaExceededError: Si se excede el límite del plan.
    """
    ...
```

---

## Convención de Commits

Seguimos [Conventional Commits](https://www.conventionalcommits.org/):

### Formato

```
<tipo>(<alcance>): <descripción>

[cuerpo opcional]

[footer opcional]
```

### Tipos

| Tipo | Descripción |
|------|-------------|
| `feat` | Nueva funcionalidad |
| `fix` | Corrección de bug |
| `docs` | Solo documentación |
| `style` | Formateo, sin cambios de código |
| `refactor` | Refactorización sin cambio de funcionalidad |
| `test` | Agregar o corregir tests |
| `chore` | Tareas de mantenimiento |
| `perf` | Mejoras de rendimiento |
| `ci` | Cambios en CI/CD |

### Ejemplos

```bash
# Feature
git commit -m "feat(invoice): agregar exportación a Excel"

# Bug fix
git commit -m "fix(auth): corregir validación de token expirado"

# Documentación
git commit -m "docs: actualizar guía de instalación"

# Refactor
git commit -m "refactor(database): extraer queries a módulo separado"

# Breaking change
git commit -m "feat(api)!: cambiar formato de respuesta de errores

BREAKING CHANGE: El campo 'error' ahora es un objeto con 'code' y 'message'"
```

---

## Pull Requests

### Checklist

Antes de crear un PR, verifica:

- [ ] Tests pasan localmente (`pytest`)
- [ ] Linting pasa (`ruff check src/`)
- [ ] Type checking pasa (`python scripts/typecheck.py`)
- [ ] Documentación actualizada si es necesario
- [ ] CHANGELOG.md actualizado (sección Unreleased)
- [ ] Commits siguen la convención

### Template de PR

```markdown
## Descripción

Breve descripción de los cambios.

## Tipo de Cambio

- [ ] Bug fix
- [ ] Nueva funcionalidad
- [ ] Breaking change
- [ ] Documentación

## Cómo Probar

1. Paso 1
2. Paso 2
3. Verificar que...

## Checklist

- [ ] Tests agregados/actualizados
- [ ] Documentación actualizada
- [ ] CHANGELOG actualizado
```

### Revisión

- Al menos 1 aprobación requerida
- CI debe pasar (tests, linting, type check)
- Sin conflictos con main

---

## Reportar Bugs

### Antes de Reportar

1. Verificar que no exista un issue similar
2. Probar con la última versión
3. Recopilar información del error

### Template de Bug

```markdown
## Descripción del Bug

Descripción clara y concisa.

## Pasos para Reproducir

1. Ir a '...'
2. Click en '...'
3. Ver error

## Comportamiento Esperado

Qué debería pasar.

## Screenshots

Si aplica, agregar capturas.

## Entorno

- OS: [ej. Windows 11]
- Python: [ej. 3.11.5]
- Docker: [ej. 24.0.5]
```

---

## Solicitar Features

### Template de Feature Request

```markdown
## Problema

Descripción del problema que resuelve.

## Solución Propuesta

Descripción de la solución.

## Alternativas Consideradas

Otras opciones evaluadas.

## Contexto Adicional

Información extra, mockups, etc.
```

---

## Preguntas

Si tienes dudas:

1. Revisar la [documentación](docs/)
2. Buscar en [issues existentes](https://github.com/ryandeivis/facturacionjoyeriasbot/issues)
3. Crear un issue con la etiqueta `question`

---

Gracias por contribuir.
