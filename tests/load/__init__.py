# ==============================================================================
# Load Testing Module - Jewelry Invoice Bot
# ==============================================================================
#
# Pruebas de carga usando Locust para validar rendimiento del sistema.
#
# Arquitectura: Clean Code, Modular, SaaS Multi-tenant
#
# Estructura:
#   - locustfile.py     : Entry point principal
#   - config.py         : Configuración de escenarios y thresholds
#   - users/            : Usuarios virtuales por rol (Vendedor, Admin)
#   - tasks/            : Tareas modulares reutilizables
#   - data/             : Generadores de datos de prueba
#
# Uso:
#   locust -f tests/load/locustfile.py --host=http://localhost:8000
#
# ==============================================================================
"""
Load Testing para Jewelry Invoice Bot.

Este módulo contiene pruebas de carga usando Locust para:
- Validar rendimiento bajo carga
- Identificar cuellos de botella
- Establecer baselines de performance
- Detectar memory leaks en pruebas prolongadas
"""

__version__ = "1.0.0"
