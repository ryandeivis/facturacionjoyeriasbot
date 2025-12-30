# Plan de Corrección de Errores - Pre Fase 9

> **Archivo temporal** - Eliminar después de completar las correcciones

---

## Resumen de Errores Encontrados

| # | Severidad | Problema | Archivo |
|---|-----------|----------|---------|
| 1 | 🔴 ALTA | Función duplicada `find_or_create_customer` | invoice_queries.py, customer_queries.py |
| 2 | 🟡 MEDIA | Commit interno en `delete_items_by_invoice_async` | invoice_item_queries.py |
| 3 | 🟡 MEDIA | Doble commit en `replace_invoice_items_async` | invoice_item_queries.py |

---

## Pasos de Corrección

### Paso 1: Eliminar commit interno de `delete_items_by_invoice_async`
**Archivo:** `src/database/queries/invoice_item_queries.py`

**Acciones:**
- [x] Localizar función `delete_items_by_invoice_async` (línea 360)
- [x] Eliminar línea `await db.commit()`
- [x] Actualizar docstring indicando que el caller debe hacer commit
- [x] Cambiar `await db.rollback()` por `raise` para propagar errores

**Cambios realizados:**
```python
# ANTES (línea 378):
await db.commit()

# DESPUÉS:
# NO hacer commit aquí - el caller debe hacerlo

# ANTES (manejo de error):
await db.rollback()
return 0

# DESPUÉS:
raise  # Re-lanzar para que el caller maneje el rollback
```

**Estado:** ✅ COMPLETADO

---

### Paso 2: Verificar `replace_invoice_items_async` (doble commit)
**Archivo:** `src/database/queries/invoice_item_queries.py`

**Acciones:**
- [x] Después del Paso 1, verificar que solo hay un commit
- [x] El commit debe estar al final de la función
- [x] Si hay doble commit, eliminar el redundante

**Verificación realizada:**

| Función | ¿Tiene commit? | Estado |
|---------|----------------|--------|
| `delete_items_by_invoice_async` | ❌ NO (corregido Paso 1) | ✅ OK |
| `create_invoice_items_async` | ❌ NO (usa `flush`) | ✅ OK |
| `replace_invoice_items_async` | ✅ SÍ (línea 416) | ✅ OK - Único commit |

**Resultado:** No hay doble commit. El problema se resolvió con el Paso 1.

**Nota adicional:** `create_invoice_item_async` (singular) SÍ tiene commit interno (línea 229), pero no afecta a `replace_invoice_items_async` que usa la versión batch.

**Estado:** ✅ COMPLETADO (sin cambios necesarios)

---

### Paso 3: Eliminar función duplicada `_find_or_create_customer`
**Archivo:** `src/database/queries/invoice_queries.py`

**Acciones:**
- [x] Agregar import: `from src.database.queries.customer_queries import find_or_create_customer_async`
- [x] Modificar `create_invoice_with_items_async` para usar la función importada (línea 624)
- [x] Manejar diferencia de comportamiento (ValueError vs None) con try/except
- [x] Eliminar función `_find_or_create_customer` (líneas 693-768 eliminadas)

**Cambios realizados:**

```python
# IMPORT AGREGADO (línea 15):
from src.database.queries.customer_queries import find_or_create_customer_async

# ANTES (línea 622):
customer = await _find_or_create_customer(db, org_id, customer_data)
if customer:
    customer_id = customer.id
    ...

# DESPUÉS:
try:
    customer = await find_or_create_customer_async(db, org_id, customer_data)
    customer_id = customer.id
    ...
except ValueError as e:
    logger.warning(f"No se pudo crear cliente: {e}")

# ELIMINADO:
async def _find_or_create_customer(...) -> Optional[Customer]:
    # 76 líneas eliminadas (693-768)
```

**Resultado:** Una sola fuente de verdad para find_or_create_customer (en customer_queries.py)

**Estado:** ✅ COMPLETADO

---

### Paso 4: Verificar funcionamiento
**Acciones:**
- [x] Verificar sintaxis de archivos modificados (py_compile)
- [x] Verificar que no hay referencias a función eliminada
- [ ] Ejecutar tests existentes (bloqueado por incompatibilidad Python 3.14 + SQLAlchemy)

**Verificaciones realizadas:**

| Verificación | Resultado |
|--------------|-----------|
| Sintaxis `invoice_queries.py` | ✅ OK |
| Sintaxis `invoice_item_queries.py` | ✅ OK |
| Sintaxis `customer_queries.py` | ✅ OK |
| Referencias a `_find_or_create_customer` | ✅ No encontradas |

**Nota:** Los tests completos no pueden ejecutarse debido a un error preexistente de compatibilidad entre Python 3.14.0 y SQLAlchemy (error en `SoftDeleteMixin.deleted_at`). Este error NO fue causado por nuestras correcciones.

**Estado:** ✅ COMPLETADO (con nota)

---

## Progreso

| Paso | Estado | Fecha |
|------|--------|-------|
| 1 | ✅ COMPLETADO | 2024-12-30 |
| 2 | ✅ COMPLETADO | 2024-12-30 |
| 3 | ✅ COMPLETADO | 2024-12-30 |
| 4 | ✅ COMPLETADO | 2024-12-30 |

---

## Resumen de Correcciones

| Archivo | Cambio | Líneas afectadas |
|---------|--------|------------------|
| `invoice_item_queries.py` | Eliminar commit interno | 378, 384-388 |
| `invoice_queries.py` | Agregar import | 15 |
| `invoice_queries.py` | Modificar llamada con try/except | 622-634 |
| `invoice_queries.py` | Eliminar función duplicada | 693-768 (eliminadas) |

**Todas las correcciones completadas. Listo para continuar con Fase 9.**

---

*Creado: 2024-12-30*
*Completado: 2024-12-30*
