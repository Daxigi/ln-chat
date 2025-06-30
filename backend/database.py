# backend/database.py
import pymysql
from pymysql.connections import Connection
from pymysql.cursors import DictCursor
import os
from dotenv import load_dotenv
import logging
from typing import Optional
from contextlib import contextmanager
import time

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseConnectionPool:
    """Pool de conexiones para manejar mejor las conexiones MySQL"""
    
    def __init__(self):
        self.connection_params = {
            'host': os.getenv("MYSQL_HOST", "localhost"),
            'user': os.getenv("MYSQL_USER", "root"),
            'password': os.getenv("MYSQL_PASSWORD", ""),
            'database': os.getenv("MYSQL_DATABASE", "digitalform"),
            'port': int(os.getenv("MYSQL_PORT", 3306)),
            'charset': 'utf8mb4',
            'cursorclass': DictCursor,
            'autocommit': True,
            'connect_timeout': 10
        }
        self._connection = None
        self._last_ping = 0
        self.ping_interval = 300  # Ping cada 5 minutos
    
    def _create_connection(self) -> Connection:
        """Crea una nueva conexión a la base de datos"""
        try:
            logger.info("Creando nueva conexión a MySQL...")
            conn = pymysql.connect(**self.connection_params)
            logger.info("✅ Conexión establecida correctamente")
            return conn
        except Exception as e:
            logger.error(f"❌ Error creando conexión: {e}")
            raise
    
    def _ensure_connected(self, conn: Connection) -> Connection:
        """Asegura que la conexión esté activa"""
        try:
            # Verificar si necesitamos hacer ping
            current_time = time.time()
            if current_time - self._last_ping > self.ping_interval:
                conn.ping(reconnect=True)
                self._last_ping = current_time
                logger.debug("Ping exitoso a la base de datos")
            return conn
        except Exception as e:
            logger.warning(f"Conexión perdida, reconectando: {e}")
            return self._create_connection()
    
    def get_connection(self) -> Connection:
        """Obtiene una conexión activa del pool"""
        if self._connection is None:
            self._connection = self._create_connection()
        
        # Asegurar que la conexión esté activa
        self._connection = self._ensure_connected(self._connection)
        return self._connection
    
    def close_connection(self):
        """Cierra la conexión actual si existe"""
        if self._connection:
            try:
                self._connection.close()
                logger.info("Conexión cerrada")
            except:
                pass
            finally:
                self._connection = None

# Instancia global del pool
connection_pool = DatabaseConnectionPool()

def get_db_connection() -> Connection:
    """
    Obtiene una conexión a la base de datos con manejo de errores mejorado
    """
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            conn = connection_pool.get_connection()
            return conn
        except Exception as e:
            logger.error(f"Intento {attempt + 1}/{max_retries} falló: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2  # Backoff exponencial
            else:
                raise Exception(f"No se pudo conectar a la base de datos después de {max_retries} intentos: {str(e)}")

@contextmanager
def get_db_cursor(dict_cursor=True):
    """
    Context manager para obtener un cursor de base de datos
    Maneja automáticamente la apertura y cierre del cursor
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor_class = DictCursor if dict_cursor else None
        cursor = conn.cursor(cursor_class)
        yield cursor
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error en operación de base de datos: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        # No cerramos la conexión aquí porque es del pool

def test_connection() -> bool:
    """
    Prueba la conexión a la base de datos
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            return result is not None
    except Exception as e:
        logger.error(f"Error probando conexión: {e}")
        return False

def execute_query(query: str, params: tuple = None) -> list:
    """
    Ejecuta una consulta SELECT y retorna los resultados
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error ejecutando query: {e}")
        raise

def execute_query_single(query: str, params: tuple = None) -> Optional[dict]:
    """
    Ejecuta una consulta SELECT y retorna un solo resultado
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()
    except Exception as e:
        logger.error(f"Error ejecutando query: {e}")
        raise

# Función para limpiar conexiones al cerrar la aplicación
def cleanup():
    """Limpia las conexiones del pool"""
    connection_pool.close_connection()
    logger.info("Pool de conexiones cerrado")

# Para compatibilidad con código existente
def close_db_connection(conn):
    """
    Función legacy para cerrar conexión
    Con el pool, no necesitamos cerrar conexiones individuales
    """
    pass  # No hacemos nada porque el pool maneja las conexiones