# backend/main.py
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# Importar servicios locales
from auth import authenticate_user, create_access_token, get_current_user, get_password_hash
from database import get_db_connection, test_connection
from vanna_service import VannaService

# Cargar variables de entorno
load_dotenv()

# Inicializar FastAPI
app = FastAPI(
    title="API de Consultas Inteligentes",
    description="Backend con Vanna.ai para consultas SQL naturales",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],  # Streamlit
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializar servicio de Vanna
vanna_service = VannaService()

# Modelos Pydantic
class QueryRequest(BaseModel):
    query: str

class ChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = None

class TrainingRequest(BaseModel):
    training_type: str  # 'ddl', 'documentation', 'sql'
    question: Optional[str] = None
    sql: Optional[str] = None
    ddl: Optional[str] = None
    documentation: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

# Usuarios de prueba (en producción usar BD)
fake_users_db = {
    "admin": {
        "username": "admin",
        "hashed_password": get_password_hash("admin123"),
    }
}

@app.post("/auth/login", summary="Generar un token de acceso")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # La clase OAuth2PasswordRequestForm tiene los campos .username y .password
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token_expires = timedelta(minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 120)))
    
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}
# Endpoints de Estado
@app.get("/health")
async def health_check():
    """Verificar estado del sistema"""
    mysql_status = test_connection()
    vanna_status = vanna_service.is_connected()
    
    return {
        "status": "ok",
        "mysql_connected": mysql_status,
        "mindsdb_connected": vanna_status,  # Mantengo el nombre para compatibilidad con frontend
        "vanna_connected": vanna_status,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/vanna/training-data", summary="Obtener todos los datos de entrenamiento de Vanna")
async def get_training_data(current_user: dict = Depends(get_current_user)):
    """
    Devuelve una lista de todos los fragmentos de conocimiento (DDL, docs, SQL)
    con los que Vanna ha sido entrenado.
    """
    try:
        data = vanna_service.get_all_training_data()
        return {"success": True, "count": len(data), "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Endpoints de MySQL
@app.get("/mysql/tables")
async def get_tables(current_user: dict = Depends(get_current_user)):
    """Obtener lista de tablas"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES")
        tables = [table[0] for table in cursor.fetchall()]
        cursor.close()
        conn.close()
        return {"tables": tables}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/mysql/table/{table_name}")
async def get_table_structure(table_name: str, current_user: dict = Depends(get_current_user)):
    """Obtener estructura de una tabla"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"DESCRIBE {table_name}")
        structure = cursor.fetchall()
        cursor.close()
        conn.close()
        return {"data": structure}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/vanna/debug-prompt", summary="[DEBUG] Ver el prompt enviado a OpenAI")
async def debug_vanna_prompt(request: QueryRequest, current_user: dict = Depends(get_current_user)):
    """
    Endpoint de depuración para ver el contexto y el prompt completo que Vanna 
    construye para una pregunta específica antes de enviarlo a OpenAI.
    """
    try:
        debug_info = vanna_service.generate_prompt(request.query)
        return debug_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/mysql/query")
async def execute_query(request: QueryRequest, current_user: dict = Depends(get_current_user)):
    """Ejecutar query SQL directamente"""
    try:
        # Validación básica de seguridad
        query_upper = request.query.upper()
        dangerous_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE']
        if any(keyword in query_upper for keyword in dangerous_keywords):
            raise HTTPException(status_code=400, detail="Operación no permitida")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(request.query)
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "data": results,
            "query": request.query
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "query": request.query
        }

# Endpoints de Vanna/MindsDB (mantengo el nombre para compatibilidad)
@app.post("/mindsdb/chat")
async def chat_with_vanna(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    """Hacer preguntas en lenguaje natural"""
    try:
        # Generar SQL desde pregunta natural
        sql = vanna_service.generate_sql(request.query)
        
        if not sql:
            return {
                "success": False,
                "answer": "No pude generar una consulta SQL para tu pregunta. ¿Podrías reformularla?",
                "sql": None
            }
        
        # Ejecutar SQL
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(sql)
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Generar respuesta natural - siempre usar el método mejorado
        answer = vanna_service.generate_summary(request.query, sql, results)
        
        # Si no hay resumen generado (por error), crear fallback mejorado
        if not answer:
            if not results:
                answer = "No encontré resultados para tu consulta. Parece que no hay datos que coincidan con lo que buscas."
            elif len(results) == 1:
                # Para resultados únicos
                if isinstance(results[0], dict) and len(results[0]) == 1:
                    value = list(results[0].values())[0]
                    answer = f"Según los datos disponibles, el resultado es: {value}"
                else:
                    answer = f"Encontré un registro con la siguiente información: {results[0]}"
            else:
                answer = f"Encontré {len(results)} registros que coinciden con tu búsqueda."
                if len(results) <= 5:
                    answer += " Aquí están todos los resultados:"
                    for i, row in enumerate(results):
                        answer += f"\n{i+1}. {row}"
                else:
                    answer += " Te muestro los primeros 5:"
                    for i, row in enumerate(results[:5]):
                        answer += f"\n{i+1}. {row}"
        
        return {
            "success": True,
            "answer": answer,
            "sql": sql,
            "raw_results": results[:10] if results else []  # Limitar resultados
        }
        
    except Exception as e:
        return {
            "success": False,
            "answer": f"Ocurrió un error al procesar tu pregunta: {str(e)}",
            "sql": None,
            "error": str(e)
        }

# Endpoints de Entrenamiento de Vanna
@app.post("/vanna/train")
async def train_vanna(request: TrainingRequest, current_user: dict = Depends(get_current_user)):
    """Entrenar Vanna con nuevos ejemplos"""
    try:
        result = False
        
        if request.training_type == "ddl" and request.ddl:
            result = vanna_service.train_ddl(request.ddl)
        elif request.training_type == "documentation" and request.documentation:
            result = vanna_service.train_documentation(request.documentation)
        elif request.training_type == "sql" and request.question and request.sql:
            result = vanna_service.train_sql(request.question, request.sql)
        else:
            raise HTTPException(status_code=400, detail="Parámetros de entrenamiento inválidos")
        
        if result:
            return {"success": True, "message": "Entrenamiento completado"}
        else:
            return {"success": False, "message": "Error en el entrenamiento"}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/vanna/training-data")
async def get_training_data(current_user: dict = Depends(get_current_user)):
    """Obtener datos de entrenamiento actuales"""
    try:
        data = vanna_service.get_training_data()
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/vanna/remove-training")
async def remove_training(training_id: str, current_user: dict = Depends(get_current_user)):
    """Eliminar un dato de entrenamiento"""
    try:
        result = vanna_service.remove_training(training_id)
        if result:
            return {"success": True, "message": "Dato de entrenamiento eliminado"}
        else:
            return {"success": False, "message": "No se pudo eliminar el dato"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Endpoint de inicio
@app.get("/")
async def root():
    return {
        "message": "API de Consultas Inteligentes con Vanna.ai",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "auth": "/auth/login"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)