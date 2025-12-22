"""Modelos Pydantic para validación"""
from src.models.user import UserBase, UserCreate, UserInDB
from src.models.invoice import InvoiceItem, InvoiceCreate, InvoiceResponse, N8NResponse