# Plan: Generación de PDF + HTML para Telegram

## Objetivo
Generar factura en PDF real + HTML y enviar ambos formatos al usuario via Telegram.

---

## Arquitectura Propuesta

```
Bot Python                              n8n
    │                                    │
    ├─ Confirmar factura                 │
    │  ────────────────────────────────→ │ [workflow_pdf.json]
    │                                    │
    │                                    ├─ 1. Generar HTML (ya existe)
    │                                    │
    │                                    ├─ 2. Crear Google Doc con HTML
    │                                    │
    │                                    ├─ 3. Exportar PDF desde Drive
    │                                    │
    │                                    ├─ 4. Subir PDF a carpeta Drive
    │                                    │
    │  ←──────────────────────────────── │ Retorna: pdf_url + html
    │                                    │
    └─ Enviar ambos a Telegram           │
       - PDF como documento              │
       - HTML como archivo adjunto       │
```

---

## Opciones para Generar PDF

### Opción A: Google Docs + Drive (Recomendada)
**Pros:** Gratis, confiable, PDFs profesionales
**Contras:** Requiere cuenta Google conectada a n8n

**Flujo:**
1. Crear documento Google Docs con contenido HTML
2. Exportar como PDF via Google Drive API
3. Obtener URL pública del PDF
4. Retornar URL al bot

### Opción B: Gotenberg (Self-hosted)
**Pros:** Sin límites, control total
**Contras:** Requiere servidor adicional con Docker

**Flujo:**
1. Enviar HTML a Gotenberg API
2. Recibir PDF binario
3. Guardar en Drive o retornar base64

### Opción C: html2pdf.app (API externa)
**Pros:** Fácil de configurar
**Contras:** Requiere API key, tiene límites gratuitos

---

## Plan de Implementación (Opción A - Google Docs)

### Fase 1: Configurar Credenciales Google en n8n

1. En n8n, ir a **Credentials** → **Add Credential**
2. Seleccionar **Google Docs API** (OAuth2)
3. Configurar:
   - Client ID
   - Client Secret
   - Scopes: `https://www.googleapis.com/auth/documents`, `https://www.googleapis.com/auth/drive`
4. Autorizar la aplicación

### Fase 2: Actualizar Workflow n8n

**Nodos a agregar:**

```
[Webhook] → [Generar HTML] → [Crear Google Doc] → [Exportar PDF] → [Responder]
```

#### Nodo 1: Generar HTML (ya existe)
- Genera el HTML de la factura con estilos

#### Nodo 2: Crear Google Doc
- Tipo: Google Docs → Create Document
- Nombre: `Factura_{{numero_factura}}`
- Contenido: HTML generado

#### Nodo 3: Exportar como PDF
- Tipo: Google Drive → Export
- File ID: del documento creado
- MIME Type: `application/pdf`

#### Nodo 4: Subir PDF a Drive (opcional)
- Tipo: Google Drive → Upload
- Carpeta: "Facturas"
- Hacer público o compartir link

#### Nodo 5: Responder
```json
{
  "success": true,
  "pdf_url": "https://drive.google.com/...",
  "pdf_base64": "...",
  "html": "<html>...</html>",
  "filename": "factura_JOY-202412-0001.pdf"
}
```

### Fase 3: Actualizar Bot Python

**Modificar `_enviar_pdf_usuario` en invoice.py:**

```python
async def _enviar_pdf_usuario(update, context, invoice, pdf_data) -> bool:
    chat_id = update.effective_chat.id

    # 1. Enviar PDF
    if pdf_data.pdf_url:
        # Descargar PDF desde URL
        async with aiohttp.ClientSession() as session:
            async with session.get(pdf_data.pdf_url) as resp:
                pdf_bytes = await resp.read()

        # Enviar como documento
        await context.bot.send_document(
            chat_id=chat_id,
            document=pdf_bytes,
            filename=f"factura_{invoice.numero_factura}.pdf",
            caption=f"📄 Factura {invoice.numero_factura}"
        )

    elif pdf_data.pdf_base64:
        pdf_bytes = base64.b64decode(pdf_data.pdf_base64)
        # ... enviar como documento

    # 2. Enviar HTML (opcional)
    if pdf_data.html:
        html_bytes = pdf_data.html.encode('utf-8')
        await context.bot.send_document(
            chat_id=chat_id,
            document=html_bytes,
            filename=f"factura_{invoice.numero_factura}.html",
            caption="📋 Vista web de la factura"
        )

    return True
```

### Fase 4: Agregar Campo html a N8NPDFResponse

**Modificar src/models/invoice.py:**

```python
class N8NPDFResponse(BaseModel):
    success: bool = False
    pdf_url: Optional[str] = None
    pdf_base64: Optional[str] = None
    html: Optional[str] = None  # <-- Agregar
    filename: Optional[str] = None  # <-- Agregar
    error: Optional[str] = None
```

---

## Workflow n8n Actualizado

```json
{
  "nodes": [
    // 1. Webhook (existente)
    // 2. Generar HTML (existente)

    // 3. NUEVO: Crear Google Doc
    {
      "type": "n8n-nodes-base.googleDocs",
      "name": "Crear Documento",
      "parameters": {
        "operation": "create",
        "title": "=Factura_{{ $json.factura_numero }}",
        "content": "={{ $json.html }}"
      }
    },

    // 4. NUEVO: Exportar PDF
    {
      "type": "n8n-nodes-base.googleDrive",
      "name": "Exportar PDF",
      "parameters": {
        "operation": "download",
        "fileId": "={{ $json.documentId }}",
        "options": {
          "googleFileConversion": {
            "docsToFormat": "application/pdf"
          }
        }
      }
    },

    // 5. Preparar Respuesta
    {
      "type": "n8n-nodes-base.code",
      "name": "Preparar Respuesta",
      "parameters": {
        "jsCode": "return { success: true, pdf_base64: $binary.data.toString('base64'), html: $('Generar HTML').item.json.html }"
      }
    }
  ]
}
```

---

## Alternativa: Sin Google (Gotenberg)

Si no quieres usar Google, puedo configurar Gotenberg:

### Docker Compose
```yaml
services:
  gotenberg:
    image: gotenberg/gotenberg:8
    ports:
      - "3000:3000"
```

### Nodo n8n
```json
{
  "type": "n8n-nodes-base.httpRequest",
  "name": "HTML to PDF",
  "parameters": {
    "url": "http://gotenberg:3000/forms/chromium/convert/html",
    "method": "POST",
    "sendBody": true,
    "bodyContentType": "multipart-form-data",
    "bodyParameters": {
      "parameters": [
        {
          "name": "files",
          "value": "={{ $json.html }}"
        }
      ]
    }
  }
}
```

---

## Resumen de Cambios

| Componente | Cambio |
|------------|--------|
| n8n workflow | Agregar nodos Google Docs + Drive |
| N8NPDFResponse | Agregar campos `html` y `filename` |
| invoice.py | Enviar PDF + HTML a Telegram |
| .env | (Opcional) Agregar GOOGLE_FOLDER_ID |

---

## Próximos Pasos

1. **¿Tienes Google conectado a n8n?**
   - Si → Implemento Opción A (Google Docs)
   - No → Configuramos credenciales primero

2. **¿Prefieres Gotenberg (self-hosted)?**
   - Requiere Docker en tu servidor

3. **¿Quieres que el PDF se guarde en Drive?**
   - Si → Creo carpeta "Facturas" organizada por mes
   - No → Solo genero y envío, sin guardar

Dime qué opción prefieres y procedo con la implementación.