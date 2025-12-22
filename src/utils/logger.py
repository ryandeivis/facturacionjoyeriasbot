"""
Sistema de Logging

Configura el logging para toda la aplicación con:
- Salida a consola (INFO+)
- Archivo rotativo para logs generales
- Archivo rotativo para errores
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def get_logger(name: str) -> logging.Logger:
    """
    Obtiene un logger configurado para el módulo especificado.

    Args:
        name: Nombre del módulo (típicamente __name__)

    Returns:
        Logger configurado
    """
    logger = logging.getLogger(name)

    # Solo configurar si no tiene handlers
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)

        # Formato de log
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)d] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Handler de consola
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # Crear directorio de logs si no existe
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)

        # Handler de archivo general (rotativo)
        file_handler = RotatingFileHandler(
            logs_dir / "app.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Handler de errores (rotativo)
        error_handler = RotatingFileHandler(
            logs_dir / "errors.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        logger.addHandler(error_handler)

    return logger