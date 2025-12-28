# Guía de Despliegue

Guía completa para desplegar Jewelry Invoice Bot en producción.

## Tabla de Contenidos

- [Requisitos](#requisitos)
- [Despliegue con Docker](#despliegue-con-docker)
- [Variables de Entorno](#variables-de-entorno)
- [Configuración por Entorno](#configuración-por-entorno)
- [Base de Datos](#base-de-datos)
- [Health Checks](#health-checks)
- [Monitoreo](#monitoreo)
- [Logs](#logs)
- [Backup y Recovery](#backup-y-recovery)
- [Escalamiento](#escalamiento)
- [Troubleshooting](#troubleshooting)

---

## Requisitos

### Hardware Mínimo

| Componente | Desarrollo | Staging | Producción |
|------------|------------|---------|------------|
| CPU | 2 cores | 2 cores | 4 cores |
| RAM | 2 GB | 4 GB | 8 GB |
| Disco | 20 GB | 50 GB | 100 GB SSD |

### Software

- Docker 24.0+
- Docker Compose 2.20+
- (Opcional) Kubernetes 1.28+

### Puertos

| Puerto | Servicio | Descripción |
|--------|----------|-------------|
| 8000 | Bot/API | API REST y health checks |
| 5432 | PostgreSQL | Base de datos |
| 6379 | Redis | Cache |
| 5678 | n8n | Workflows UI |

---

## Despliegue con Docker

### 1. Clonar Repositorio

```bash
git clone https://github.com/ryandeivis/facturacionjoyeriasbot.git
cd facturacionjoyeriasbot
```

### 2. Configurar Variables

```bash
# Copiar template
cp .env.example .env

# Editar con valores de producción
nano .env
```

### 3. Build de Imagen

```bash
# Build para producción
docker-compose build --no-cache

# Verificar imagen
docker images | grep jewelry
```

### 4. Iniciar Servicios

```bash
# Solo servicios base (bot + db)
docker-compose up -d

# Con Redis
docker-compose --profile redis up -d

# Stack completo (bot + db + redis + n8n)
docker-compose --profile full up -d
```

### 5. Ejecutar Migraciones

```bash
# Primera vez o después de cambios de schema
docker-compose --profile migrate up migrations

# Verificar estado de migraciones
docker-compose exec bot alembic current
```

### 6. Verificar Despliegue

```bash
# Health check
curl http://localhost:8000/health

# Logs
docker-compose logs -f bot

# Estado de servicios
docker-compose ps
```

---

## Variables de Entorno

### Requeridas

```env
# Telegram
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz

# Base de Datos
DB_PASSWORD=contraseña_segura_minimo_16_chars
DB_NAME=jewelry_db

# Seguridad
SECRET_KEY=clave_secreta_32_caracteres_min
```

### Opcionales

```env
# Entorno
ENVIRONMENT=production  # development, staging, production

# API
API_PORT=8000
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR

# Redis (si se usa)
REDIS_URL=redis://redis:6379/0

# n8n (si se usa)
N8N_WEBHOOK_URL=http://n8n:5678/webhook/jewelry-extract
N8N_USER=admin
N8N_PASSWORD=contraseña_n8n

# CORS (producción)
CORS_ORIGINS=https://app.tudominio.com,https://admin.tudominio.com
```

### Generación de Secrets

```bash
# SECRET_KEY (Python)
python -c "import secrets; print(secrets.token_urlsafe(32))"

# DB_PASSWORD (OpenSSL)
openssl rand -base64 24

# Con Docker
docker run --rm python:3.11-slim python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## Configuración por Entorno

### Development

```python
# config/environments.py
class DevelopmentConfig:
    DEBUG = True
    LOG_LEVEL = "DEBUG"
    DATABASE_POOL_SIZE = 5
    DATABASE_MAX_OVERFLOW = 10
    RATE_LIMIT_REQUESTS = 1000  # Relajado
```

### Staging

```python
class StagingConfig:
    DEBUG = False
    LOG_LEVEL = "INFO"
    DATABASE_POOL_SIZE = 15
    DATABASE_MAX_OVERFLOW = 15
    RATE_LIMIT_REQUESTS = 100
```

### Production

```python
class ProductionConfig:
    DEBUG = False
    LOG_LEVEL = "WARNING"
    DATABASE_POOL_SIZE = 30
    DATABASE_MAX_OVERFLOW = 20
    RATE_LIMIT_REQUESTS = 60
    CORS_ORIGINS = ["https://tudominio.com"]
```

---

## Base de Datos

### Pool de Conexiones

| Parámetro | Dev | Staging | Prod |
|-----------|-----|---------|------|
| pool_size | 5 | 15 | 30 |
| max_overflow | 10 | 15 | 20 |
| pool_timeout | 30s | 30s | 30s |
| pool_recycle | 1800s | 1800s | 1800s |

### Índices Importantes

```sql
-- Verificar índices existentes
SELECT indexname, tablename FROM pg_indexes WHERE schemaname = 'public';

-- Índices críticos para rendimiento
CREATE INDEX IF NOT EXISTS ix_invoices_org_created
    ON invoices(organization_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_invoices_org_deleted
    ON invoices(organization_id, is_deleted);
```

### Mantenimiento

```bash
# Vacuum (limpieza)
docker-compose exec db psql -U postgres -d jewelry_db -c "VACUUM ANALYZE;"

# Reindex
docker-compose exec db psql -U postgres -d jewelry_db -c "REINDEX DATABASE jewelry_db;"

# Estadísticas de tablas
docker-compose exec db psql -U postgres -d jewelry_db -c "\dt+"
```

---

## Health Checks

### Endpoints

| Endpoint | Propósito | Uso |
|----------|-----------|-----|
| `/health` | Estado general | Monitoreo |
| `/health/live` | Liveness | Kubernetes |
| `/health/ready` | Readiness | Kubernetes |

### Respuestas

```bash
# Healthy
curl http://localhost:8000/health
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "version": "1.0.0"
}

# Unhealthy
{
  "status": "unhealthy",
  "database": "disconnected",
  "error": "Connection refused"
}
```

### Docker Health Check

```yaml
# docker-compose.yml
healthcheck:
  test: ["CMD", "curl", "--fail", "--silent", "http://localhost:8000/health/live"]
  interval: 30s
  timeout: 5s
  start_period: 30s
  retries: 3
```

### Kubernetes Probes

```yaml
# kubernetes/deployment.yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
```

---

## Monitoreo

### Métricas Prometheus

```bash
# Endpoint de métricas
curl http://localhost:8000/metrics

# Métricas disponibles
jewelry_requests_total{method="GET", endpoint="/api/v1/invoices"}
jewelry_request_duration_seconds{endpoint="/api/v1/invoices"}
jewelry_invoices_created_total{organization="org-123"}
jewelry_active_users{organization="org-123"}
```

### Dashboard Grafana

```bash
# Importar dashboard
# ID: (crear dashboard personalizado)

# Paneles recomendados:
# - Requests por segundo
# - Latencia p50/p95/p99
# - Errores por endpoint
# - Facturas creadas por hora
# - Usuarios activos
```

### Alertas Recomendadas

| Alerta | Condición | Severidad |
|--------|-----------|-----------|
| High Error Rate | error_rate > 5% | Critical |
| High Latency | p99 > 2s | Warning |
| Database Down | health != "connected" | Critical |
| High Memory | memory > 80% | Warning |
| Disk Full | disk > 90% | Critical |

---

## Logs

### Formato Estructurado

```json
{
  "timestamp": "2025-01-15T10:30:00Z",
  "level": "INFO",
  "logger": "jewelry.api.invoices",
  "message": "Invoice created",
  "organization_id": "org-123",
  "invoice_id": "inv-456",
  "user_id": 789,
  "duration_ms": 45
}
```

### Niveles

| Nivel | Uso |
|-------|-----|
| DEBUG | Desarrollo, debugging |
| INFO | Operaciones normales |
| WARNING | Situaciones inesperadas |
| ERROR | Errores que requieren atención |
| CRITICAL | Sistema comprometido |

### Rotación

```yaml
# docker-compose.yml
logging:
  driver: "json-file"
  options:
    max-size: "100m"
    max-file: "5"
```

### Ver Logs

```bash
# Todos los servicios
docker-compose logs -f

# Solo bot
docker-compose logs -f bot

# Últimas 100 líneas
docker-compose logs --tail=100 bot

# Filtrar errores
docker-compose logs bot 2>&1 | grep ERROR
```

---

## Backup y Recovery

### Backup de Base de Datos

```bash
# Backup manual
docker-compose exec db pg_dump -U postgres jewelry_db > backup_$(date +%Y%m%d).sql

# Backup comprimido
docker-compose exec db pg_dump -U postgres jewelry_db | gzip > backup_$(date +%Y%m%d).sql.gz

# Backup automático (cron)
0 2 * * * docker-compose exec -T db pg_dump -U postgres jewelry_db | gzip > /backups/jewelry_$(date +\%Y\%m\%d).sql.gz
```

### Restore

```bash
# Restore desde backup
cat backup_20250115.sql | docker-compose exec -T db psql -U postgres jewelry_db

# Restore comprimido
gunzip -c backup_20250115.sql.gz | docker-compose exec -T db psql -U postgres jewelry_db
```

### Backup de Volúmenes

```bash
# Listar volúmenes
docker volume ls | grep jewelry

# Backup de volumen
docker run --rm -v jewelry_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_data.tar.gz /data

# Restore de volumen
docker run --rm -v jewelry_postgres_data:/data -v $(pwd):/backup alpine tar xzf /backup/postgres_data.tar.gz -C /
```

---

## Escalamiento

### Horizontal (múltiples instancias)

```yaml
# docker-compose.override.yml
services:
  bot:
    deploy:
      replicas: 3
```

**Requisitos para escalar:**
- Redis obligatorio (rate limiting compartido)
- Load balancer frente a las instancias
- Sesiones stateless (JWT)

### Vertical (más recursos)

```yaml
# docker-compose.yml
deploy:
  resources:
    limits:
      cpus: '2.0'      # Aumentar de 0.5
      memory: 2G       # Aumentar de 512M
    reservations:
      cpus: '1.0'
      memory: 1G
```

### Límites Actuales

| Servicio | CPU | Memoria | Notas |
|----------|-----|---------|-------|
| bot | 0.50 | 512M | Aumentar si hay timeouts |
| db | 1.00 | 1G | Aumentar para más conexiones |
| redis | 0.25 | 256M | Suficiente para cache |
| n8n | 0.50 | 512M | Aumentar para workflows pesados |

---

## Troubleshooting

### Bot no responde

```bash
# Verificar que el servicio está corriendo
docker-compose ps bot

# Ver logs
docker-compose logs --tail=50 bot

# Reiniciar
docker-compose restart bot

# Verificar conexión a Telegram
curl https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe
```

### Error de conexión a base de datos

```bash
# Verificar que PostgreSQL está corriendo
docker-compose ps db

# Verificar conectividad
docker-compose exec bot python -c "from src.database.connection import engine; print('OK')"

# Ver logs de PostgreSQL
docker-compose logs db

# Verificar credenciales
docker-compose exec db psql -U postgres -c "SELECT 1"
```

### Redis no conecta

```bash
# Verificar servicio
docker-compose ps redis

# Test de conexión
docker-compose exec redis redis-cli ping

# Ver memoria usada
docker-compose exec redis redis-cli info memory
```

### Alto uso de memoria

```bash
# Ver uso actual
docker stats

# Identificar contenedor problemático
docker-compose top

# Forzar garbage collection (Python)
docker-compose exec bot python -c "import gc; gc.collect()"
```

### Migraciones fallan

```bash
# Ver estado actual
docker-compose exec bot alembic current

# Ver historial
docker-compose exec bot alembic history

# Rollback una versión
docker-compose exec bot alembic downgrade -1

# Regenerar migración
docker-compose exec bot alembic revision --autogenerate -m "descripcion"
```

---

## Checklist de Producción

Antes de ir a producción, verificar:

- [ ] Variables de entorno configuradas (no usar defaults)
- [ ] SECRET_KEY generada de forma segura
- [ ] TELEGRAM_BOT_TOKEN válido
- [ ] DB_PASSWORD segura (16+ caracteres)
- [ ] CORS_ORIGINS específicos (no `*`)
- [ ] LOG_LEVEL en WARNING o INFO
- [ ] Health checks funcionando
- [ ] Backups automatizados
- [ ] Monitoreo configurado
- [ ] Alertas configuradas
- [ ] SSL/TLS habilitado (reverse proxy)
- [ ] Rate limiting activo
- [ ] Límites de recursos definidos

---

## Soporte

- **Issues**: [GitHub Issues](https://github.com/ryandeivis/facturacionjoyeriasbot/issues)
- **Docs**: [Documentación](../README.md)
