# Load Testing - Jewelry Invoice Bot

Pruebas de carga usando [Locust](https://locust.io/) para validar el rendimiento del sistema.

## Instalación

```bash
pip install locust>=2.20.0,<3.0.0
```

## Uso Rápido

### Modo Interactivo (con UI Web)

```bash
# Iniciar Locust
locust -f tests/load/locustfile.py --host=http://localhost:8000

# Abrir navegador en http://localhost:8089
# Configurar número de usuarios y spawn rate
```

### Modo Headless (CI/CD)

```bash
# Smoke test (rápido)
locust -f tests/load/locustfile.py --headless \
    -u 5 -r 1 -t 1m \
    --host=http://localhost:8000 \
    --html=reports/smoke_test.html

# Load test (normal)
locust -f tests/load/locustfile.py --headless \
    -u 50 -r 5 -t 10m \
    --host=http://localhost:8000 \
    --html=reports/load_test.html

# Stress test (límites)
locust -f tests/load/locustfile.py --headless \
    -u 200 -r 10 -t 15m \
    --host=http://localhost:8000 \
    --html=reports/stress_test.html
```

## Escenarios de Prueba

| Escenario | Usuarios | Duración | Descripción |
|-----------|----------|----------|-------------|
| **Smoke** | 3-5 | 1 min | Verificar que funciona |
| **Load** | 50 | 10 min | Carga normal esperada |
| **Stress** | 200 | 15 min | Encontrar límites |
| **Spike** | 10→100→10 | 5 min | Picos de tráfico |
| **Soak** | 30 | 1 hora | Detectar memory leaks |

## Usuarios Virtuales

### VendedorUser (weight=3, 75% del tráfico)

Simula un vendedor de joyería:

| Tarea | Peso | Descripción |
|-------|------|-------------|
| `list_invoices` | 5 | Ver listado de facturas |
| `get_invoice` | 3 | Ver detalle de factura |
| `create_invoice` | 2 | Crear nueva factura |
| `update_invoice` | 1 | Actualizar estado |
| `export_pdf` | 1 | Exportar a PDF |

### AdminUser (weight=1, 25% del tráfico)

Simula un administrador:

| Tarea | Peso | Descripción |
|-------|------|-------------|
| `list_organizations` | 3 | Ver organizaciones |
| `get_organization` | 2 | Detalle de org |
| `view_metrics` | 2 | Dashboard de métricas |
| `list_invoices` | 1 | Supervisión general |

## Filtrar por Tags

```bash
# Solo health checks
locust -f tests/load/locustfile.py --tags health

# Solo operaciones de facturas
locust -f tests/load/locustfile.py --tags invoices

# Solo tareas de admin
locust -f tests/load/locustfile.py --tags admin

# Excluir operaciones lentas
locust -f tests/load/locustfile.py --exclude-tags slow
```

## Configuración de Credenciales

Las credenciales de prueba se configuran via variables de entorno:

```bash
export LOAD_TEST_CEDULA="123456789"
export LOAD_TEST_PASSWORD="test_password_123"
export LOAD_TEST_ORG_ID="test-org-001"
export LOAD_TEST_ENV="staging"
```

O en un archivo `.env.load_test`:

```env
LOAD_TEST_CEDULA=123456789
LOAD_TEST_PASSWORD=test_password_123
LOAD_TEST_ORG_ID=test-org-001
LOAD_TEST_ENV=staging
```

## Thresholds de Performance

Tiempos de respuesta objetivo (milisegundos):

| Endpoint | p50 | p95 | p99 | Max |
|----------|-----|-----|-----|-----|
| Health Check | 20 | 50 | 100 | 200 |
| Login | 100 | 300 | 500 | 1000 |
| List Invoices | 100 | 300 | 500 | 1000 |
| Create Invoice | 200 | 500 | 1000 | 2000 |
| Export PDF | 500 | 2000 | 5000 | 10000 |

## Estructura de Archivos

```
tests/load/
├── __init__.py          # Módulo principal
├── locustfile.py        # Entry point de Locust
├── config.py            # Configuración centralizada
├── README.md            # Esta documentación
├── users/               # Usuarios virtuales
│   ├── __init__.py
│   ├── base.py          # BaseAPIUser con auth
│   ├── vendedor.py      # VendedorUser
│   └── admin.py         # AdminUser
├── tasks/               # Tareas reutilizables
│   └── __init__.py
└── data/                # Generadores de datos
    ├── __init__.py
    └── generators.py    # Datos de joyería colombiana
```

## Reportes

Los reportes HTML se guardan en `reports/`:

```bash
# Generar reporte
locust -f tests/load/locustfile.py --headless \
    -u 50 -r 5 -t 5m \
    --host=http://localhost:8000 \
    --html=reports/load_test_$(date +%Y%m%d_%H%M%S).html
```

## Integración con CI

En GitHub Actions:

```yaml
load-test:
  runs-on: ubuntu-latest
  needs: [test]
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: '3.11'
    - run: pip install locust
    - run: |
        locust -f tests/load/locustfile.py --headless \
            -u 10 -r 2 -t 1m \
            --host=${{ secrets.STAGING_URL }} \
            --html=reports/load_test.html
    - uses: actions/upload-artifact@v4
      with:
        name: load-test-report
        path: reports/
```

## Troubleshooting

### Error: "Connection refused"

Asegúrate de que el servidor esté corriendo:

```bash
# Iniciar el servidor
python -m src.api.app

# Verificar health
curl http://localhost:8000/health/live
```

### Error: "Unauthorized"

Verifica las credenciales de prueba:

```bash
# El usuario debe existir en la base de datos
python -c "from tests.load.config import DEFAULT_CREDENTIALS; print(DEFAULT_CREDENTIALS)"
```

### Rendimiento bajo

- Verificar que la base de datos tiene índices (Mejora 11)
- Verificar el pool de conexiones (Mejora 12)
- Revisar logs del servidor durante la prueba
