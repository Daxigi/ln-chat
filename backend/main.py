# main.py - API REST con FastAPI para Vanna
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
from vanna_service import VannaChromaDB
from dotenv import load_dotenv
import uvicorn

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
            return {
                "success": True,
                "question": question,
                "sql": sql,
                "results": results,
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
            "error": str(e)
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
            doc_id = vn.train(ddl=request.ddl)
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