"""
Script para crear usuarios iniciales

Ejecutar una vez para crear usuarios de prueba.
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.connection import init_db, create_tables, get_db
from src.database.models import User
from src.utils.crypto import hash_password
from config.constants import UserRole


def create_initial_users():
    """Crea usuarios iniciales para el sistema"""

    # Inicializar base de datos
    print("Inicializando base de datos...")
    init_db()
    create_tables()

    # Usuarios a crear
    usuarios = [
        {
            "cedula": "1111111111",
            "nombre_completo": "Admin Joyeria",
            "email": "admin@joyeria.com",
            "telefono": "+573001111111",
            "password_hash": hash_password("Admin123!"),
            "rol": UserRole.ADMIN.value,
            "activo": True
        },
        {
            "cedula": "2222222222",
            "nombre_completo": "Vendedor Demo",
            "email": "vendedor@joyeria.com",
            "telefono": "+573002222222",
            "password_hash": hash_password("Venta456!"),
            "rol": UserRole.VENDEDOR.value,
            "activo": True
        },
        {
            "cedula": "3333333333",
            "nombre_completo": "Maria Vendedora",
            "email": "maria@joyeria.com",
            "telefono": "+573003333333",
            "password_hash": hash_password("Maria789!"),
            "rol": UserRole.VENDEDOR.value,
            "activo": True
        }
    ]

    # Crear usuarios
    db = next(get_db())

    for user_data in usuarios:
        # Verificar si ya existe
        existing = db.query(User).filter(User.cedula == user_data["cedula"]).first()

        if existing:
            print(f"  Usuario {user_data['cedula']} ya existe, omitiendo...")
            continue

        user = User(**user_data)
        db.add(user)
        print(f"  Creado: {user_data['nombre_completo']} ({user_data['rol']})")

    db.commit()
    db.close()

    print("\n" + "=" * 50)
    print("USUARIOS CREADOS")
    print("=" * 50)
    print("\nAdmin:")
    print("  Cédula: 1111111111")
    print("  Password: Admin123!")
    print("\nVendedor 1:")
    print("  Cédula: 2222222222")
    print("  Password: Venta456!")
    print("\nVendedor 2:")
    print("  Cédula: 3333333333")
    print("  Password: Maria789!")
    print("\n" + "=" * 50)


if __name__ == '__main__':
    create_initial_users()