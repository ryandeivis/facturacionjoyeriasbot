# Jewelry Invoice Bot - API Documentation

## Overview

API REST para el sistema de facturación de joyerías. Diseñada para integraciones SaaS multi-tenant.

## Base URL

| Entorno     | URL                              |
|-------------|----------------------------------|
| Desarrollo  | `http://localhost:8000`          |
| Producción  | `https://api.joyeriainvoice.com` |

## Autenticación

### Headers Requeridos

```http
X-Organization-ID: org-xyz-123
Authorization: Bearer <token>
```

### Obtener Token

```bash
curl -X POST /api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"cedula": "12345678", "password": "SecurePass123!"}'
```

Respuesta:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

## Quick Start

### 1. Listar Facturas

```bash
curl -X GET "http://localhost:8000/api/v1/invoices?limit=10" \
  -H "X-Organization-ID: org-xyz-123" \
  -H "Authorization: Bearer <token>"
```

### 2. Crear Factura

```bash
curl -X POST "http://localhost:8000/api/v1/invoices" \
  -H "X-Organization-ID: org-xyz-123" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "cliente_nombre": "Juan Pérez",
    "cliente_cedula": "12345678",
    "cliente_telefono": "3001234567",
    "items": [
      {
        "descripcion": "Anillo Oro 18K",
        "cantidad": 1,
        "precio_unitario": 500000
      }
    ]
  }'
```

### 3. Obtener Factura

```bash
curl -X GET "http://localhost:8000/api/v1/invoices/inv-123" \
  -H "X-Organization-ID: org-xyz-123" \
  -H "Authorization: Bearer <token>"
```

### 4. Actualizar Estado

```bash
curl -X PATCH "http://localhost:8000/api/v1/invoices/inv-123/status" \
  -H "X-Organization-ID: org-xyz-123" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"status": "PAGADA"}'
```

## Endpoints

### Health Check

| Método | Endpoint       | Descripción                    |
|--------|----------------|--------------------------------|
| GET    | `/health`      | Estado del sistema             |
| GET    | `/health/live` | Liveness (Kubernetes)          |
| GET    | `/health/ready`| Readiness (Kubernetes)         |
| GET    | `/metrics`     | Métricas Prometheus            |

### Organizations

| Método | Endpoint                        | Descripción                 |
|--------|---------------------------------|-----------------------------|
| GET    | `/api/v1/organizations`         | Listar organizaciones       |
| POST   | `/api/v1/organizations`         | Crear organización          |
| GET    | `/api/v1/organizations/{id}`    | Obtener organización        |
| PATCH  | `/api/v1/organizations/{id}`    | Actualizar organización     |
| GET    | `/api/v1/organizations/{id}/stats` | Estadísticas            |

### Invoices

| Método | Endpoint                              | Descripción              |
|--------|---------------------------------------|--------------------------|
| GET    | `/api/v1/invoices`                    | Listar facturas          |
| POST   | `/api/v1/invoices`                    | Crear factura            |
| GET    | `/api/v1/invoices/{id}`               | Obtener factura          |
| DELETE | `/api/v1/invoices/{id}`               | Eliminar factura         |
| PATCH  | `/api/v1/invoices/{id}/status`        | Actualizar estado        |
| GET    | `/api/v1/invoices/by-number/{numero}` | Buscar por número        |

## Modelos

### Invoice (Factura)

```json
{
  "id": "inv-123-abc",
  "numero_factura": "FAC-202401-0001",
  "organization_id": "org-xyz",
  "cliente_nombre": "Juan Pérez",
  "cliente_cedula": "12345678",
  "cliente_telefono": "3001234567",
  "cliente_direccion": "Calle 123",
  "cliente_email": "juan@email.com",
  "items": [
    {
      "descripcion": "Anillo Oro 18K",
      "cantidad": 1,
      "precio_unitario": 500000,
      "subtotal": 500000
    }
  ],
  "subtotal": 500000,
  "descuento": 0,
  "impuestos": 95000,
  "total": 595000,
  "estado": "PENDIENTE",
  "vendedor_id": 1,
  "notas": "Cliente frecuente",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

### Organization (Organización)

```json
{
  "id": "org-xyz-123",
  "name": "Joyería El Diamante",
  "plan": "pro",
  "invoice_prefix": "JOY",
  "is_active": true,
  "users_count": 5,
  "invoices_count": 150,
  "created_at": "2024-01-01T00:00:00Z",
  "plan_limits": {
    "invoices_per_month": 500,
    "users_per_org": 10,
    "max_items_per_invoice": 100,
    "features": {
      "ai_extraction": true,
      "voice_input": true,
      "photo_input": true,
      "custom_templates": true,
      "api_access": true
    }
  }
}
```

### Estados de Factura

| Estado     | Descripción                        |
|------------|------------------------------------|
| BORRADOR   | Factura en edición                 |
| PENDIENTE  | Factura emitida, pendiente de pago |
| PAGADA     | Factura pagada                     |
| ANULADA    | Factura anulada                    |

### Planes

| Plan       | Facturas/mes | Usuarios | Características              |
|------------|--------------|----------|------------------------------|
| basic      | 100          | 3        | IA, Foto                     |
| pro        | 500          | 10       | IA, Foto, Voz, Plantillas    |
| enterprise | Ilimitado    | Ilimitado| Todo + API + Soporte         |

## Paginación

Todos los endpoints de listado soportan paginación:

```http
GET /api/v1/invoices?limit=20&offset=40
```

| Parámetro | Tipo    | Default | Máximo | Descripción                |
|-----------|---------|---------|--------|----------------------------|
| limit     | integer | 50      | 100    | Resultados por página      |
| offset    | integer | 0       | -      | Resultados a saltar        |

## Filtros

### Filtrar Facturas por Estado

```http
GET /api/v1/invoices?status=PENDIENTE
```

### Incluir Organizaciones Inactivas

```http
GET /api/v1/organizations?include_inactive=true
```

## Rate Limiting

La API implementa rate limiting por plan:

| Plan       | Requests/min | Descripción                    |
|------------|--------------|--------------------------------|
| basic      | 60           | 1 request por segundo          |
| pro        | 300          | 5 requests por segundo         |
| enterprise | 1000         | ~17 requests por segundo       |

Headers de respuesta:
```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1705312200
```

## Errores

### Formato de Error

```json
{
  "error": "ValidationError",
  "message": "El campo 'cliente_nombre' es requerido",
  "status_code": 400,
  "timestamp": "2024-01-15T10:30:00Z",
  "details": {
    "field": "cliente_nombre",
    "type": "missing"
  }
}
```

### Códigos de Error

| Código | Error              | Descripción                        |
|--------|--------------------|------------------------------------|
| 400    | BadRequest         | Datos de entrada inválidos         |
| 401    | Unauthorized       | Token inválido o expirado          |
| 403    | Forbidden          | Sin permisos para esta acción      |
| 404    | NotFound           | Recurso no encontrado              |
| 429    | RateLimitExceeded  | Límite de requests excedido        |
| 500    | InternalError      | Error interno del servidor         |

## Ejemplos con Python

### Usando requests

```python
import requests

BASE_URL = "http://localhost:8000"
HEADERS = {
    "X-Organization-ID": "org-xyz-123",
    "Authorization": "Bearer <token>",
    "Content-Type": "application/json"
}

# Listar facturas
response = requests.get(
    f"{BASE_URL}/api/v1/invoices",
    headers=HEADERS,
    params={"limit": 10, "status": "PENDIENTE"}
)
facturas = response.json()

# Crear factura
nueva_factura = {
    "cliente_nombre": "María García",
    "cliente_cedula": "87654321",
    "items": [
        {"descripcion": "Collar Perlas", "cantidad": 1, "precio_unitario": 350000}
    ]
}
response = requests.post(
    f"{BASE_URL}/api/v1/invoices",
    headers=HEADERS,
    json=nueva_factura
)
factura_creada = response.json()
print(f"Factura creada: {factura_creada['numero_factura']}")
```

### Clase Cliente

```python
from typing import Optional, List, Dict, Any
import requests


class JewelryInvoiceClient:
    """Cliente para la API de Jewelry Invoice Bot."""

    def __init__(self, base_url: str, org_id: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "X-Organization-ID": org_id,
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def list_invoices(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Lista facturas."""
        params = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status

        response = requests.get(
            f"{self.base_url}/api/v1/invoices",
            headers=self.headers,
            params=params
        )
        response.raise_for_status()
        return response.json()

    def get_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """Obtiene una factura."""
        response = requests.get(
            f"{self.base_url}/api/v1/invoices/{invoice_id}",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

    def create_invoice(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Crea una factura."""
        response = requests.post(
            f"{self.base_url}/api/v1/invoices",
            headers=self.headers,
            json=data
        )
        response.raise_for_status()
        return response.json()

    def update_status(self, invoice_id: str, status: str) -> Dict[str, Any]:
        """Actualiza estado de factura."""
        response = requests.patch(
            f"{self.base_url}/api/v1/invoices/{invoice_id}/status",
            headers=self.headers,
            json={"status": status}
        )
        response.raise_for_status()
        return response.json()


# Uso
client = JewelryInvoiceClient(
    base_url="http://localhost:8000",
    org_id="org-xyz-123",
    token="<token>"
)

# Listar pendientes
pendientes = client.list_invoices(status="PENDIENTE")
for factura in pendientes:
    print(f"{factura['numero_factura']}: ${factura['total']:,.0f}")
```

## Swagger UI

La documentación interactiva está disponible en:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## Soporte

- **Email**: soporte@joyeriainvoice.com
- **Documentación**: https://docs.joyeriainvoice.com
- **Status Page**: https://status.joyeriainvoice.com
