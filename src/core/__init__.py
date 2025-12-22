"""
Core Module

Contiene el contexto de aplicación y dependency injection.
"""

from src.core.context import AppContext, get_app_context

__all__ = ["AppContext", "get_app_context"]