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
    
    def generate_sql(self, question: str, conversation_history: List[Dict[str, str]] = None) -> Optional[str]:
        """Genera SQL usando OpenAI con contexto local, reglas estrictas y memoria conversacional."""
        try:
            # Detectar si es una pregunta contextual
            is_contextual = self.is_contextual_question(question)
            
            # Si es contextual y no hay historial, advertir
            if is_contextual and (not conversation_history or len(conversation_history) == 0):
                logger.warning("Pregunta contextual detectada sin historial de conversación")
            
            # Obtener contexto relevante de la base de datos
            db_context = self.get_relevant_context(question)
            
            # Construir contexto conversacional si existe historial
            conversation_context = ""
            if conversation_history and len(conversation_history) > 0:
                conversation_context = "\n\nPREVIOUS CONVERSATION CONTEXT:\n"
                # Si es contextual, incluir más historial
                history_limit = 7 if is_contextual else 5
                for i, interaction in enumerate(conversation_history[-history_limit:]):
                    conversation_context += f"\nInteraction {i+1}:\n"
                    conversation_context += f"User asked: {interaction.get('question', '')}\n"
                    conversation_context += f"SQL generated: {interaction.get('sql', '')}\n"
                    if interaction.get('answer'):
                        # Incluir un resumen de la respuesta si es muy larga
                        answer = interaction['answer']
                        if len(answer) > 200:
                            answer = answer[:200] + "..."
                        conversation_context += f"Answer summary: {answer}\n"
            
            # Prompt mejorado con soporte para contexto conversacional
            system_prompt = """You are a world-class SQL generation expert for MySQL with conversational memory. Your task is to generate a single, valid MySQL query based on a user's question, database context, and conversation history.

Follow these rules STRICTLY:
1. **Analyze the context first.** The context contains table schemas (DDL), documentation, and query examples. This is your ONLY source of truth for table/column names.
2. **Consider conversation history.** If the user refers to previous queries or results (e.g., "and how many were men?" after asking about women), use the previous SQL as reference.
3. **You MUST use the table and column names EXACTLY as provided in the context.** Do NOT invent or assume table or column names.
4. **Handle contextual references intelligently.** If the user says "the same but for X", modify the previous query appropriately.
5. **Do not add any explanation, comments, or markdown.** Your output must be ONLY the SQL query.

Examples of contextual queries:
- Previous: "how many female users?" → Current: "and males?" → Modify the previous query changing the gender condition
- Previous: "users created in 2024" → Current: "show me the first 10" → Add LIMIT to previous query
- Previous: "count of forms" → Current: "which are the most used?" → Change from COUNT to listing with ORDER BY
"""
            
            # Agregar indicación especial si es contextual
            if is_contextual and conversation_history:
                system_prompt += "\n\nIMPORTANT: The current question appears to be contextual. Pay special attention to the previous queries and modify them accordingly."
            
            user_prompt = f"""DATABASE CONTEXT:
{db_context}
{conversation_context}

CURRENT USER QUESTION:
{question}

SQL QUERY:
"""

            # Llamar a OpenAI con el contexto completo
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
            
            logger.info(f"SQL generado {'con contexto' if is_contextual else ''}: {sql}")
            return sql
            
        except Exception as e:
            logger.error(f"Error generando SQL: {e}")
            return None

    def generate_summary(self, question: str, sql: str, results: List[Dict[str, Any]], 
                        conversation_history: List[Dict[str, str]] = None) -> Optional[str]:
        """Genera un resumen en lenguaje natural con contexto conversacional."""
        try:
            # Límite de resultados a enviar a la IA para evitar sobrecarga.
            SUMMARY_RESULT_LIMIT = 50
            
            if not results:
                return "No se encontraron resultados para tu consulta. Parece que no hay datos que coincidan con lo que buscas."

            results_truncated = len(results) > SUMMARY_RESULT_LIMIT
            results_to_send = results[:SUMMARY_RESULT_LIMIT]
            
            # Convertir resultados a formato más legible
            if results_to_send and isinstance(results_to_send[0], tuple):
                import re
                select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql, re.IGNORECASE)
                if select_match and 'COUNT' in sql.upper():
                    results_to_send = [{"count": row[0]} for row in results_to_send]
                else:
                    results_to_send = [{"resultado": row[0] if len(row) == 1 else row} for row in results_to_send]
            
            results_str = str(results_to_send)

            # Construir contexto conversacional
            conversation_context = ""
            if conversation_history and len(conversation_history) > 0:
                conversation_context = "\n\nContexto de conversación previa:"
                # Solo incluir las últimas 3 interacciones para el resumen
                for interaction in conversation_history[-3:]:
                    if interaction.get('question') and interaction.get('answer'):
                        conversation_context += f"\n- Preguntaste: {interaction['question']}"
                        # Resumir respuestas largas
                        answer = interaction['answer']
                        if len(answer) > 150:
                            answer = answer[:150] + "..."
                        conversation_context += f"\n  Respondí: {answer}"

            # Prompt mejorado con memoria conversacional
            prompt = f"""Eres un asistente amigable que ayuda a usuarios a entender datos de trámites digitales. 
Tu tarea es explicar los resultados de una consulta de manera clara, natural y conversacional en español.

Contexto:
- Pregunta actual del usuario: "{question}"
- Consulta SQL ejecutada: {sql}
- Resultados obtenidos: {results_str}
{conversation_context}

Instrucciones específicas:
1. Responde de forma natural y conversacional, como si estuvieras hablando con un amigo
2. Si la pregunta hace referencia a algo anterior (ej: "¿y cuántos hombres?" después de preguntar por mujeres), haz la conexión explícita
3. Si es relevante, compara con resultados anteriores (ej: "A diferencia de las 2,977 mujeres que mencioné antes, hay X hombres")
4. Para consultas de conteo, sé específico sobre qué estás contando
5. Si hay fechas involucradas, menciónalas de forma natural
6. Usa números con formato legible (2,977 en lugar de 2977)
7. Si detectas que es una pregunta de seguimiento, relaciónala con la respuesta anterior

Genera una respuesta natural y contextualizada:"""

            # Añadir nota sobre resultados truncados
            if results_truncated:
                prompt += f"\n\nNota: La consulta encontró {len(results)} resultados en total, pero estoy mostrando solo los primeros {SUMMARY_RESULT_LIMIT}."

            # Llamada a OpenAI
            response = openai.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system", 
                        "content": "Eres un asistente conversacional con memoria que explica datos de manera amigable y natural. Siempre respondes en español de forma clara, contextualizada y recordando conversaciones previas cuando es relevante."
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.3
            )

            summary = response.choices[0].message.content.strip()
            logger.info(f"Resumen generado con contexto: {summary}")
            return summary

        except Exception as e:
            logger.error(f"Error generando resumen: {e}")
            # Fallback mejorado
            if results and len(results) == 1:
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

    def is_contextual_question(self, question: str) -> bool:
        """Detecta si una pregunta hace referencia a contexto previo"""
        contextual_patterns = [
            "y cuánt", "y los", "y las", "y el", "y la",
            "mismo", "misma", "igual", 
            "pero", "sin embargo",
            "también", "además",
            "anterior", "previo",
            "comparar", "diferencia",
            "primero", "último",
            "resto", "demás", "otros",
            "ahora", "entonces",
            "ese", "esa", "esos", "esas",
            "dicho", "mencionado"
        ]
        
        question_lower = question.lower()
        return any(pattern in question_lower for pattern in contextual_patterns)
    

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