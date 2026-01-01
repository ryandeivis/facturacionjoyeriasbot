# Análisis de Bugs y Problemas - Jewelry Invoice Bot

**Fecha:** 2025-12-31
**Versión:** 1.0
**Autor:** Análisis automatizado con Claude Code

---

## Índice

1. [Resumen Ejecutivo](#resumen-ejecutivo)
2. [Problemas Críticos](#problemas-críticos)
3. [Problemas Altos](#problemas-altos)
4. [Problemas Medios](#problemas-medios)
5. [Problemas Bajos](#problemas-bajos)
6. [Plan de Corrección por Fases](#plan-de-corrección-por-fases)
7. [Análisis de Código Muerto](#análisis-de-código-muerto)
8. [Trazabilidad de Errores](#trazabilidad-de-errores)

---

## Resumen Ejecutivo

| Categoría | Crítico | Alto | Medio | Bajo | Total |
|-----------|---------|------|-------|------|-------|
| **Handler invoice.py** | 4 | 7 | 9 | 5 | **25** |
| **Database queries** | 2 | 13 | 18 | 2 | **35** |
| **Services + Metrics** | 0 | 3 | 10 | 4 | **17** |
| **TOTAL** | **6** | **23** | **37** | **11** | **77** |

### Impacto en Producción

- **Críticos**: Pueden causar pérdida de datos, vulnerabilidades de seguridad, o crashes
- **Altos**: Afectan funcionalidad importante del usuario
- **Medios**: Degradan rendimiento o mantenibilidad
- **Bajos**: Mejoras de código y limpieza

---

## Problemas Críticos

### CRIT-001: Race Condition en Generación de Números de Factura

**Archivo:** `src/database/queries/invoice_queries.py`
**Líneas:** 26-67
**Severidad:** CRÍTICA
**Estado:** Pendiente

**Descripción:**
Dos requests simultáneos pueden obtener el mismo `last_invoice` y generar números de factura duplicados.

**Código Problemático:**
```python
def generate_invoice_number(db: Session, org_id: Optional[str] = None) -> str:
    # ...
    last_invoice = query.order_by(Invoice.numero_factura.desc()).first()

    if last_invoice:
        last_num = int(last_invoice.numero_factura.split("-")[-1])
        new_num = last_num + 1  # ⚠️ RACE CONDITION AQUÍ
    else:
        new_num = 1

    return f"{prefix_pattern}{new_num:04d}"
```

**Impacto:**
- Violación de constraint UNIQUE en base de datos
- Facturas con números duplicados
- Errores 500 para usuarios

**Solución Propuesta:**
```python
async def generate_invoice_number_async(db: AsyncSession, org_id: str) -> str:
    async with db.begin_nested():
        # Usar SELECT FOR UPDATE para lock
        result = await db.execute(
            select(func.max(Invoice.numero_factura))
            .where(
                and_(
                    Invoice.organization_id == org_id,
                    Invoice.numero_factura.like(f"{prefix_pattern}%")
                )
            )
            .with_for_update()
        )
        # ...
```

---

### CRIT-002: Estados de Edición Nunca Registrados (Código Muerto)

**Archivo:** `src/bot/handlers/invoice.py`
**Líneas:** 87-94, 1070-1239
**Severidad:** CRÍTICA
**Estado:** Pendiente

**Descripción:**
5 estados definidos pero NO registrados en el ConversationHandler. Las funciones de edición de items individuales NUNCA se ejecutan.

**Estados Muertos:**
```python
EDITAR_SELECCIONAR_ITEM = InvoiceStates.EDITAR_SELECCIONAR_ITEM  # MUERTO
EDITAR_ITEM_CAMPO = InvoiceStates.EDITAR_ITEM_CAMPO              # MUERTO
AGREGAR_ITEM = InvoiceStates.AGREGAR_ITEM                        # MUERTO
AGREGAR_ITEM_CANTIDAD = InvoiceStates.AGREGAR_ITEM_CANTIDAD      # MUERTO
AGREGAR_ITEM_PRECIO = InvoiceStates.AGREGAR_ITEM_PRECIO          # MUERTO
```

**Funciones Afectadas (~170 líneas de código muerto):**
| Función | Línea | Propósito Original |
|---------|-------|-------------------|
| `editar_item_nombre()` | 1070 | Editar nombre de item individual |
| `editar_item_cantidad()` | 1097 | Editar cantidad de item |
| `editar_item_precio()` | 1128 | Editar precio de item |
| `agregar_item_nombre()` | 1152 | Agregar nuevo item (nombre) |
| `agregar_item_cantidad()` | 1174 | Agregar nuevo item (cantidad) |
| `agregar_item_precio()` | 1206 | Agregar nuevo item (precio) |
| `editar_cliente_campo()` | 1242 | Editar campo específico de cliente |

**Impacto:**
- El usuario NO puede editar items individuales
- Solo puede usar modo bulk (editar_items)
- UX degradada

**Solución Propuesta:**
Agregar estados al ConversationHandler en línea ~1514:
```python
states={
    # ... estados existentes ...
    EDITAR_SELECCIONAR_ITEM: [MessageHandler(filters.TEXT, editar_item_seleccionar)],
    EDITAR_ITEM_CAMPO: [MessageHandler(filters.TEXT, editar_item_campo)],
    AGREGAR_ITEM: [MessageHandler(filters.TEXT, agregar_item_nombre)],
    AGREGAR_ITEM_CANTIDAD: [MessageHandler(filters.TEXT, agregar_item_cantidad)],
    AGREGAR_ITEM_PRECIO: [MessageHandler(filters.TEXT, agregar_item_precio)],
}
```

---

### CRIT-003: Variables cliente_telefono y cliente_cedula Nunca Pobladas

**Archivo:** `src/bot/handlers/invoice.py`
**Líneas:** 745-746
**Severidad:** CRÍTICA
**Estado:** Pendiente

**Descripción:**
Se accede a `context.user_data.get('cliente_telefono')` y `context.user_data.get('cliente_cedula')` pero estos valores NUNCA se establecen en ninguna parte del flujo.

**Código Problemático:**
```python
invoice_data = {
    # ...
    "cliente_telefono": context.user_data.get('cliente_telefono'),  # Siempre None
    "cliente_cedula": context.user_data.get('cliente_cedula'),      # Siempre None
    # ...
}
```

**Análisis del Flujo Actual:**
```
datos_cliente() → cliente_direccion() → cliente_ciudad() → cliente_email() → resumen
                                                                    ↑
                                                          Falta: cliente_telefono()
                                                          Falta: cliente_cedula()
```

**Impacto:**
- TODAS las facturas tienen teléfono y cédula del cliente como NULL
- Datos incompletos en base de datos
- Reportes de clientes sin información de contacto

**Solución Propuesta:**
Agregar dos pasos adicionales al flujo después de `cliente_email()`:
```python
async def cliente_telefono(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Captura teléfono del cliente."""
    telefono = update.message.text.strip()
    if telefono.lower() != 'omitir':
        context.user_data['cliente_telefono'] = telefono
    return CLIENTE_CEDULA

async def cliente_cedula(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Captura cédula del cliente."""
    cedula = update.message.text.strip()
    if cedula.lower() != 'omitir':
        context.user_data['cliente_cedula'] = cedula
    return await _mostrar_resumen_factura(update, context)
```

---

### CRIT-004: Conexión BD No Se Cierra Si Hay Excepción

**Archivo:** `src/bot/handlers/invoice.py`
**Líneas:** 729-760
**Severidad:** CRÍTICA
**Estado:** Pendiente

**Descripción:**
La conexión de base de datos se obtiene con `next(get_db())` pero no se cierra si ocurre una excepción.

**Código Problemático:**
```python
db = next(get_db())
org_id = context.user_data.get('organization_id')

# ... código que puede fallar ...

invoice = create_invoice(db, invoice_data)
db.close()  # ⚠️ Solo cierra si no hay excepciones
```

**Impacto:**
- Connection leak
- Agotamiento del pool de conexiones
- Errores "too many connections"
- Degradación progresiva del sistema

**Solución Propuesta:**
```python
db = next(get_db())
try:
    org_id = context.user_data.get('organization_id')
    # ... código ...
    invoice = create_invoice(db, invoice_data)
finally:
    db.close()
```

O mejor, usar context manager:
```python
with get_db_context() as db:
    invoice = create_invoice(db, invoice_data)
```

---

### CRIT-005: Acceso Cross-Tenant a Items (Vulnerabilidad de Seguridad)

**Archivo:** `src/database/queries/invoice_item_queries.py`
**Línea:** 24
**Severidad:** CRÍTICA (Seguridad)
**Estado:** Pendiente

**Descripción:**
La función `get_item_by_id()` no valida `organization_id`, permitiendo que un tenant acceda a items de otro tenant.

**Código Vulnerable:**
```python
def get_item_by_id(db: Session, item_id: int) -> Optional[InvoiceItem]:
    return db.query(InvoiceItem).filter(InvoiceItem.id == item_id).first()
    # ⚠️ No valida organización - VULNERABILIDAD MULTI-TENANT
```

**Impacto:**
- Un usuario puede ver items de facturas de otras organizaciones
- Violación de aislamiento de datos
- Potencial fuga de información sensible

**Solución Propuesta:**
```python
def get_item_by_id(db: Session, item_id: int, org_id: str) -> Optional[InvoiceItem]:
    return db.query(InvoiceItem)\
        .join(Invoice)\
        .filter(
            and_(
                InvoiceItem.id == item_id,
                Invoice.organization_id == org_id
            )
        ).first()
```

---

### CRIT-006: Race Condition en find_or_create_customer

**Archivo:** `src/database/queries/customer_queries.py`
**Líneas:** 271-319
**Severidad:** CRÍTICA
**Estado:** Pendiente

**Descripción:**
Patrón check-then-act sin transacción atómica. Dos requests pueden crear el mismo cliente simultáneamente.

**Código Problemático:**
```python
async def find_or_create_customer_async(db, org_id, customer_data):
    cedula = customer_data.get('cedula')
    if cedula:
        customer = await get_customer_by_cedula_async(db, cedula, org_id)
        if customer:
            return customer

    # ⚠️ RACE CONDITION: Otro thread puede crear el mismo cliente aquí

    customer = await create_customer_async(db, customer_data)
    return customer
```

**Impacto:**
- Clientes duplicados en base de datos
- Violación de constraint UNIQUE (si existe)
- Datos inconsistentes

**Solución Propuesta:**
```python
async def find_or_create_customer_async(db, org_id, customer_data):
    try:
        async with db.begin_nested():
            customer = Customer(**customer_data)
            db.add(customer)
            await db.flush()
        await db.commit()
        return customer
    except IntegrityError:
        await db.rollback()
        # Ya existe, buscar
        return await get_customer_by_cedula_async(db, cedula, org_id)
```

---

## Problemas Altos

### Handler invoice.py (7 problemas)

| ID | Línea | Problema | Impacto |
|----|-------|----------|---------|
| HIGH-001 | 418-423 | InlineKeyboard enviado pero handler espera MessageHandler(TEXT) | Botones no funcionan |
| HIGH-002 | 478-479 | Handler espera texto pero interfaz tiene callbacks | UX rota |
| HIGH-003 | 799-801 | No se valida resultado de envío de PDF | Usuario no sabe si PDF falló |
| HIGH-004 | 79-80 | Estados CLIENTE_TELEFONO/CEDULA definidos pero nunca usados | Código muerto |
| HIGH-005 | 429 | Fallback a modo manual incorrecto (vuelve a RECIBIR_INPUT) | Loop infinito potencial |
| HIGH-006 | 345-355 | context.user_data sin sincronización entre usuarios | Data corruption posible |
| HIGH-007 | 730 | get_db() puede no ser thread-safe | Race condition |

### Database Queries (13 problemas)

| ID | Archivo:Línea | Problema |
|----|---------------|----------|
| HIGH-008 | invoice_queries.py:249 | LIKE pattern sin escapar caracteres SQL |
| HIGH-009 | customer_queries.py:140 | Wildcard injection en ILIKE |
| HIGH-010 | metrics_queries.py:90-108 | Falta índice compuesto (org_id, event_type, created_at) |
| HIGH-011 | invoice_queries.py:52-59 | LIKE con wildcard no usa índice |
| HIGH-012 | invoice_queries.py:703-751 | N+1 query en get_invoice_with_items |
| HIGH-013 | invoice_item_queries.py:470 | N+1 en acceso a invoice desde items |
| HIGH-014 | invoice_queries.py:558-700 | Flush sin commit protegido |
| HIGH-015 | invoice_item_queries.py:84-128 | Transacción no atómica en batch create |
| HIGH-016 | draft_queries.py:204-260 | Race condition en cancelar borrador anterior |
| HIGH-017 | invoice_item_queries.py:391-421 | Replace items sin lock en invoice |
| HIGH-018 | customer_queries.py:48 | Campo nullable pero queries asumen presencia |
| HIGH-019 | invoice_queries.py:244 | numero_factura sin validación de formato |
| HIGH-020 | metrics_queries.py:253 | SQLite-specific syntax, incompatible con PostgreSQL |

### Services + Metrics (3 problemas)

| ID | Archivo:Línea | Problema |
|----|---------------|----------|
| HIGH-021 | n8n_service.py:254-263 | Timeout sin reintentos en send_pdf_to_telegram |
| HIGH-022 | n8n_service.py:321-371 | ResilientHTTPClient no se usa en métodos principales |
| HIGH-023 | collectors.py:274,330 | Memory leak en self._events list |

---

## Problemas Medios

### Validaciones Faltantes (4)
- `invoice.py:197` - Sin validación de texto vacío (solo espacios)
- `invoice.py:735` - subtotal no validado como número
- `invoice.py:551,555` - Parsing de precio débil
- `invoice.py:567` - Key inconsistente ('descripcion' vs 'nombre')

### Manejo de Errores Incompleto (4)
- `invoice.py:985` - Import dentro de excepción
- `invoice.py:1010-1012` - Excepciones silenciosas en descarga PDF
- `n8n_service.py:330-346` - Validación de JSON incompleta
- `n8n_service.py:434` - JSONDecodeError no capturado

### Memory Leaks y Threading (5)
- `collectors.py:354-366` - Eventos perdidos sin confirmación de BD
- `collectors.py:284,339` - Contadores nunca se resetean
- `collectors.py:448` - cleanup_old_events() nunca se llama
- `aggregators.py:145` - _aggregations crece sin límite
- `collectors.py:28` - _db_persistence_enabled sin sincronización

### Código Duplicado (2)
- `n8n_service.py:330-346 vs 433-445` - Validación de respuestas duplicada
- `tracker.py:189-226` - Evento AI_EXTRACTION registrado dos veces

### Funciones No Usadas (6)
- `invoice_queries.py:102` - get_invoices_by_vendedor()
- `customer_queries.py:73` - get_customer_by_telefono() sync
- `user_queries.py:45` - get_user_by_telegram_id() sync
- `user_queries.py:66` - update_last_login() sync
- `metrics_queries.py:70` - get_recent_events() sync
- `metrics_queries.py:230` - get_hourly_distribution()

### Archivos Temporales (3)
- `invoice.py:962-975` - HTML no se elimina si send_document falla
- `invoice.py:993-1006` - PDF temporal no se limpia en error
- `invoice.py:1419-1436` - Test HTML sin cleanup

---

## Problemas Bajos

- Imports no usados o mal ubicados
- ThreadPoolExecutor sin shutdown()
- Validaciones de operation_name silenciosas
- Comentarios desactualizados

---

## Plan de Corrección por Fases

### FASE 1: Críticos de Seguridad y Estabilidad
**Duración estimada:** Prioridad inmediata
**Objetivo:** Eliminar vulnerabilidades y crashes potenciales

#### Sub-fase 1.1: Seguridad Multi-Tenant
- [ ] CRIT-005: Agregar validación org_id en todas las queries de items
- [ ] Auditar otras queries por mismo problema

#### Sub-fase 1.2: Race Conditions
- [ ] CRIT-001: Implementar lock en generate_invoice_number()
- [ ] CRIT-006: Implementar upsert atómico para clientes

#### Sub-fase 1.3: Connection Leaks
- [ ] CRIT-004: Agregar try-finally en todas las conexiones BD
- [ ] Crear context manager reutilizable

---

### FASE 2: Funcionalidad Rota
**Duración estimada:** Alta prioridad
**Objetivo:** Restaurar funcionalidad que nunca funcionó

#### Sub-fase 2.1: Flujo de Datos del Cliente
- [ ] CRIT-003: Agregar estados CLIENTE_TELEFONO y CLIENTE_CEDULA
- [ ] Actualizar flujo en ConversationHandler
- [ ] Migrar datos existentes (script)

#### Sub-fase 2.2: Edición de Items
- [ ] CRIT-002: Registrar estados de edición en ConversationHandler
- [ ] Verificar que funciones existentes funcionan
- [ ] Agregar tests

#### Sub-fase 2.3: Handlers y Callbacks
- [ ] HIGH-001, HIGH-002: Corregir InlineKeyboard vs MessageHandler
- [ ] Implementar CallbackQueryHandler donde corresponda

---

### FASE 3: Rendimiento y Estabilidad
**Duración estimada:** Prioridad media
**Objetivo:** Mejorar rendimiento y prevenir degradación

#### Sub-fase 3.1: Queries de Base de Datos
- [ ] HIGH-010: Agregar índices compuestos
- [ ] HIGH-012, HIGH-013: Implementar eager loading
- [ ] HIGH-011: Optimizar queries LIKE

#### Sub-fase 3.2: Memory Leaks
- [ ] HIGH-023: Limitar tamaño de _events
- [ ] MED: Implementar cleanup automático de métricas
- [ ] MED: Agregar reset de contadores

#### Sub-fase 3.3: HTTP Client
- [ ] HIGH-021, HIGH-022: Usar ResilientHTTPClient en todos los métodos

---

### FASE 4: Limpieza y Mantenibilidad
**Duración estimada:** Prioridad baja
**Objetivo:** Código más limpio y mantenible

#### Sub-fase 4.1: Código Muerto
- [ ] Eliminar funciones sync no usadas
- [ ] Eliminar imports no usados
- [ ] Documentar decisiones

#### Sub-fase 4.2: Validaciones
- [ ] Centralizar validaciones de entrada
- [ ] Agregar validación de tipos

#### Sub-fase 4.3: Archivos Temporales
- [ ] Agregar try-finally para limpieza
- [ ] Usar tempfile correctamente

---

## Análisis de Código Muerto

### Código Muerto Confirmado

| Función | Archivo | Líneas | Propósito Original | ¿Por qué está muerto? |
|---------|---------|--------|--------------------|-----------------------|
| `editar_item_nombre()` | invoice.py | 1070-1095 | Editar nombre de item individual | Estado no registrado en ConversationHandler |
| `editar_item_cantidad()` | invoice.py | 1097-1126 | Editar cantidad de item | Estado no registrado |
| `editar_item_precio()` | invoice.py | 1128-1150 | Editar precio de item | Estado no registrado |
| `agregar_item_nombre()` | invoice.py | 1152-1172 | Paso 1 de agregar item | Estado no registrado |
| `agregar_item_cantidad()` | invoice.py | 1174-1204 | Paso 2 de agregar item | Estado no registrado |
| `agregar_item_precio()` | invoice.py | 1206-1240 | Paso 3 de agregar item | Estado no registrado |
| `editar_cliente_campo()` | invoice.py | 1242-1300 | Editar campo específico de cliente | Estado no registrado |

### Código Potencialmente Muerto (Requiere Verificación)

| Función | Archivo | Propósito | Verificar Uso |
|---------|---------|-----------|---------------|
| `get_invoices_by_vendedor()` | invoice_queries.py | Listar facturas por vendedor | Buscar llamadas |
| `get_customer_by_telefono()` | customer_queries.py | Buscar cliente por teléfono | Buscar llamadas |
| `get_user_by_telegram_id()` | user_queries.py | Buscar usuario por ID Telegram | Buscar llamadas |
| `update_last_login()` | user_queries.py | Actualizar último login | Buscar llamadas |
| `get_recent_events()` | metrics_queries.py | Obtener eventos recientes | Buscar llamadas |
| `get_hourly_distribution()` | metrics_queries.py | Distribución por hora | Buscar llamadas |

---

## Trazabilidad de Errores

### Matriz de Dependencias de Errores

```
CRIT-001 (Race condition facturas)
    └─► Puede causar: Violación UNIQUE, Error 500
    └─► Afectado por: Alto volumen de usuarios simultáneos

CRIT-002 (Estados no registrados)
    └─► Causa: Funciones muertas (líneas 1070-1300)
    └─► Afecta: UX de edición de items
    └─► Relacionado: HIGH-001, HIGH-002 (handlers/callbacks)

CRIT-003 (Variables nunca pobladas)
    └─► Causa: Flujo incompleto
    └─► Afecta: Datos NULL en BD
    └─► Relacionado: HIGH-004 (estados no usados)

CRIT-004 (Connection leak)
    └─► Puede causar: Agotamiento pool, crashes
    └─► Afecta: Todo el sistema

CRIT-005 (Cross-tenant)
    └─► Severidad: Vulnerabilidad de seguridad
    └─► Afecta: Aislamiento de datos

CRIT-006 (Race condition clientes)
    └─► Puede causar: Duplicados
    └─► Afecta: Integridad de datos
```

### Flujo de Impacto

```
Usuario inicia factura
        │
        ▼
    ¿Input OK? ──NO──► n8n extrae datos
        │                    │
        │                    ▼
        │              ¿Extracción OK?
        │                    │
        │         ┌────YES───┴───NO────┐
        │         │                    │
        │         ▼                    ▼
        │    Mostrar datos        Modo manual
        │         │                    │
        │         ▼                    │
        │    ¿Editar items? ◄──────────┘
        │         │
        │    ┌────┴────┐
        │    │         │
        │    ▼         ▼
        │  Editar    Continuar
        │  (ROTO)        │
        │    ⚠️          │
        │  CRIT-002      │
        │                ▼
        │         Datos cliente
        │                │
        │         ┌──────┴──────┐
        │         │             │
        │         ▼             ▼
        │    Teléfono      Email (actual)
        │    (FALTA)            │
        │      ⚠️               │
        │    CRIT-003           │
        │                       ▼
        │                  Generar factura
        │                       │
        │              ┌────────┴────────┐
        │              │                 │
        │              ▼                 ▼
        │         get_db()          create_invoice
        │         (LEAK)                 │
        │           ⚠️                   │
        │         CRIT-004               │
        │                                ▼
        │                      generate_number()
        │                         (RACE)
        │                           ⚠️
        │                         CRIT-001
        │                                │
        │                                ▼
        │                      find_or_create_customer()
        │                              (RACE)
        │                                ⚠️
        │                              CRIT-006
        │                                │
        └────────────────────────────────┘
```

---

## Recomendaciones Finales

1. **Prioridad Inmediata:** CRIT-005 (seguridad) y CRIT-004 (estabilidad)
2. **Esta Semana:** CRIT-001, CRIT-006 (race conditions)
3. **Próxima Semana:** CRIT-002, CRIT-003 (funcionalidad rota)
4. **Continuo:** Problemas HIGH y MEDIUM según disponibilidad

### Métricas de Seguimiento

- [ ] Número de errores 500 (antes/después)
- [ ] Conexiones de BD activas (monitorear leak)
- [ ] Facturas con datos NULL (cliente_telefono, cliente_cedula)
- [ ] Tiempo de respuesta de queries (después de índices)

---

## Análisis de Código Mediante Ejecución de Ejemplos

### ¿Se puede determinar qué código se usa ejecutando ejemplos?

**Respuesta: SÍ, es posible y altamente recomendable.**

Ejecutar 5-10 flujos completos con trazado de código (code tracing/profiling) permite:

1. **Confirmar código muerto** - El código que nunca se ejecuta en ningún flujo es definitivamente muerto
2. **Identificar código parcialmente usado** - Funciones que solo se ejecutan en casos específicos
3. **Medir cobertura real** - Porcentaje exacto de líneas ejecutadas vs no ejecutadas
4. **Detectar caminos inesperados** - Flujos que no deberían ocurrir pero ocurren

### Metodología Propuesta

#### Paso 1: Instrumentar el Código

```python
# Agregar decorador de tracing a funciones clave
import functools
import logging

executed_functions = set()

def trace_execution(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        executed_functions.add(f"{func.__module__}.{func.__name__}")
        logging.info(f"TRACE: {func.__name__} ejecutada")
        return await func(*args, **kwargs)
    return wrapper
```

#### Paso 2: Escenarios de Prueba (5-10 ejemplos)

| # | Escenario | Input | Flujo Esperado |
|---|-----------|-------|----------------|
| 1 | Factura por texto simple | "1 anillo oro 2500000" | Texto → Parser local → Confirmar → Cliente → Generar |
| 2 | Factura por voz | Audio .ogg | Voz → n8n Whisper → GPT-4 → Confirmar → Cliente → Generar |
| 3 | Factura por foto | Imagen .jpg | Foto → n8n Vision → GPT-4 → Confirmar → Cliente → Generar |
| 4 | Editar items (modo bulk) | Seleccionar "Editar" | Editar → Modificar lista → Confirmar |
| 5 | Editar item individual | Seleccionar item #1 | ⚠️ **Debería fallar** - código muerto |
| 6 | Agregar item nuevo | Botón "Agregar item" | ⚠️ **Debería fallar** - código muerto |
| 7 | Cliente con cédula | Ingresar cédula | ⚠️ **Nunca se pide** - campo faltante |
| 8 | Factura con descuento | Aplicar 10% descuento | Verificar flujo descuento |
| 9 | Cancelar factura | Botón "Cancelar" | Verificar limpieza de estado |
| 10 | Error de n8n | Timeout o error 500 | Verificar fallback a modo manual |

#### Paso 3: Herramientas de Coverage

```bash
# Ejecutar con coverage.py
pip install coverage

# Ejecutar bot con tracing
coverage run --source=src main.py

# Generar reporte HTML
coverage html

# Ver reporte
open htmlcov/index.html
```

#### Paso 4: Resultados Esperados

Después de ejecutar los 10 escenarios, obtendremos:

| Archivo | Cobertura Esperada | Código Muerto Confirmado |
|---------|-------------------|--------------------------|
| invoice.py | ~75% | Líneas 1070-1300 (edición individual) |
| invoice_queries.py | ~60% | get_invoices_by_vendedor() |
| customer_queries.py | ~70% | get_customer_by_telefono() sync |
| metrics_queries.py | ~50% | get_hourly_distribution() |

### ¿Por qué existe el código muerto?

Basado en el análisis del código, hay 3 razones principales:

#### 1. Funcionalidad Planeada Pero No Conectada
**Ejemplo:** `editar_item_nombre()`, `agregar_item_precio()`

Estas funciones fueron escritas como parte de una feature de "edición granular de items", pero el desarrollador:
- Escribió las funciones
- **Olvidó registrar los estados** en el ConversationHandler
- El código nunca fue probado porque los estados nunca transicionan hacia él

```python
# El estado existe pero no está registrado
EDITAR_SELECCIONAR_ITEM = InvoiceStates.EDITAR_SELECCIONAR_ITEM

# La función existe pero nunca se llama
async def editar_item_nombre(update, context):
    # ... 25 líneas de código que nunca se ejecutan ...
```

#### 2. Migración de Sync a Async Incompleta
**Ejemplo:** `get_customer_by_telefono()` sync vs `get_customer_by_telefono_async()`

El proyecto migró de operaciones síncronas a asíncronas, pero:
- Se crearon versiones async de las funciones
- Las versiones sync quedaron "por compatibilidad"
- Nadie las usa porque todo el código nuevo usa async

```python
# Versión sync - MUERTA
def get_customer_by_telefono(db, telefono, org_id):
    return db.query(Customer).filter(...).first()

# Versión async - USADA
async def get_customer_by_telefono_async(db, telefono, org_id):
    result = await db.execute(select(Customer).where(...))
    return result.scalar_one_or_none()
```

#### 3. Features de Métricas Avanzadas No Implementadas
**Ejemplo:** `get_hourly_distribution()`

Funciones de analytics avanzados que fueron escritas anticipando un dashboard que nunca se construyó:

```python
# Escrita para un dashboard que no existe
async def get_hourly_distribution(db, org_id, event_type, days):
    # Distribución por hora del día
    # Útil para dashboard, pero no hay dashboard
    ...
```

### Tabla de Código Muerto con Propósito Original

| Función | Propósito Original | ¿Por qué murió? | ¿Debería revivir? |
|---------|-------------------|-----------------|-------------------|
| `editar_item_nombre()` | UX granular de edición | Estado no registrado | ✅ SÍ - mejora UX |
| `editar_item_cantidad()` | UX granular de edición | Estado no registrado | ✅ SÍ - mejora UX |
| `editar_item_precio()` | UX granular de edición | Estado no registrado | ✅ SÍ - mejora UX |
| `agregar_item_nombre()` | Agregar items uno a uno | Estado no registrado | ✅ SÍ - mejora UX |
| `agregar_item_cantidad()` | Agregar items uno a uno | Estado no registrado | ✅ SÍ - mejora UX |
| `agregar_item_precio()` | Agregar items uno a uno | Estado no registrado | ✅ SÍ - mejora UX |
| `editar_cliente_campo()` | Editar campos individuales | Estado no registrado | ⚠️ QUIZÁS - evaluar |
| `get_invoices_by_vendedor()` | Listar facturas por vendedor | Sin llamada en código | ❓ REVISAR - puede ser útil |
| `get_customer_by_telefono()` | Buscar por teléfono (sync) | Reemplazada por async | ❌ NO - eliminar |
| `get_user_by_telegram_id()` | Buscar usuario (sync) | Reemplazada por async | ❌ NO - eliminar |
| `update_last_login()` | Tracking login (sync) | Reemplazada por async | ❌ NO - eliminar |
| `get_recent_events()` | Métricas recientes (sync) | Reemplazada por async | ❌ NO - eliminar |
| `get_hourly_distribution()` | Analytics por hora | Dashboard no existe | ⚠️ CONSERVAR - futuro |

### Conclusión

**Ejecutar 5-10 ejemplos con coverage.py** nos dará:

1. ✅ **Confirmación definitiva** de qué código nunca se ejecuta
2. ✅ **Porcentaje exacto** de cobertura por archivo
3. ✅ **Lista de funciones** que se pueden eliminar con seguridad
4. ✅ **Identificación de bugs** donde el código debería ejecutarse pero no lo hace

**Recomendación:** Antes de eliminar cualquier código muerto, ejecutar los 10 escenarios de prueba con coverage para tener certeza absoluta.

---

*Documento generado automáticamente. Revisar y validar cada hallazgo antes de implementar correcciones.*
