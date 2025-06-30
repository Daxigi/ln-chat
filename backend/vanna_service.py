# backend/vanna_service_alt.py - Implementación alternativa 100% local
import os
import logging
from dotenv import load_dotenv
import openai
import chromadb
import pymysql
import pandas as pd
from typing import Optional, List, Dict, Any
from chromadb.utils import embedding_functions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

class LocalVannaService:
    """Implementación local sin dependencia de servidores Vanna"""
    
    def __init__(self):
        self.client = None
        self.collection = None
        self.connection = None
        self.connected = False
        
        # Configurar OpenAI
        openai.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("VANNA_MODEL", "gpt-4o-mini")
        
        # Inicializar ChromaDB local
        self.init_chromadb()
        
        # Conectar a MySQL
        if self.connect_to_mysql():
            self.connected = True
            logger.info("✅ Servicio inicializado correctamente")
    
    def init_chromadb(self):
        """Inicializa ChromaDB localmente usando embeddings de OpenAI."""
        try:
            chroma_path = os.getenv("VANNA_VECTOR_DB_PATH", "./chroma_db")
            self.client = chromadb.PersistentClient(path=chroma_path)

            # --- INICIO DE CAMBIOS ---

            # 1. Crear la función de embedding de OpenAI
            openai_ef = embedding_functions.OpenAIEmbeddingFunction(
                api_key=os.getenv("OPENAI_API_KEY"),
                model_name="text-embedding-3-small"  # Modelo recomendado: potente y económico
            )

            # 2. Asignar la función al crear la colección
            self.collection = self.client.get_or_create_collection(
                name="vanna_training_openai",  # Un nuevo nombre para evitar conflictos
                metadata={"hnsw:space": "cosine"},
                embedding_function=openai_ef  # ¡La clave está aquí!
            )

            # --- FIN DE CAMBIOS ---

            logger.info(f"✅ ChromaDB inicializado en {chroma_path} con embeddings de OpenAI")
        except Exception as e:
            logger.error(f"Error inicializando ChromaDB: {e}")

    def connect_to_mysql(self) -> bool:
        """Conecta a MySQL"""
        try:
            self.connection = pymysql.connect(
                host=os.getenv("MYSQL_HOST"),
                user=os.getenv("MYSQL_USER"),
                password=os.getenv("MYSQL_PASSWORD"),
                database=os.getenv("MYSQL_DATABASE"),
                port=int(os.getenv("MYSQL_PORT", 3306)),
                cursorclass=pymysql.cursors.DictCursor
            )
            logger.info("✅ Conectado a MySQL")
            return True
        except Exception as e:
            logger.error(f"Error conectando a MySQL: {e}")
            return False
    
    def train(self, **kwargs) -> bool:
        """Entrena el modelo con DDL, documentación o pares pregunta-SQL"""
        try:
            if not self.collection:
                return False
                
            # Generar ID único
            import uuid
            doc_id = str(uuid.uuid4())
            
            if 'ddl' in kwargs:
                # Entrenar con DDL
                self.collection.add(
                    documents=[kwargs['ddl']],
                    metadatas=[{"type": "ddl"}],
                    ids=[doc_id]
                )
                logger.info("✅ DDL agregado al entrenamiento")
                
            elif 'documentation' in kwargs:
                # Entrenar con documentación
                self.collection.add(
                    documents=[kwargs['documentation']],
                    metadatas=[{"type": "documentation"}],
                    ids=[doc_id]
                )
                logger.info("✅ Documentación agregada")
                
            elif 'question' in kwargs and 'sql' in kwargs:
                # Entrenar con par pregunta-SQL
                combined = f"Question: {kwargs['question']}\nSQL: {kwargs['sql']}"
                self.collection.add(
                    documents=[combined],
                    metadatas=[{
                        "type": "question_sql",
                        "question": kwargs['question'],
                        "sql": kwargs['sql']
                    }],
                    ids=[doc_id]
                )
                logger.info("✅ Par pregunta-SQL agregado")
                
            return True
            
        except Exception as e:
            logger.error(f"Error en train: {e}")
            return False
    
    def get_relevant_context(self, question: str, n_results: int = 5) -> str:
        """Obtiene contexto relevante de ChromaDB"""
        try:
            if not self.collection:
                return ""
                
            results = self.collection.query(
                query_texts=[question],
                n_results=n_results
            )
            
            context_parts = []
            
            # Agregar documentos relevantes
            for i, doc in enumerate(results['documents'][0]):
                metadata = results['metadatas'][0][i]
                if metadata['type'] == 'ddl':
                    context_parts.append(f"Table Schema:\n{doc}")
                elif metadata['type'] == 'documentation':
                    context_parts.append(f"Documentation:\n{doc}")
                elif metadata['type'] == 'question_sql':
                    context_parts.append(f"Example:\n{doc}")
            
            return "\n\n".join(context_parts)
            
        except Exception as e:
            logger.error(f"Error obteniendo contexto: {e}")
            return ""
    
    def generate_sql(self, question: str) -> Optional[str]:
        """Genera SQL usando OpenAI con contexto local y reglas estrictas."""
        try:
            # Obtener contexto relevante
            context = self.get_relevant_context(question)
            
            # --- INICIO DE CAMBIOS EN EL PROMPT ---
            
            # Construimos un prompt mucho más directivo
            system_prompt = """You are a world-class SQL generation expert for MySQL. Your task is to generate a single, valid MySQL query based on a user's question and the provided context.

Follow these rules STRICTLY:
1.  **Analyze the context first.** The context contains table schemas (DDL), documentation, and query examples. This is your ONLY source of truth.
2.  **You MUST use the table and column names EXACTLY as provided in the context.** Do NOT invent or assume table or column names. If a column for 'last connection' is named 'ultima_conexion' in the context, you must use 'ultima_conexion'.
3.  **Prioritize Documentation and DDL.** The 'Documentation' and 'Table Schema' sections are the most reliable sources for column names and their meanings.
4.  **Do not add any explanation, comments, or markdown.** Your output must be ONLY the SQL query.
"""
            
            user_prompt = f"""CONTEXT:
{context}

USER QUESTION:
{question}

SQL QUERY:
"""
            # --- FIN DE CAMBIOS EN EL PROMPT ---

            # Llamar a OpenAI con el nuevo sistema de prompts
            response = openai.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=250,
                temperature=0
            )
            
            sql = response.choices[0].message.content.strip()
            
            # Limpiar el SQL
            sql = sql.replace("```sql", "").replace("```", "").strip()
            
            logger.info(f"SQL generado: {sql}")
            return sql
            
        except Exception as e:
            logger.error(f"Error generando SQL: {e}")
            return None

    def generate_summary(self, question: str, sql: str, results: List[Dict[str, Any]]) -> Optional[str]:
        """Genera un resumen en lenguaje natural a partir de los resultados de la consulta."""
        try:
            # Límite de resultados a enviar a la IA para evitar sobrecarga.
            SUMMARY_RESULT_LIMIT = 50
            
            if not results:
                return "No se encontraron resultados para tu consulta. Parece que no hay datos que coincidan con lo que buscas."

            results_truncated = len(results) > SUMMARY_RESULT_LIMIT
            results_to_send = results[:SUMMARY_RESULT_LIMIT]
            
            # Convertir resultados a formato más legible
            # Si es una lista de tuplas (resultado directo de MySQL), convertir a lista de dicts
            if results_to_send and isinstance(results_to_send[0], tuple):
                # Intentar obtener los nombres de columnas del SQL
                import re
                select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql, re.IGNORECASE)
                if select_match and 'COUNT' in sql.upper():
                    # Para consultas COUNT, asignar nombre genérico
                    results_to_send = [{"count": row[0]} for row in results_to_send]
                else:
                    # Para otras consultas, usar índices genéricos
                    results_to_send = [{"resultado": row[0] if len(row) == 1 else row} for row in results_to_send]
            
            results_str = str(results_to_send)

            # Construimos el prompt para la IA con instrucciones más específicas
            prompt = f"""Eres un asistente amigable que ayuda a usuarios a entender datos de trámites digitales. 
Tu tarea es explicar los resultados de una consulta de manera clara, natural y conversacional en español.

Contexto:
- Pregunta del usuario: "{question}"
- Consulta SQL ejecutada: {sql}
- Resultados obtenidos: {results_str}

Instrucciones específicas:
1. Responde de forma natural y conversacional, como si estuvieras hablando con un amigo
2. Si es un conteo o número único, no digas solo "El resultado es X". En su lugar, formula una respuesta completa y contextualizada
3. Para consultas de conteo de usuarios, menciona específicamente qué tipo de usuarios (ej: "usuarios mujeres", "usuarios nuevos", etc.)
4. Si hay fechas involucradas, menciónalas de forma natural
5. Agrega contexto útil cuando sea apropiado (ej: "Durante el año 2024 se registraron...")
6. Sé específico pero amigable
7. Si el resultado es un número grande, puedes mencionarlo con formato más legible (ej: "2,977" en lugar de "2977")

Genera una respuesta natural y completa:"""

            # Añadimos una nota si los resultados fueron truncados
            if results_truncated:
                prompt += f"\n\nNota: La consulta encontró {len(results)} resultados en total, pero estoy mostrando solo los primeros {SUMMARY_RESULT_LIMIT}."

            # Llamada a la API de OpenAI para generar el resumen
            response = openai.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system", 
                        "content": "Eres un asistente conversacional que explica datos de manera amigable y natural. Siempre respondes en español de forma clara y contextualizada."
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.3  # Un poco más de variabilidad para respuestas más naturales
            )

            summary = response.choices[0].message.content.strip()
            logger.info(f"Resumen generado: {summary}")
            return summary

        except Exception as e:
            logger.error(f"Error generando resumen: {e}")
            # Fallback mejorado
            if results and len(results) == 1:
                # Para resultados únicos, intentar dar una respuesta más natural
                if isinstance(results[0], (tuple, list)) and len(results[0]) == 1:
                    value = results[0][0]
                    if 'count' in sql.lower():
                        return f"Según los datos, hay {value} registros que cumplen con tu consulta."
                    else:
                        return f"El valor encontrado es: {value}"
                elif isinstance(results[0], dict) and len(results[0]) == 1:
                    value = list(results[0].values())[0]
                    return f"Encontré que el resultado es: {value}"
            
            return f"Se encontraron {len(results)} resultados para tu consulta."

    def is_connected(self) -> bool:
        """Verifica si el servicio está conectado y funcionando"""
        return self.connected and self.connection is not None

    # También agrega estos métodos alias si no los tienes:

    def train_ddl(self, ddl: str) -> bool:
        """Entrena con DDL"""
        return self.train(ddl=ddl)

    def train_documentation(self, documentation: str) -> bool:
        """Entrena con documentación"""
        return self.train(documentation=documentation)

    def train_sql(self, question: str, sql: str) -> bool:
        """Entrena con par pregunta-SQL"""
        return self.train(question=question, sql=sql)

    def get_training_data(self) -> Dict[str, Any]:
        """Obtiene información sobre los datos de entrenamiento"""
        try:
            if not self.collection:
                return {
                    "ddl_count": 0,
                    "documentation_count": 0,
                    "sql_count": 0,
                    "total": 0
                }
            
            return {
                "ddl_count": 0,  # Puedes implementar conteo real si quieres
                "documentation_count": 0,
                "sql_count": 0,
                "total": self.collection.count() if self.collection else 0
            }
        except:
            return {
                "ddl_count": 0,
                "documentation_count": 0,
                "sql_count": 0,
                "total": 0
            }

    def get_all_training_data(self) -> List[Dict[str, Any]]:
        """
        Recupera todos los datos de entrenamiento almacenados en ChromaDB.
        """
        if not self.collection:
            return []
        
        # El método .get() sin filtros devuelve todo
        # Contamos cuántos items hay para recuperarlos todos
        count = self.collection.count()
        if count == 0:
            return []
            
        data = self.collection.get(
            limit=count,
            include=["metadatas", "documents"]
        )
        
        # Formateamos la salida para que sea más legible
        formatted_data = []
        for i, doc_id in enumerate(data['ids']):
            formatted_data.append({
                "id": doc_id,
                "document": data['documents'][i],
                "metadata": data['metadatas'][i]
            })
            
        return formatted_data

    def remove_training(self, training_id: str) -> bool:
        """Elimina un dato de entrenamiento"""
        try:
            if not self.collection:
                return False
            
            self.collection.delete(ids=[training_id])
            return True
        except:
            return False

    def generate_prompt(self, question: str) -> Dict[str, Any]:
        """
        Genera y devuelve el prompt completo que se enviaría a OpenAI para depuración.
        """
        try:
            # Obtiene el contexto de la misma forma que lo hace generate_sql
            context = self.get_relevant_context(question)
            
            # Construye el prompt
            prompt = f"""You are a SQL expert. Generate a SQL query for MySQL based on the following:
            
Context from database:
{context}

User question: {question}

Return only the SQL query without any explanation."""
            
            return {
                "success": True,
                "question": question,
                "context_retrieved": context,
                "full_prompt": prompt
            }
        except Exception as e:
            logger.error(f"Error generando prompt de debug: {e}")
            return {"success": False, "error": str(e)}
    
    def run_sql(self, sql: str) -> Optional[pd.DataFrame]:
        """Ejecuta SQL y retorna DataFrame"""
        try:
            if not self.connection:
                return None
                
            # Reconectar si es necesario
            self.connection.ping(reconnect=True)
            
            # Ejecutar query usando cursor para evitar warning de pandas
            with self.connection.cursor() as cursor:
                cursor.execute(sql)
                
                # Obtener datos y columnas
                data = cursor.fetchall()
                
                # Si no hay datos, retornar DataFrame vacío
                if not data:
                    return pd.DataFrame()
                
                # Crear DataFrame
                # Los datos ya vienen como lista de diccionarios gracias a DictCursor
                df = pd.DataFrame(data)
                return df
            
        except Exception as e:
            logger.error(f"Error ejecutando SQL: {e}")
            return None

    def ask(self, question: str) -> Dict[str, Any]:
        """Método principal: genera SQL y ejecuta"""
        try:
            sql = self.generate_sql(question)
            if not sql:
                return {"success": False, "error": "No se pudo generar SQL"}
            
            result = self.run_sql(sql)
            
            if result is not None:
                return {
                    "success": True,
                    "question": question,
                    "sql": sql,
                    "result": result.to_dict('records')
                }
            else:
                return {"success": False, "error": "Error ejecutando SQL"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}

# Alias para compatibilidad
VannaService = LocalVannaService
