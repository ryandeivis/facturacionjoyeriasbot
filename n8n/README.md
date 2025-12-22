# Workflows n8n - Jewelry Invoice Bot

## Arquitectura

```
Bot Python                              n8n
    │                                    │
    ├─ Recibe input (texto/voz/foto)    │
    │  ────────────────────────────────→ │ [workflow_extract.json]
    │                                    │ - Transcribe audio (Whisper)
    │                                    │ - Analiza imagen (GPT-4o)
    │                                    │ - Extrae items con IA
    │  ←──────────────────────────────── │ Retorna items + totales
    │                                    │
    ├─ Muestra items al usuario          │
    ├─ Maneja edición conversacional     │
    ├─ Recolecta datos del cliente       │
    │                                    │
    ├─ Confirmar factura                 │
    │  ────────────────────────────────→ │ [workflow_pdf.json]
    │                                    │ - Genera HTML factura
    │                                    │ - Convierte a PDF
    │  ←──────────────────────────────── │ Retorna PDF (base64/URL)
    │                                    │
    └─ Envía PDF al usuario              │
```

## Workflows

### 1. workflow_extract.json - Extracción de Datos

**Endpoint:** `POST /webhook/jewelry-extract`

**Input:**
```json
{
  "type": "text|voice|photo",
  "content": "texto o base64",
  "content_type": "audio/ogg|image/jpeg",
  "vendedor_cedula": "123456789",
  "organization_id": "uuid-org",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

**Output:**
```json
{
  "success": true,
  "items": [
    {
      "numero": 1,
      "nombre": "Anillo oro 18k",
      "descripcion": "Solitario con diamante 0.5ct",
      "cantidad": 1,
      "precio": 2500000,
      "total": 2500000
    }
  ],
  "cliente": {
    "nombre": null,
    "direccion": null,
    "ciudad": null,
    "email": null,
    "telefono": null
  },
  "totales": {
    "subtotal": 2500000,
    "descuento": 0,
    "impuesto": 475000,
    "total": 2975000
  },
  "input_type": "texto",
  "transcripcion": null,
  "notas": null,
  "confianza": 0.85
}
```

### 2. workflow_pdf.json - Generación de PDF

**Endpoint:** `POST /webhook/jewelry-pdf`

**Input (generar_pdf):**
```json
{
  "tipo_evento": "generar_pdf",
  "organization_id": "uuid-org",
  "factura": {
    "id": "uuid-factura",
    "numero": "JOY-202401-0001",
    "fecha_emision": "2024-01-15",
    "fecha_vencimiento": "2024-02-15"
  },
  "cliente": {
    "nombre": "Juan Pérez",
    "direccion": "Calle 123 #45-67",
    "ciudad": "Bogotá",
    "email": "juan@email.com",
    "telefono": "3001234567",
    "cedula": "123456789"
  },
  "items": [...],
  "totales": {
    "subtotal": 2500000,
    "descuento": 0,
    "impuesto": 475000,
    "total": 2975000
  },
  "vendedor": {
    "nombre": "María García",
    "cedula": "987654321"
  },
  "notas": "Pago en efectivo"
}
```

**Output:**
```json
{
  "success": true,
  "pdf_base64": "JVBERi0xLjQK...",
  "html": "<html>...</html>",
  "filename": "factura_JOY-202401-0001.pdf"
}
```

## Configuración

### 1. Importar Workflows en n8n

1. Abrir n8n
2. Ir a **Workflows** → **Import from file**
3. Importar `workflow_extract.json`
4. Importar `workflow_pdf.json`

### 2. Configurar Credenciales

#### OpenAI API
1. Ir a **Credentials** → **Add credential** → **OpenAI API**
2. Agregar tu API Key
3. Actualizar los nodos que usan OpenAI con la credencial

#### Telegram (solo para workflow_pdf)
1. Ir a **Credentials** → **Add credential** → **Telegram API**
2. Agregar el token del bot
3. Actualizar el nodo "Enviar PDF a Telegram"

### 3. Activar Webhooks

1. Abrir cada workflow
2. Click en **Activate** (toggle arriba a la derecha)
3. Copiar las URLs del webhook:
   - Extract: `https://tu-n8n.com/webhook/jewelry-extract`
   - PDF: `https://tu-n8n.com/webhook/jewelry-pdf`

### 4. Configurar .env del Bot

```env
# n8n Webhooks
N8N_WEBHOOK_URL=https://tu-n8n.com/webhook/jewelry-extract
N8N_PDF_WEBHOOK_URL=https://tu-n8n.com/webhook/jewelry-pdf
N8N_TIMEOUT_SECONDS=60
```

## Personalización

### Cambiar Modelo de IA

En el nodo "Extraer Items con IA", puedes cambiar:
- `gpt-4o-mini` → `gpt-4o` (más preciso, más lento)
- `gpt-4o-mini` → `gpt-3.5-turbo` (más rápido, menos preciso)

### Cambiar Tasa de IVA

En el nodo "Procesar Respuesta", modificar:
```javascript
const impuesto = Math.round(baseGravable * 0.19);  // 19% Colombia
```

### Personalizar PDF

En el nodo "Generar HTML Factura", puedes modificar:
- Colores (buscar `#c9a227` para el color dorado)
- Logo (agregar imagen en el header)
- Campos adicionales

## Troubleshooting

### Error: "No pude procesar la información"
- Verificar que el texto de entrada tenga productos claros
- Revisar logs del nodo "Extraer Items con IA"

### Error: "Webhook URL no configurado"
- Verificar que las variables N8N_WEBHOOK_URL estén en .env
- Reiniciar el bot después de cambiar .env

### Timeout en procesamiento
- Aumentar N8N_TIMEOUT_SECONDS en .env
- Verificar que n8n esté corriendo correctamente

## Testing

### Test Extract (curl)
```bash
curl -X POST https://tu-n8n.com/webhook/jewelry-extract \
  -H "Content-Type: application/json" \
  -d '{
    "type": "text",
    "content": "1 anillo oro 18k precio 2500000, 2 aretes plata 925 precio 180000 cada uno",
    "vendedor_cedula": "123456789"
  }'
```

### Test PDF (curl)
```bash
curl -X POST https://tu-n8n.com/webhook/jewelry-pdf \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_evento": "generar_pdf",
    "organization_id": "test-org",
    "factura": {"numero": "TEST-001"},
    "cliente": {"nombre": "Test Cliente"},
    "items": [{"nombre": "Test", "cantidad": 1, "precio": 100000}],
    "totales": {"subtotal": 100000, "impuesto": 19000, "total": 119000},
    "vendedor": {"nombre": "Test Vendedor"}
  }'
```