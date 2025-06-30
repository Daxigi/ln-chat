# create_user.py
import sqlite3
import os
from passlib.context import CryptContext

# --- CONFIGURACIÓN ---
# Es crucial usar el mismo contexto de encriptación que tu API de login.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
DB_FILE = "users.db"
TABLE_NAME = "users"

def get_password_hash(password):
    """Genera el hash de una contraseña."""
    return pwd_context.hash(password)

def create_database_and_table():
    """Crea el archivo de la base de datos y la tabla de usuarios si no existen."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # --- SOLUCIÓN AÑADIDA ---
        # Borramos la tabla si ya existe para asegurar un esquema limpio.
        # Esto es seguro para este script porque su único propósito es crear/resetear usuarios.
        cursor.execute(f"DROP TABLE IF EXISTS {TABLE_NAME};")
        
        # Crear la tabla de usuarios con el esquema correcto
        cursor.execute(f"""
        CREATE TABLE {TABLE_NAME} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            hashed_password TEXT NOT NULL,
            role TEXT DEFAULT 'user'
        );
        """)
        
        conn.commit()
        conn.close()
        print(f"✅ Base de datos '{DB_FILE}' y tabla '{TABLE_NAME}' listas.")
    except Exception as e:
        print(f"❌ Error al crear la base de datos: {e}")

def create_admin_user(username, password):
    """Crea o actualiza el usuario administrador con una nueva contraseña."""
    hashed_password = get_password_hash(password)
    
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Usar INSERT OR REPLACE para crear el usuario o actualizar su contraseña si ya existe
        # Esto es útil para poder correr el script varias veces si olvidas la contraseña.
        cursor.execute(f"""
        INSERT OR REPLACE INTO {TABLE_NAME} (username, hashed_password, role) 
        VALUES (?, ?, ?);
        """, (username, hashed_password, 'admin'))
        
        conn.commit()
        conn.close()
        
        print("\n" + "="*50)
        print(f"🎉 ¡Usuario '{username}' creado/actualizado exitosamente!")
        print(f"   - Usuario: {username}")
        print(f"   - Contraseña: {password}")
        print("="*50)
        
    except sqlite3.IntegrityError:
        print(f"⚠️ El usuario '{username}' ya existe.")
    except Exception as e:
        print(f"❌ Error al crear el usuario: {e}")

if __name__ == "__main__":
    print("--- Iniciando la creación del usuario administrador ---")
    create_database_and_table()
    
    # --- DATOS DEL USUARIO A CREAR ---
    ADMIN_USERNAME = "admin"
    ADMIN_PASSWORD = "admin123"
    
    create_admin_user(ADMIN_USERNAME, ADMIN_PASSWORD)
    print("\nScript finalizado.")
