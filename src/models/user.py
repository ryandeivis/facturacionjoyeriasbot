"""
Modelos Pydantic de Usuario

Schemas para validación de datos de usuario.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

from config.constants import UserRole


class UserBase(BaseModel):
    """Schema base de usuario"""
    cedula: str = Field(..., min_length=7, max_length=15)
    nombre_completo: str = Field(..., min_length=3, max_length=200)
    email: Optional[EmailStr] = None
    telefono: Optional[str] = None
    rol: UserRole


class UserCreate(UserBase):
    """Schema para crear usuario"""
    password: str = Field(..., min_length=8)


class UserInDB(UserBase):
    """Schema de usuario en base de datos"""
    id: int
    password_hash: str
    telegram_id: Optional[int] = None
    activo: bool = True
    fecha_creacion: datetime
    ultimo_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserResponse(UserBase):
    """Schema de respuesta (sin password)"""
    id: int
    activo: bool
    fecha_creacion: datetime
    ultimo_login: Optional[datetime] = None

    class Config:
        from_attributes = True