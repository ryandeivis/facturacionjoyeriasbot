# ==============================================================================
# Locustfile - Entry Point for Load Testing
# ==============================================================================
#
# Jewelry Invoice Bot - Pruebas de Carga
#
# Arquitectura: Clean Code, Modular, SaaS Multi-tenant
#
# Uso:
#   # Modo interactivo (UI web en http://localhost:8089)
#   locust -f tests/load/locustfile.py --host=http://localhost:8000
#
#   # Modo headless (CI/CD)
#   locust -f tests/load/locustfile.py --headless \
#       -u 50 -r 5 -t 5m \
#       --host=http://localhost:8000 \
#       --html=reports/load_test.html
#
#   # Ejecutar solo escenario smoke
#   locust -f tests/load/locustfile.py --tags smoke --host=http://localhost:8000
#
# ==============================================================================
"""
Entry point para pruebas de carga con Locust.

Este archivo importa todos los usuarios virtuales y los expone a Locust.
La proporción de usuarios se controla con el atributo `weight` de cada clase.
"""

import logging
import sys
from pathlib import Path

# Agregar el directorio raíz al path para imports
ROOT_DIR = Path(__file__).parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ==============================================================================
# IMPORTAR USUARIOS
# ==============================================================================

from tests.load.users.vendedor import VendedorUser
from tests.load.users.admin import AdminUser


# ==============================================================================
# EVENTOS DE LOCUST (Hooks)
# ==============================================================================

from locust import events
from locust.runners import MasterRunner, WorkerRunner


@events.init.add_listener
def on_locust_init(environment, **kwargs):
    """
    Ejecutado al iniciar Locust.

    Configura el ambiente de pruebas.
    """
    logger.info("=" * 60)
    logger.info("Jewelry Invoice Bot - Load Testing")
    logger.info("=" * 60)

    if isinstance(environment.runner, MasterRunner):
        logger.info("Iniciando como MASTER")
    elif isinstance(environment.runner, WorkerRunner):
        logger.info("Iniciando como WORKER")
    else:
        logger.info("Iniciando en modo LOCAL")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """
    Ejecutado al iniciar las pruebas.
    """
    logger.info("-" * 60)
    logger.info("Iniciando pruebas de carga...")
    logger.info(f"Host: {environment.host}")
    logger.info(f"Usuarios configurados:")
    logger.info(f"  - VendedorUser (weight=3)")
    logger.info(f"  - AdminUser (weight=1)")
    logger.info("-" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """
    Ejecutado al detener las pruebas.
    """
    logger.info("-" * 60)
    logger.info("Pruebas de carga finalizadas")

    # Mostrar resumen si hay estadísticas
    if environment.stats.total.num_requests > 0:
        stats = environment.stats.total
        logger.info(f"Total requests: {stats.num_requests}")
        logger.info(f"Failures: {stats.num_failures}")
        logger.info(f"Avg response time: {stats.avg_response_time:.0f}ms")
        logger.info(f"Requests/s: {stats.total_rps:.2f}")

        if stats.num_failures > 0:
            error_rate = (stats.num_failures / stats.num_requests) * 100
            logger.warning(f"Error rate: {error_rate:.2f}%")

    logger.info("-" * 60)


@events.request.add_listener
def on_request(
    request_type,
    name,
    response_time,
    response_length,
    response,
    context,
    exception,
    **kwargs
):
    """
    Ejecutado en cada request.

    Útil para logging detallado o métricas personalizadas.
    """
    if exception:
        logger.debug(f"Request failed: {name} - {exception}")


# ==============================================================================
# USUARIOS EXPUESTOS A LOCUST
# ==============================================================================

# Locust detecta automáticamente las clases que heredan de HttpUser
# La proporción está definida por el atributo `weight` de cada clase:
#   - VendedorUser: weight=3 (75% del tráfico)
#   - AdminUser: weight=1 (25% del tráfico)

__all__ = ["VendedorUser", "AdminUser"]


# ==============================================================================
# MODO DEBUG (ejecutar directamente)
# ==============================================================================

if __name__ == "__main__":
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║     Jewelry Invoice Bot - Load Testing con Locust         ║
    ╠═══════════════════════════════════════════════════════════╣
    ║                                                           ║
    ║  Uso:                                                     ║
    ║    locust -f tests/load/locustfile.py \\                  ║
    ║        --host=http://localhost:8000                       ║
    ║                                                           ║
    ║  Luego abrir: http://localhost:8089                       ║
    ║                                                           ║
    ║  Modo headless (CI):                                      ║
    ║    locust -f tests/load/locustfile.py --headless \\       ║
    ║        -u 50 -r 5 -t 5m \\                                ║
    ║        --host=http://localhost:8000 \\                    ║
    ║        --html=reports/load_test.html                      ║
    ║                                                           ║
    ║  Escenarios disponibles (--tags):                         ║
    ║    - smoke: Prueba básica rápida                          ║
    ║    - invoices: Solo operaciones de facturas               ║
    ║    - admin: Solo operaciones de administrador             ║
    ║    - health: Solo health checks                           ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
