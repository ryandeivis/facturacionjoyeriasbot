# Plan de 20 Mejoras para Producción y Escalabilidad

## Resumen de Estado

| Fase | Mejoras | Estado |
|------|---------|--------|
| Fase 1: Críticas | 1-4 | ✅ Completadas |
| Fase 2: Alta Prioridad | 5-9 | ✅ Completadas |
| Fase 3: Media Prioridad | 10-14 | 10-12 ✅ / 13-14 ⏳ Pendientes |
| Fase 4: Deuda Técnica | 15-18 | ⏳ Pendientes |
| Opcionales | A-B | 🔮 Evaluar después |

---

## 🚨 FASE 1: CRÍTICAS (Acción Inmediata)

### Mejora 1: Revocar Token Telegram Expuesto ✅
- **Problema:** El archivo `.env` estaba versionado con tokens reales
- **Solución:** Token revocado y regenerado
- **Estado:** Completado

### Mejora 2: Configurar .gitignore para .env ✅
- **Problema:** Archivos sensibles versionados
- **Solución:** `.env` agregado a `.gitignore`
- **Estado:** Completado

### Mejora 3: Implementar Gestión de Secrets ✅
- **Problema:** No había integración con secrets manager
- **Solución:** Sistema de configuración segura implementado
- **Estado:** Completado

### Mejora 4: Corregir CORS en API ✅
- **Problema:** `allow_origins=["*"]` permitía cualquier origen
- **Solución:** Orígenes específicos configurados por entorno
- **Archivo:** `src/api/app.py`
- **Estado:** Completado

---

## 🔴 FASE 2: ALTA PRIORIDAD

### Mejora 5: Dividir invoice.py en Módulos ✅
- **Problema:** Archivo de 1363 líneas, difícil de mantener
- **Solución:** Dividido en:
  - `invoice_create.py` - Creación de facturas
  - `invoice_edit.py` - Edición de items/cliente
  - `invoice_export.py` - Generación PDF/HTML
  - `invoice_list.py` - Listado y búsqueda
- **Estado:** Completado

### Mejora 6: Implementar Redis para Caching ✅
- **Problema:** Cada request consultaba la DB
- **Solución:** Sistema de caché con Redis implementado
  - Config de tenant (30 min)
  - Usuarios autenticados (15 min)
- **Archivo:** `src/cache/`
- **Estado:** Completado

### Mejora 7: Rate Limiting Distribuido con Redis ✅
- **Problema:** Rate limiting solo en memoria local
```python
self._requests: Dict[int, list] = defaultdict(list)  # Solo en memoria
```
- **Solución:** Rate limiting con Redis para múltiples instancias
- **Archivo:** `src/bot/middleware/rate_limit.py`
- **Estado:** Completado

### Mejora 8: Circuit Breaker para Base de Datos ✅
- **Problema:** Cuando la DB caía, todas las requests fallaban sin retry
- **Solución:** Circuit breaker pattern implementado
- **Estado:** Completado

### Mejora 9: Validar Coverage Mínimo en CI ✅
- **Problema:** pytest generaba reporte pero no fallaba si era bajo
- **Solución:** `--cov-fail-under=80` configurado
- **Estado:** Completado

---

## 🟡 FASE 3: MEDIA PRIORIDAD

### Mejora 10: Agregar Índices de DB Faltantes ✅
- **Problema:** Faltan índices compuestos para queries comunes
- **Solución:** Índices agregados:
```python
Index('ix_invoices_org_created', 'organization_id', 'created_at')
Index('ix_invoices_org_deleted', 'organization_id', 'is_deleted')
```
- **Archivo:** `src/database/models.py`
- **Estado:** Completado

### Mejora 11: Aumentar Pool de Conexiones ✅
- **Problema:** Pool muy pequeño para producción
```python
DATABASE_POOL_SIZE = 20  # Insuficiente
```
- **Solución:** Pool optimizado por entorno:
  - Desarrollo: 5 base + 10 overflow = 15 máximo
  - Staging: 15 base + 15 overflow = 30 máximo
  - Producción: 30 base + 20 overflow = 50 máximo
- **Parámetros agregados:**
  - `DATABASE_POOL_TIMEOUT`: 30s máximo de espera
  - `DATABASE_POOL_RECYCLE`: 1800s (30 min) para evitar stale
  - `DATABASE_POOL_PRE_PING`: True para verificar conexiones
- **Archivos modificados:**
  - `config/settings.py`
  - `config/environments.py`
  - `src/database/connection.py`
- **Tests:** `tests/unit/test_database_pool.py` (17 tests)
- **Estado:** ✅ COMPLETADO

### Mejora 12: Health Check HTTP en Docker ✅
- **Problema:** Health check ineficiente
```dockerfile
HEALTHCHECK CMD python -c "import ..."  # Importa módulos cada vez (~1s)
```
- **Solución:** Usar endpoint HTTP `/health/live` con curl (~20ms)
```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl --fail --silent --max-time 5 http://localhost:8000/health/live || exit 1
```
- **Beneficios:**
  - 50x más rápido (~20ms vs ~1000ms)
  - Verifica que el servidor HTTP responde
  - Menor uso de CPU/memoria
- **Archivos modificados:**
  - `Dockerfile` - HEALTHCHECK actualizado
  - `docker-compose.yml` - healthcheck agregado al servicio bot
- **Estado:** ✅ COMPLETADO

### Mejora 13: Activar MyPy Estricto en CI ⏳
- **Problema:** MyPy ignorado en CI
```bash
mypy src/ || true  # El || true permite errores
```
- **Solución:** Remover `|| true` y corregir errores de tipos
- **Estado:** PENDIENTE

### Mejora 14: Upper Bounds en Dependencias ⏳
- **Problema:** Dependencias sin límite superior
```
python-telegram-bot>=22.0  # Debería ser >=22.0,<23.0
```
- **Solución:** Agregar upper bounds a todas las dependencias
- **Archivo:** `requirements.txt`
- **Estado:** PENDIENTE

---

## 🟢 FASE 4: DEUDA TÉCNICA

### Mejora 15: Factory Pattern para Tests ⏳
- **Problema:** Fixtures complejos y repetitivos
- **Solución:** Implementar factory-boy
```python
class InvoiceFactory(Factory):
    class Meta:
        model = Invoice
```
- **Estado:** PENDIENTE

### Mejora 16: Staging Environment ⏳
- **Problema:** Deploy directo a producción
- **Solución:** Crear ambiente de staging
- **Estado:** PENDIENTE

### Mejora 17: Load Testing con Locust ⏳
- **Problema:** Sin pruebas de carga
- **Solución:** Implementar tests con Locust
```bash
pip install locust
# Crear tests/load/load_test.py
```
- **Estado:** PENDIENTE

### Mejora 18: Límites de Recursos en Docker ⏳
- **Problema:** Sin límites de CPU/memoria
- **Solución:** Agregar limits en docker-compose
```yaml
deploy:
  resources:
    limits:
      cpus: '0.5'
      memory: 512M
```
- **Archivo:** `docker-compose.yml`
- **Estado:** PENDIENTE

---

## 📋 Plan de Acción

| Fase | Prioridad | Tareas |
|------|-----------|--------|
| Fase 1 | Inmediato | ✅ Revocar tokens, secrets manager, CORS |
| Fase 2 | 1 sprint | ✅ Redis, dividir invoice.py, circuit breaker |
| Fase 3 | 2 sprints | ⏳ Pool DB, health check, MyPy, deps |
| Fase 4 | Continuo | ⏳ Factories, staging, load tests, Docker limits |

---

## 🔮 MEJORAS OPCIONALES (Evaluar después de completar las 18)

Estas mejoras se evaluarán una vez completadas las 18 mejoras principales del plan.

### Mejora A: Regenerar SECRET_KEY 🔮
- **Problema:** SECRET_KEY en texto plano expuesta
- **Solución:** Nueva key generada con secrets seguros
- **Nota:** Evaluar si es necesario según el estado actual del proyecto
- **Estado:** PENDIENTE EVALUACIÓN

### Mejora B: Centralizar Logs (ELK/Datadog) 🔮
- **Problema:** No hay integración con sistemas de logging centralizados
- **Solución:** Integrar con ELK Stack, Datadog, o CloudWatch
- **Nota:** Requiere decisión sobre qué sistema usar:
  - AWS → CloudWatch
  - SaaS → Datadog
  - Self-hosted → ELK o Loki
- **Estado:** PENDIENTE EVALUACIÓN

---

## Próxima Mejora: #13 - Activar MyPy Estricto en CI

**Descripción:** MyPy está configurado pero ignorado en CI con `|| true`.

**Cambios necesarios:**

1. Remover `|| true` del comando mypy en CI
2. Corregir errores de tipos existentes
3. Agregar type hints faltantes

**Archivos a modificar:**

- `.github/workflows/` o archivo de CI
- Archivos con errores de tipos
