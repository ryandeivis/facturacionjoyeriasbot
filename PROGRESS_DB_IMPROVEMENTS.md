# Progreso: Mejoras de Base de Datos - jewelry_invoice_bot

> **Archivo de seguimiento temporal** - Actualizar al completar cada fase

---

## Resumen del Plan

| Área | Descripción |
|------|-------------|
| **Normalización** | Tablas `customers`, `invoice_items` |
| **Integridad** | CHECK constraints para montos y enums |
| **Performance** | Índices optimizados para queries frecuentes |
| **Auditoría** | Campos `created_by`, `updated_by`, `version` |
| **Trazabilidad** | Tabla `invoice_drafts` con historial de cambios |
| **Métricas Negocio** | Eventos para joyería (customer.new, product.sold) |

---

## Estado de las Fases

| # | Fase | Estado | Fecha Completado |
|---|------|--------|------------------|
| 1-3 | Modelos (Customer, InvoiceItem, InvoiceDraft + modificar Invoice/Organization/User) | ✅ COMPLETADO | 2024-12-30 |
| 4 | Crear migración Alembic 0002 | ✅ COMPLETADO | 2024-12-30 |
| 5 | Crear customer_queries.py (sync + async) | ✅ COMPLETADO | 2024-12-30 |
| 6 | Crear invoice_item_queries.py (sync + async) | ✅ COMPLETADO | 2024-12-30 |
| 7 | Crear draft_queries.py (sync + async) | ✅ COMPLETADO | 2024-12-30 |
| 8 | Actualizar invoice_queries.py con create_invoice_with_items_async | ✅ COMPLETADO | 2024-12-30 |
| 9 | Actualizar queries/__init__.py con exports | ⬜ PENDIENTE | - |
| 10 | Expandir src/metrics/business.py con métricas de joyería | ⬜ PENDIENTE | - |
| 11 | Crear tests/unit/test_traceability.py | ⬜ PENDIENTE | - |
| 12 | Expandir tests/unit/test_business_metrics.py | ⬜ PENDIENTE | - |
| 13 | Crear tests/integration/test_invoice_flow.py | ⬜ PENDIENTE | - |
| 14 | Ejecutar migración y tests | ⬜ PENDIENTE | - |

**Leyenda:** ✅ Completado | ⏳ En Progreso | ⬜ Pendiente

---

## Detalle por Fase

### Fase 1-3: Modelos ✅

**Archivo modificado:** `src/database/models.py`

**Cambios realizados:**

1. **Modelo `Customer`** (líneas 419-478)
   - Campos: id, organization_id, nombre, cedula, telefono, email, direccion, ciudad, notas
   - Auditoría: created_by, updated_by
   - Índices: org_cedula, org_nombre, org_email
   - Métodos: to_dict()

2. **Modelo `InvoiceItem`** (líneas 481-544)
   - Campos: id, invoice_id, numero, descripcion, cantidad, precio_unitario, subtotal
   - Metadata joyería: material, peso_gramos, tipo_prenda
   - CHECK constraints: cantidad >= 1, precio_unitario >= 0, subtotal >= 0
   - Métodos: to_dict()

3. **Modelo `InvoiceDraft`** (líneas 547-665)
   - Trazabilidad: input_type, input_raw, input_file_path
   - IA: ai_response_raw, ai_extraction_timestamp
   - Datos: items_data, customer_data, totals_data (JSON)
   - Historial: change_history (JSON array)
   - Estados: active, completed, cancelled, expired
   - Métodos: add_change(), to_dict()

4. **Modificaciones a `Organization`** (líneas 74-82)
   - Nuevos campos: created_by, updated_by
   - Nuevas relaciones: customers, invoice_drafts

5. **Modificaciones a `User`** (líneas 143-150)
   - Nuevos campos: created_by, updated_by
   - Nueva relación: invoice_drafts

6. **Modificaciones a `Invoice`** (líneas 178-253)
   - Nuevos campos: customer_id (FK), notas, version, created_by, updated_by
   - Nuevas relaciones: customer, items_rel, drafts
   - Nuevo índice: ix_invoices_org_created, ix_invoices_cliente_cedula
   - CHECK constraints: subtotal >= 0, descuento >= 0, impuesto >= 0, total >= 0, estado válido
   - Nueva propiedad: items_list (lee de items_rel o JSON legacy)

---

### Fase 4: Migración Alembic 0002 ✅

**Archivo creado:** `migrations/versions/20241230_0002_database_improvements.py`

**Tareas completadas:**
- [x] Crear tabla `customers` (con índices: id, org_id, cedula, org_cedula, org_nombre, org_email)
- [x] Crear tabla `invoice_items` (con índices: id, invoice_id, descripcion, material, tipo_prenda)
- [x] Crear tabla `invoice_drafts` (con índices: id, org_id, org_user, chat, status, org_status)
- [x] Crear tabla `metric_events` (con índices para queries de agregación)
- [x] Agregar columnas a `invoices`: customer_id, notas, version, created_by, updated_by, cliente_direccion, cliente_ciudad, cliente_email
- [x] Agregar columnas a `organizations`: created_by, updated_by
- [x] Agregar columnas a `users`: created_by, updated_by
- [x] Crear índices nuevos en `invoices`: ix_invoices_org_created, ix_invoices_cliente_cedula
- [x] CHECK constraints documentados (se aplican a nivel de modelo para SQLite)
- [x] Crear FKs: customer_id -> customers.id

**Estructura de la migración:**
1. Agregar columnas a tablas existentes (organizations, users, invoices)
2. Crear tabla customers
3. Agregar FK customer_id a invoices
4. Crear tabla invoice_items
5. Crear tabla invoice_drafts
6. Crear tabla metric_events
7. Crear índices adicionales
8. Downgrade completo implementado

---

### Fase 5: customer_queries.py ✅

**Archivo creado:** `src/database/queries/customer_queries.py`

**Funciones implementadas:**

Sincrónicas (compatibilidad):
- [x] get_customer_by_cedula
- [x] get_customer_by_id
- [x] get_customer_by_telefono
- [x] create_customer
- [x] search_customers

Asincrónicas (recomendado):
- [x] get_customer_by_cedula_async
- [x] get_customer_by_id_async
- [x] get_customer_by_telefono_async
- [x] create_customer_async
- [x] find_or_create_customer_async (busca por cédula/teléfono o crea)
- [x] update_customer_async
- [x] get_customers_by_org_async
- [x] search_customers_async
- [x] soft_delete_customer_async
- [x] count_customers_async
- [x] get_recent_customers_async

---

### Fase 6: invoice_item_queries.py ✅

**Archivo creado:** `src/database/queries/invoice_item_queries.py`

**Funciones implementadas:**

Sincrónicas (compatibilidad):

- [x] get_item_by_id
- [x] get_items_by_invoice
- [x] create_invoice_item
- [x] create_invoice_items_batch
- [x] delete_items_by_invoice

Asincrónicas (recomendado):

- [x] get_item_by_id_async
- [x] get_items_by_invoice_async
- [x] create_invoice_item_async
- [x] create_invoice_items_async (batch con cálculo automático de subtotal)
- [x] update_item_async
- [x] delete_item_async
- [x] delete_items_by_invoice_async
- [x] replace_invoice_items_async
- [x] count_items_by_invoice_async
- [x] get_invoice_total_from_items_async

Análisis (métricas joyería):

- [x] get_items_by_material_async
- [x] get_items_by_tipo_prenda_async
- [x] get_top_selling_items_async
- [x] get_sales_by_material_async

---

### Fase 7: draft_queries.py ✅

**Archivo creado:** `src/database/queries/draft_queries.py`

**Funciones implementadas:**

Sincrónicas (compatibilidad):

- [x] get_draft_by_id
- [x] get_active_draft_by_chat
- [x] create_draft
- [x] cancel_draft

Asincrónicas (recomendado):

- [x] get_draft_by_id_async
- [x] get_active_draft_async (busca por telegram_chat_id)
- [x] create_draft_async (cancela borradores anteriores automáticamente)
- [x] update_draft_step_async (actualiza paso y registra en historial)
- [x] record_input_async (registra input original del usuario)
- [x] record_ai_extraction_async (registra respuesta IA con timestamp)
- [x] record_user_edit_async (registra ediciones en historial)
- [x] update_draft_data_async (actualiza items/customer/totals)
- [x] finalize_draft_async (vincula a factura final)
- [x] cancel_draft_async
- [x] cancel_draft_by_chat_async
- [x] cleanup_expired_drafts_async (marca expirados en batch)
- [x] get_drafts_by_user_async
- [x] get_drafts_by_org_async
- [x] count_drafts_async
- [x] get_draft_with_history_async (incluye métricas del borrador)

**Constantes definidas:**

- DRAFT_STATUS_ACTIVE, DRAFT_STATUS_COMPLETED, DRAFT_STATUS_CANCELLED, DRAFT_STATUS_EXPIRED
- DEFAULT_EXPIRATION_HOURS = 24

---

### Fase 8: Actualizar invoice_queries.py ✅

**Archivo modificado:** `src/database/queries/invoice_queries.py`

**Funciones agregadas:**

- [x] create_invoice_with_items_async (función principal - crea factura con items normalizados)
- [x] _find_or_create_customer (helper interno - busca/crea cliente)
- [x] get_invoice_with_items_async (obtiene factura con items y cliente)
- [x] update_invoice_with_items_async (actualiza factura y reemplaza items)
- [x] get_invoices_by_customer_async (facturas por cliente)

**Características:**

- Compatibilidad dual: guarda items en tabla normalizada Y en JSON legacy
- Find-or-create de cliente por cédula/teléfono
- Versionado automático en actualizaciones
- Transacción única para factura + items + cliente

---

### Fase 9: Actualizar exports ⬜

**Archivo a modificar:** `src/database/queries/__init__.py`

**Exports a agregar:**
- [ ] customer_queries.*
- [ ] invoice_item_queries.*
- [ ] draft_queries.*

---

### Fase 10: Métricas de negocio ⬜

**Archivo a modificar:** `src/metrics/business.py`

**Funciones a agregar:**
- [ ] track_customer_activity
- [ ] track_product_sale
- [ ] get_top_products
- [ ] get_customer_stats
- [ ] get_seller_performance

---

### Fase 11: test_traceability.py ⬜

**Archivo a crear:** `tests/unit/test_traceability.py`

**Tests a implementar:**
- [ ] test_draft_created_on_flow_start
- [ ] test_ai_extraction_recorded
- [ ] test_user_edit_tracked
- [ ] test_draft_linked_to_final_invoice
- [ ] test_full_flow_traceability

---

### Fase 12: test_business_metrics.py ⬜

**Archivo a expandir:** `tests/unit/test_business_metrics.py`

**Tests a agregar:**
- [ ] test_track_new_customer
- [ ] test_track_product_sale_with_metadata
- [ ] test_get_top_products
- [ ] test_customer_purchase_history

---

### Fase 13: test_invoice_flow.py ⬜

**Archivo a crear:** `tests/integration/test_invoice_flow.py`

**Tests a implementar:**
- [ ] test_full_invoice_flow_with_traceability
- [ ] test_data_consistency_after_edits
- [ ] test_rollback_on_failure

---

### Fase 14: Ejecutar migración y tests ⬜

**Comandos a ejecutar:**
- [ ] `alembic upgrade head`
- [ ] `pytest tests/ -v`
- [ ] Verificar que no hay errores

---

## Esquema Final de Tablas

```
organizations (1) ──┬──> (N) users
                    ├──> (N) customers ──────────┐
                    │                            └──> (N) invoices ──> (N) invoice_items
                    ├──> (N) invoices ───────────────────────────────> (N) invoice_items
                    ├──> (N) invoice_drafts
                    ├──> (N) audit_logs
                    ├──> (N) metric_events
                    └──> (1) tenant_configs
```

---

## Notas

- **Compatibilidad**: El campo `items` (JSON) se mantiene para compatibilidad con facturas existentes
- **Propiedad `items_list`**: Lee de `items_rel` primero, fallback a JSON
- **Campos `cliente_*`**: Se mantienen en Invoice (deprecados gradualmente)
- **`customer_id`**: Nullable para facturas existentes sin cliente vinculado

---

*Última actualización: 2024-12-30 - Fase 8 completada*
