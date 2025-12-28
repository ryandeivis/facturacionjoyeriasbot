# Changelog

Todos los cambios notables de este proyecto serán documentados en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

## [Unreleased]

### Added

- Documentación profesional completa (README, LICENSE, CONTRIBUTING)

---

## [1.0.0] - 2025-12-28

### Added

- **Bot de Telegram** con comandos `/start`, `/factura`, `/lista`, `/buscar`, `/ayuda`
- **Arquitectura SaaS Multi-tenant** con aislamiento por organización
- **API REST** con FastAPI y documentación Swagger/OpenAPI
- **Autenticación** por cédula y contraseña con JWT
- **Generación de PDF** de facturas profesionales
- **Integración n8n** para procesamiento IA (texto, voz, fotos)
- **Sistema de métricas** de negocio para dashboard SaaS
- **Rate limiting distribuido** con Redis
- **Circuit breaker** para resiliencia de base de datos
- **Health checks** HTTP para Kubernetes/Docker
- **Load testing** con Locust (escenarios smoke, load, stress, spike, soak)
- **Factory pattern** para tests con factory-boy
- **Type checking** estricto con MyPy (0 errores)
- **Límites de recursos** Docker (CPU/memoria por servicio)

### Security

- Token de Telegram regenerado (no expuesto)
- CORS configurado por entorno (no `*`)
- Gestión segura de secrets
- `.gitignore` configurado para archivos sensibles

### Infrastructure

- Docker Compose con servicios: bot, db, redis, n8n, migrations
- Pool de conexiones PostgreSQL optimizado por entorno
- Índices de base de datos para queries frecuentes
- Upper bounds en todas las dependencias

---

## Tipos de Cambios

- **Added** - Nuevas funcionalidades
- **Changed** - Cambios en funcionalidades existentes
- **Deprecated** - Funcionalidades que serán removidas
- **Removed** - Funcionalidades removidas
- **Fixed** - Corrección de bugs
- **Security** - Correcciones de vulnerabilidades

---

[Unreleased]: https://github.com/ryandeivis/facturacionjoyeriasbot/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/ryandeivis/facturacionjoyeriasbot/releases/tag/v1.0.0
