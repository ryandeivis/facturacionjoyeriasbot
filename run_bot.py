"""
Script de inicio del bot

Ejecuta el bot desde la raíz del proyecto.
"""

import sys
from pathlib import Path

# Agregar el directorio actual al path
sys.path.insert(0, str(Path(__file__).parent))

# Importar y ejecutar el bot
from src.bot.main import main

if __name__ == '__main__':
    main()