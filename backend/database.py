# backend/database.py - Helper para conexión a MySQL
import os
import pymysql
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    """Obtiene una conexión a la base de datos MySQL"""
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE"),
        port=int(os.getenv("MYSQL_PORT", 3306)),
        cursorclass=pymysql.cursors.DictCursor
    )

def test_connection():
    """Prueba la conexión a la base de datos"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT DATABASE()")
            result = cursor.fetchone()
            print(f"✅ Conectado a: {result['DATABASE()']}")
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return False

if __name__ == "__main__":
    test_connection()