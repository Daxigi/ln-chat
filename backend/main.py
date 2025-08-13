# main.py - API REST con FastAPI para Vanna
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from vanna_service import VannaChromaDB
from dotenv import load_dotenv
from datetime import datetime
import uvicorn
import logging
import os
import json
import numpy as np

# Configuración
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Crear aplicación FastAPI
app = FastAPI(
    title="Vanna AI API",
    description="API para consultas SQL inteligentes con Vanna AI",
    version="1.0.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instancia global de Vanna
vn = None


# ===== MODELOS PYDANTIC =====

class QuestionRequest(BaseModel):
    question: str

class TrainSQLRequest(BaseModel):
    question: str
    sql: str

class TrainDDLRequest(BaseModel):
    ddl: str

class TrainDocRequest(BaseModel):
    documentation: str

class TrainRequest(BaseModel):
    question: Optional[str] = None
    sql: Optional[str] = None
    ddl: Optional[str] = None
    documentation: Optional[str] = None

class SQLRequest(BaseModel):
    sql: str

class RestoreRequest(BaseModel):
    filename: str
    clear_before_restore: bool = True

class ClearRequest(BaseModel):
    confirmation: str

# ===== Limpiamos posibles inf o nan =====

def clean_non_json_values(data):
    """
    Recorre un diccionario o lista y reemplaza NaN, inf, -inf por None.
    """

    if isinstance(data, dict):
        return {k:clean_non_json_values(v) for k, v in data.items()}
    if isinstance(data, list):
        return [clean_non_json_values(i) for i in data]
    if isinstance(data, float) and (np.isnan(data) or np.isinf(data)):
        return None
    return data



# ===== EVENTOS DE INICIO =====

@app.on_event("startup")
async def startup_event():
    """Inicializa Vanna al iniciar la aplicación."""
    global vn
    try:
        vn = VannaChromaDB()
        logger.info("✅ Vanna inicializado correctamente")
    except Exception as e:
        logger.error(f"❌ Error inicializando Vanna: {e}")
        raise e


# ===== ENDPOINTS ESENCIALES =====

@app.get("/api/health")
async def health():
    """Verifica el estado del servicio."""
    if vn and vn.db_connection:
        return {
            "status": "healthy",
            "database_connected": True
        }
    else:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "database_connected": False
            }
        )


@app.post("/api/generate-sql")
async def generate_sql(request: QuestionRequest):
    """Genera SQL a partir de una pregunta en lenguaje natural."""
    try:
        question = request.question.strip()
        
        if not question:
            raise HTTPException(status_code=400, detail="La pregunta no puede estar vacía")
        
        sql = vn.generate_sql(question)
        
        return {
            "success": True,
            "question": question,
            "sql": sql
        }
        
    except Exception as e:
        logger.error(f"Error generando SQL: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/api/ask")
async def ask(request: QuestionRequest):
    """Genera SQL y ejecuta la consulta, retornando los resultados."""
    sql = None # Definir sql aquí para que esté disponible en el bloque except
    try:
        question = request.question.strip()
        
        if not question:
            raise HTTPException(status_code=400, detail="La pregunta no puede estar vacía")
        
        # Generar SQL
        sql = vn.generate_sql(question)
        
        # Ejecutar SQL
        df = vn.run_sql(sql)
        
        # Convertir DataFrame a JSON
        if df is not None:
            results = df.to_dict('records')
            
            # Limpia los resultados para que sean compatibles con JSON
            cleaned_results = clean_non_json_values(results)
            
            return {
                "success": True,
                "question": question,
                "sql": sql,
                "results": cleaned_results, # Usar los resultados limpios
                "row_count": len(df)
            }
        else:
            return {
                "success": False,
                "question": question,
                "sql": sql,
                "error": "Error ejecutando la consulta"
            }
            
    except Exception as e:
        logger.error(f"Error en ask: {e}")
        return {
            "success": False,
            "error": str(e),
            "sql": sql
        }

@app.post("/api/train")
async def train(request: TrainRequest):
    """Entrena el modelo con nuevos datos."""
    try:
        # Validar que al menos un tipo de entrenamiento esté presente
        if request.question and request.sql:
            doc_id = vn.train(question=request.question, sql=request.sql)
            return {
                "success": True,
                "type": "sql",
                "id": doc_id
            }
        elif request.ddl:
            doc_id = vn.train(ddl=vn.get_table_ddl(request.ddl))
            return {
                "success": True,
                "type": "ddl",
                "id": doc_id
            }
        elif request.documentation:
            doc_id = vn.train(documentation=request.documentation)
            return {
                "success": True,
                "type": "documentation",
                "id": doc_id
            }
        else:
            raise HTTPException(
                status_code=400,
                detail="Debe proporcionar: (question y sql), ddl, o documentation"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error entrenando: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/api/training-data/restore")
async def restore_from_backup(request: RestoreRequest):
    """
    Restaura el entrenamiento desde un archivo de backup JSON ESPECÍFICO.
    """
    backup_dir = "./backups"
    
    try:
        # --- LÓGICA SIMPLIFICADA ---
        # Ahora siempre usa el filename que viene en la solicitud.
        file_path = os.path.join(backup_dir, request.filename)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"Archivo de backup no encontrado: {request.filename}")

        logger.info(f"Iniciando restauración desde: {file_path}")

        # (Opcional) Limpiar el entrenamiento existente
        if request.clear_before_restore:
            logger.info("Limpiando datos de entrenamiento existentes...")
            training_data = vn.get_training_data()
            if not training_data.empty:
                ids_to_remove = training_data['id'].tolist()
                for doc_id in ids_to_remove:
                    vn.remove_training_data(id=doc_id)
            logger.info("Datos existentes eliminados.")

        # Leer el archivo de backup y re-entrenar
        with open(file_path, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)

        success_count = 0
        error_count = 0
        for record in backup_data:
            try:
                if record['type'] == 'sql':
                    vn.train(question=record['question'], sql=record['content'])
                elif record['type'] == 'ddl':
                    vn.train(ddl=record['content'])
                elif record['type'] == 'documentation':
                    vn.train(documentation=record['content'])
                success_count += 1
            except Exception as e:
                logger.error(f"Error restaurando registro {record.get('id')}: {e}")
                error_count += 1

        summary = f"Restauración completada. Exitosos: {success_count}, Errores: {error_count}."
        logger.info(summary)
        
        return {
            "success": True,
            "message": summary,
            "restored_from": file_path
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en el proceso de restauración: {e}")
        raise HTTPException(
            status_code=500,
            detail={"success": False, "error": str(e)}
        )

@app.get("/api/training-data")
async def get_training_data():
    """Obtiene todos los datos de entrenamiento."""
    try:
        df = vn.get_training_data()
        data = df.to_dict('records')
        
        return {
            "success": True,
            "count": len(data),
            "data": data
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo training data: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/api/training-data/backup")
async def backup_training_data():
    """
    Crea un backup de todos los datos de entrenamiento en un archivo JSON.
    """
    try:
        # 1. Definir la carpeta de backups
        backup_dir = "./backups"
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            logger.info(f"Creado directorio de backups en: {backup_dir}")

        # 2. Obtener todos los datos de entrenamiento
        logger.info("Obteniendo datos de entrenamiento para el backup...")
        df = vn.get_training_data()
        data = df.to_dict('records')
        
        # 3. Crear el archivo de backup con fecha y hora
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(backup_dir, f"vanna_backup_{timestamp}.json")
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        
        logger.info(f"✅ Backup creado exitosamente en: {file_path}")
        
        return {
            "success": True,
            "message": "Backup creado exitosamente.",
            "file_path": file_path,
            "record_count": len(data)
        }
        
    except Exception as e:
        logger.error(f"Error creando el backup: {e}")
        raise HTTPException(
            status_code=500,
            detail={"success": False, "error": str(e)}
        )

@app.delete("/api/training-data/clear-all")
async def clear_all_training_data(request: ClearRequest):
    """
    Elimina TODOS los datos de entrenamiento (DDL, Documentación y SQL).
    Requiere una confirmación explícita para proceder.
    """
    # 1. Medida de seguridad: Verificar el texto de confirmación
    required_confirmation_text = "BORRAR TODO"
    if request.confirmation != required_confirmation_text:
        raise HTTPException(
            status_code=400,
            detail=f"Confirmación incorrecta. Debes enviar exactamente el texto '{required_confirmation_text}'."
        )
        
    try:
        # 2. Obtener todos los IDs de los datos de entrenamiento existentes
        logger.info("Iniciando borrado de todos los datos de entrenamiento...")
        training_data = vn.get_training_data()
        
        if training_data.empty:
            logger.info("No hay datos de entrenamiento para borrar.")
            return {"success": True, "message": "No había datos de entrenamiento para borrar.", "deleted_count": 0}

        ids_to_remove = training_data['id'].tolist()
        
        # 3. Borrar cada registro uno por uno
        deleted_count = 0
        for doc_id in ids_to_remove:
            if vn.remove_training_data(id=doc_id):
                deleted_count += 1
        
        summary = f"Borrado completado. Se eliminaron {deleted_count} registros."
        logger.info(summary)
        
        return {
            "success": True,
            "message": summary,
            "deleted_count": deleted_count
        }

    except Exception as e:
        logger.error(f"Error durante el borrado masivo: {e}")
        raise HTTPException(
            status_code=500,
            detail={"success": False, "error": str(e)}
        )


@app.delete("/api/training-data/{id}")
async def remove_training_data(id: str):
    """Elimina un elemento del training data."""
    try:
        success = vn.remove_training_data(id)
        
        if success:
            return {
                "success": True,
                "message": f"Eliminado: {id}"
            }
        else:
            return {
                "success": False,
                "error": "No se pudo eliminar el elemento"
            }
            
    except Exception as e:
        logger.error(f"Error eliminando: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/api/run-sql")
async def run_sql(request: SQLRequest):
    """Ejecuta una consulta SQL directamente (útil para testing)."""
    try:
        sql = request.sql.strip()
        
        if not sql:
            raise HTTPException(status_code=400, detail="El SQL no puede estar vacío")
        
        df = vn.run_sql(sql)
        
        if df is not None:
            results = df.to_dict('records')
            return {
                "success": True,
                "results": results,
                "row_count": len(df)
            }
        else:
            return {
                "success": False,
                "error": "Error ejecutando SQL"
            }
            
    except Exception as e:
        logger.error(f"Error ejecutando SQL: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# ===== ENDPOINTS ADICIONALES ÚTILES =====

@app.get("/api/tables")
async def get_tables():
    """Obtiene la lista de tablas disponibles en la base de datos."""
    try:
        tables = vn.get_table_names()
        return {
            "success": True,
            "tables": tables,
            "count": len(tables)
        }
    except Exception as e:
        logger.error(f"Error obteniendo tablas: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/api/table/{table_name}")
async def get_table_schema(table_name: str):
    """Obtiene el esquema de una tabla específica."""
    try:
        ddl = vn.get_table_ddl(table_name)
        if ddl:
            return {
                "success": True,
                "table": table_name,
                "ddl": ddl
            }
        else:
            raise HTTPException(status_code=404, detail=f"Tabla '{table_name}' no encontrada")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo esquema de {table_name}: {e}")
        return {
            "success": False,
            "error": str(e)
        }



@app.post("/api/train/auto-ddl")
async def train_auto_ddl():
    """Entrena automáticamente con los DDLs de todas las tablas."""
    try:
        tables = vn.get_table_names()
        trained_count = 0
        errors = []
        
        for table in tables:
            try:
                vn.train_on_ddl_from_database([table])
                trained_count += 1
            except Exception as e:
                errors.append({"table": table, "error": str(e)})
        
        return {
            "success": True,
            "trained_tables": trained_count,
            "total_tables": len(tables),
            "errors": errors
        }
    except Exception as e:
        logger.error(f"Error en entrenamiento automático: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# ===== DOCUMENTACIÓN INTERACTIVA =====

@app.get("/", tags=["Root"])
async def root():
    """Endpoint raíz con información de la API."""
    return {
        "message": "🤖 Vanna AI API",
        "version": "1.0.0",
        "documentation": "/docs",
        "endpoints": {
            "health": "/api/health",
            "generate_sql": "/api/generate-sql",
            "ask": "/api/ask",
            "train": "/api/train",
            "training_data": "/api/training-data",
            "run_sql": "/api/run-sql",
            "tables": "/api/tables"
        }
    }


# ===== INICIALIZACIÓN =====

if __name__ == '__main__':
    print("""
    ╔══════════════════════════════════════════════════════╗
    ║             🤖 VANNA AI API - FastAPI 🤖             ║
    ╚══════════════════════════════════════════════════════╝
    """)
    
    print("🚀 Iniciando API de Vanna...")
    print("\n📡 Endpoints disponibles:")
    print("  GET    /api/health             - Estado del servicio")
    print("  POST   /api/generate-sql       - Generar SQL desde pregunta")
    print("  POST   /api/ask                - Generar SQL y ejecutar")
    print("  POST   /api/train              - Entrenar con nuevos datos")
    print("  GET    /api/training-data      - Ver datos de entrenamiento")
    print("  DELETE /api/training-data/<id> - Eliminar dato de entrenamiento")
    print("  POST   /api/run-sql            - Ejecutar SQL directamente")
    print("  GET    /api/tables             - Listar tablas disponibles")
    print("  GET    /api/table/<name>       - Ver esquema de tabla")
    print("  POST   /api/train/auto-ddl     - Entrenar con DDLs automáticamente")
    print("\n📚 Documentación interactiva disponible en:")
    print("  http://localhost:8000/docs     - Swagger UI")
    print("  http://localhost:8000/redoc    - ReDoc")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )