#!/usr/bin/env python3
"""
Script para ejecutar el Dashboard de Estadísticas

Uso:
    python scripts/run_dashboard.py

Opciones:
    --port PORT     Puerto del servidor (default: 8501)
    --host HOST     Host del servidor (default: localhost)
"""

import subprocess
import sys
import os
from pathlib import Path

# Directorio raíz del proyecto
ROOT_DIR = Path(__file__).parent.parent
os.chdir(ROOT_DIR)


def main():
    """Ejecuta el dashboard de Streamlit."""
    import argparse

    parser = argparse.ArgumentParser(description="Ejecutar Dashboard de Estadísticas")
    parser.add_argument("--port", type=int, default=8501, help="Puerto del servidor")
    parser.add_argument("--host", type=str, default="localhost", help="Host del servidor")
    args = parser.parse_args()

    dashboard_path = ROOT_DIR / "src" / "dashboard" / "app.py"

    if not dashboard_path.exists():
        print(f"Error: No se encontró el archivo {dashboard_path}")
        sys.exit(1)

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           💎 JEWELRY INVOICE - DASHBOARD                     ║
╠══════════════════════════════════════════════════════════════╣
║  Iniciando dashboard en:                                     ║
║  http://{args.host}:{args.port}                                       ║
║                                                              ║
║  Presiona Ctrl+C para detener                                ║
╚══════════════════════════════════════════════════════════════╝
    """)

    # Ejecutar Streamlit
    cmd = [
        sys.executable, "-m", "streamlit", "run",
        str(dashboard_path),
        "--server.port", str(args.port),
        "--server.address", args.host,
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false"
    ]

    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n\n✅ Dashboard detenido correctamente")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error al ejecutar dashboard: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
