# training/train_vanna.py - Versión Final y Robusta
import os
import sys
import logging
import shutil
from dotenv import load_dotenv
import time

# --- CONFIGURACIÓN INICIAL ---
# Agregar el directorio backend al path para encontrar el servicio
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

# Desactivar la telemetría de ChromaDB para un log más limpio
os.environ['ANONYMIZED_TELEMETRY'] = 'False'

# Importar el servicio DESPUÉS de configurar el path
from vanna_service import LocalVannaService 

# Configurar un logger específico para este script
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("VannaTrainer")


# --- CLASE DEL ENTRENADOR ---
class VannaTrainer:
    def __init__(self, service_instance):
        """Inicializa el entrenador con una instancia activa del servicio Vanna."""
        self.vanna_service = service_instance
        self.stats = {
            "tables_trained": 0,
            "docs_trained": 0,
            "queries_trained": 0,
            "errors": 0
        }

    def train_schema(self):
        """Entrena a Vanna con el esquema completo de la base de datos."""
        logger.info("--- FASE 1: Entrenando Esquema de Base de Datos ---")
        try:
            # Usar el método público run_sql del servicio
            tables_df = self.vanna_service.run_sql("SHOW TABLES")
            if tables_df is None or tables_df.empty:
                logger.error("No se pudieron obtener las tablas de la base de datos.")
                self.stats["errors"] += 1
                return

            table_names = tables_df.iloc[:, 0].tolist()
            logger.info(f"Se encontraron {len(table_names)} tablas. Entrenando...")

            for name in table_names:
                ddl_df = self.vanna_service.run_sql(f"SHOW CREATE TABLE `{name}`")
                if ddl_df is not None and not ddl_df.empty:
                    ddl = ddl_df.iloc[0, 1]
                    # Usar el método genérico train() correctamente
                    if self.vanna_service.train(ddl=ddl):
                        self.stats["tables_trained"] += 1
                    else:
                        self.stats["errors"] += 1
                        logger.warning(f"Fallo al entrenar DDL para la tabla: {name}")
                time.sleep(0.1) # Pequeña pausa para no saturar las APIs
            
            logger.info(f"✅ {self.stats['tables_trained']} de {len(table_names)} esquemas de tabla entrenados.")

        except Exception as e:
            logger.error(f"Error crítico durante el entrenamiento del esquema: {e}")
            self.stats["errors"] += 1

    def train_documentation(self, docs):
        """Entrena con una lista de documentos de texto."""
        logger.info("--- FASE 2: Entrenando Documentación de Negocio ---")
        for doc in docs:
            if self.vanna_service.train(documentation=doc):
                self.stats["docs_trained"] += 1
            else:
                self.stats["errors"] += 1
        logger.info(f"✅ {self.stats['docs_trained']} documentos entrenados.")

    def train_sql_queries(self, queries):
        """Entrena con una lista de pares pregunta-SQL."""
        logger.info("--- FASE 3: Entrenando Ejemplos de Consultas SQL ---")
        for q in queries:
            if self.vanna_service.train(question=q['question'], sql=q['sql']):
                self.stats['queries_trained'] += 1
            else:
                self.stats["errors"] += 1
        logger.info(f"✅ {self.stats['queries_trained']} ejemplos de SQL entrenados.")

    def run(self):
        """Ejecuta todas las fases del entrenamiento."""
        if not self.vanna_service.connected:
            logger.error("No se puede iniciar el entrenamiento. VannaService no está conectado.")
            return
        
        # --- Contenido del Entrenamiento ---
        documentation_to_train = [
            "La tabla `users` contiene todos los usuarios del sistema. El rol se encuentra en `current_role`.",
            "La tabla `procedures` define los tipos de trámites disponibles en la plataforma.",
            "La tabla `requests` guarda cada solicitud o trámite iniciado por un usuario."
        ]
        
        sql_examples_to_train = [
            {"question": "¿Cuántos usuarios hay?", "sql": "SELECT COUNT(*) FROM users"},
            {"question": "¿Cuáles son los 5 trámites más recientes?", "sql": "SELECT * FROM requests ORDER BY created_at DESC LIMIT 5"},
            {"question": "Muéstrame los usuarios administradores", "sql": "SELECT * FROM users WHERE current_role = 'admin'"}
        ]
        
        self.train_schema()
        self.train_documentation(documentation_to_train)
        self.train_sql_queries(sql_examples_to_train)
        
        # --- Resumen Final ---
        print("\n" + "="*50)
        logger.info("RESUMEN FINAL DEL ENTRENAMIENTO")
        logger.info(f"Tablas (DDL): {self.stats['tables_trained']}")
        logger.info(f"Documentación: {self.stats['docs_trained']}")
        logger.info(f"Consultas SQL: {self.stats['queries_trained']}")
        logger.info(f"Errores Totales: {self.stats['errors']}")
        print("="*50)
        
        if self.stats["errors"] == 0:
            logger.info("🎉 ¡Entrenamiento completado exitosamente!")
        else:
            logger.warning("⚠️  El entrenamiento finalizó con errores.")


# --- BLOQUE PRINCIPAL DE EJECUCIÓN ---
if __name__ == "__main__":
    load_dotenv()
    
    print("=" * 50)
    print("INICIANDO PROCESO DE ENTRENAMIENTO DE VANNA")
    print("=" * 50)
    
    # 1. Limpiar el entrenamiento anterior si el usuario lo desea
    chroma_path = os.path.abspath(os.getenv("VANNA_VECTOR_DB_PATH", "chroma_db"))
    if os.path.exists(chroma_path):
        response = input(f"\nSe encontró un entrenamiento anterior.\n¿Deseas eliminarlo y empezar de cero? (s/n): ")
        if response.lower() == 's':
            try:
                shutil.rmtree(chroma_path)
                logger.info(f"✅ Directorio de entrenamiento anterior eliminado.")
            except Exception as e:
                logger.error(f"No se pudo eliminar el directorio: {e}")
                sys.exit(1)
    
    # 2. Inicializar el servicio UNA SOLA VEZ
    logger.info("Creando instancia de VannaService...")
    service_instance = LocalVannaService()
    
    # 3. Crear el entrenador y ejecutarlo
    trainer = VannaTrainer(service_instance)
    trainer.run()
