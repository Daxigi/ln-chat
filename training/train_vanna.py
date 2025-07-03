# training/train_vanna.py - Versión Modificada y Configurable
import os
import sys
import logging
import shutil
from dotenv import load_dotenv
import time

# --- CONFIGURACIÓN INICIAL ---
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.environ['ANONYMIZED_TELEMETRY'] = 'False'

from vanna_service import LocalVannaService
# --- NUEVO: Importar la configuración de entrenamiento ---
from training import SELECTED_TABLES, DOCUMENTATION, SQL_EXAMPLES

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("VannaTrainer")


# --- CLASE DEL ENTRENADOR ---
class VannaTrainer:
    def __init__(self, service_instance):
        self.vanna_service = service_instance
        self.stats = {"tables_trained": 0, "docs_trained": 0, "queries_trained": 0, "errors": 0}

    # --- MODIFICADO: Acepta una lista de nombres de tablas ---
    def train_schema(self, table_names):
        """Entrena a Vanna con una lista específica de tablas de la base de datos."""
        logger.info("--- FASE 1: Entrenando Esquema de Base de Datos (Tablas Seleccionadas) ---")
        
        if not table_names:
            logger.warning("No se proporcionaron tablas en la configuración para entrenar.")
            return

        logger.info(f"Se entrenarán {len(table_names)} tablas seleccionadas: {', '.join(table_names)}")

        for name in table_names:
            try:
                # Obtener el DDL para la tabla específica
                ddl_df = self.vanna_service.run_sql(f"SHOW CREATE TABLE `{name}`")
                
                if ddl_df is not None and not ddl_df.empty:
                    ddl = ddl_df.iloc[0, 1]
                    if self.vanna_service.train(ddl=ddl):
                        self.stats["tables_trained"] += 1
                    else:
                        self.stats["errors"] += 1
                        logger.warning(f"Fallo al entrenar DDL para la tabla: {name}")
                else:
                    self.stats["errors"] += 1
                    logger.error(f"No se pudo obtener el DDL para la tabla: {name}. ¿Existe la tabla?")

                time.sleep(0.1) # Pequeña pausa
            except Exception as e:
                logger.error(f"Error crítico entrenando la tabla '{name}': {e}")
                self.stats["errors"] += 1
        
        logger.info(f"✅ {self.stats['tables_trained']} de {len(table_names)} esquemas de tabla entrenados.")

    def train_documentation(self, docs):
        """Entrena con una lista de documentos de texto."""
        logger.info("--- FASE 2: Entrenando Documentación de Negocio ---")
        if not docs:
            logger.warning("No se proporcionó documentación para entrenar.")
            return
        for doc in docs:
            if self.vanna_service.train(documentation=doc):
                self.stats["docs_trained"] += 1
            else:
                self.stats["errors"] += 1
        logger.info(f"✅ {self.stats['docs_trained']} documentos entrenados.")

    def train_sql_queries(self, queries):
        """Entrena con una lista de pares pregunta-SQL."""
        logger.info("--- FASE 3: Entrenando Ejemplos de Consultas SQL ---")
        if not queries:
            logger.warning("No se proporcionaron consultas SQL de ejemplo para entrenar.")
            return
        for q in queries:
            if self.vanna_service.train(question=q['question'], sql=q['sql']):
                self.stats['queries_trained'] += 1
            else:
                self.stats["errors"] += 1
        logger.info(f"✅ {self.stats['queries_trained']} ejemplos de SQL entrenados.")

    def run(self):
        """Ejecuta todas las fases del entrenamiento usando la configuración importada."""
        if not self.vanna_service.connected:
            logger.error("No se puede iniciar el entrenamiento. VannaService no está conectado.")
            return
        
        # --- MODIFICADO: Usar los datos importados del archivo de configuración ---
        self.train_schema(SELECTED_TABLES)
        self.train_documentation(DOCUMENTATION)
        self.train_sql_queries(SQL_EXAMPLES)
        
        # --- Resumen Final (sin cambios) ---
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


# --- BLOQUE PRINCIPAL DE EJECUCIÓN (sin cambios) ---
if __name__ == "__main__":
    load_dotenv()
    
    print("=" * 50)
    print("INICIANDO PROCESO DE ENTRENAMIENTO DE VANNA")
    print("=" * 50)
    
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
    
    logger.info("Creando instancia de VannaService...")
    service_instance = LocalVannaService()
    
    trainer = VannaTrainer(service_instance)
    trainer.run()