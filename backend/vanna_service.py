# vanna_service.py - Implementación mínima de Vanna con ChromaDB y OpenAI
import os
import json
import uuid
import logging
import pymysql
import openai
import chromadb
import pandas as pd
import re
from datetime import datetime
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from typing import List, Dict, Optional
from datetime import datetime

load_dotenv()
logger = logging.getLogger(__name__)


class VannaChromaDB:
    """
    Implementación mínima de Vanna usando ChromaDB como vector store y OpenAI.
    Basado en la arquitectura oficial de Vanna.
    """
    
    def __init__(self, config: Dict = None):
        if config is None:
            config = {}
            
        # Configuración del Vector Store (ChromaDB)
        chroma_path = os.getenv("VANNA_VECTOR_DB_PATH")
        if chroma_path is None:
            # Si la variable no está definida, detiene la aplicación y avisa.
            # Esto evita el error de guardado silencioso.
            raise ValueError("¡ERROR CRÍTICO! La variable de entorno VANNA_VECTOR_DB_PATH no está definida. La aplicación no puede iniciarse.")

        
        # Embeddings de OpenAI
        self.embedding_function = embedding_functions.OpenAIEmbeddingFunction(
            api_key=os.getenv("OPENAI_API_KEY"),
            model_name="text-embedding-3-small"
        )
        
        # Cliente ChromaDB
        self.chroma_client = chromadb.PersistentClient(path=chroma_path)
                
        # Parámetros de búsqueda
        self.n_results_sql = config.get("n_results_sql", 10)
        self.n_results_ddl = config.get("n_results_ddl", 10)
        self.n_results_documentation = config.get("n_results_documentation", 10)
        
        # Conexión a base de datos
        self.db_connection = None
        self.connect_to_mysql()
        
        # Cliente OpenAI para LLM
        self.llm_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = config.get("model", "gpt-4o")
        
        logger.info(f"✅ Vanna inicializado con ChromaDB en: {chroma_path}")
    

    def _get_collections(self, topic: str):
        """
        Obtiene o crea las 3 colecciones para un tópico específico.
        El nombre de la colección ahora incluye el tópico.
        """
        # Limpiamos el topic para que sea un nombre de colección válido
        safe_topic = re.sub(r'[^a-zA-Z0-9_-]', '', topic).lower()

        doc_collection = self.chroma_client.get_or_create_collection(
            name=f"documentation_{safe_topic}",
            embedding_function=self.embedding_function, # <- CORREGIDO (singular)
            metadata={"topic": topic}
        )
        ddl_collection = self.chroma_client.get_or_create_collection(
            name=f"ddl_{safe_topic}", 
            embedding_function=self.embedding_function, # <- CORREGIDO (singular)
            metadata={"topic": topic}
        )
        sql_collection = self.chroma_client.get_or_create_collection(
            name=f"sql_{safe_topic}",
            embedding_function=self.embedding_function, # <- CORREGIDO (singular)
            metadata={"topic": topic}
        )
        return doc_collection, ddl_collection, sql_collection

    # ===== MÉTODOS DE CONEXIÓN A BASE DE DATOS =====
    
    def connect_to_mysql(self, host: str = None, dbname: str = None, 
                        user: str = None, password: str = None, port: int = 3306):
        """Conecta a MySQL usando credenciales del entorno o las proporcionadas."""
        try:
            self.db_connection = pymysql.connect(
                host=host or os.getenv("DB_HOST"),
                user=user or os.getenv("DB_USER"),
                password=password or os.getenv("DB_PASSWORD"),
                database=dbname or os.getenv("DB_DATABASE"),
                port=port or os.getenv("DB_PORT"),
                cursorclass=pymysql.cursors.DictCursor
            )
            logger.info("✅ Conexión a MySQL exitosa")
            return True
        except Exception as e:
            logger.error(f"❌ Error conectando a MySQL: {e}")
            return False
    
    # en vanna_service.py
    def run_sql(self, sql: str) -> pd.DataFrame:
        """
        Ejecuta consultas de solo lectura (SELECT y SHOW) y retorna los resultados.
        Rechaza cualquier otra operación (INSERT, UPDATE, DELETE, etc.).
        """
        # 1. Limpiar y verificar que la consulta sea de solo lectura
        cleaned_sql = sql.strip().upper()

        # 2. Si la validación pasa, proceder a ejecutar la consulta
        if not self.db_connection:
            raise Exception("No hay conexión a la base de datos")
        
        try:
            with self.db_connection.cursor() as cursor:
                cursor.execute(sql)
                result = cursor.fetchall()
            return pd.DataFrame(result)
        except Exception as e:
            logger.error(f"Error ejecutando SQL: {e}")
            if "MySQL server has gone away" in str(e):
                self.connect_to_mysql()
                return self.run_sql(sql)
            raise e
    # ===== MÉTODOS DE ENTRENAMIENTO =====
    
    def train(self, topic: str, question: str = None, sql: str = None, 
              ddl: str = None, documentation: str = None) -> str:
        """
        Método principal de entrenamiento. Acepta diferentes tipos de datos
        y un TÓPICO OBLIGATORIO.
        Retorna el ID del documento agregado.
        """
        if not topic:
            raise ValueError("El 'topic' es obligatorio para el entrenamiento.")
        
        if question and sql:
            return self.add_question_sql(question, sql, topic)
        elif ddl:
            return self.add_ddl(ddl, topic)
        elif documentation:
            return self.add_documentation(documentation, topic)
        else:
            raise ValueError("Debe proporcionar: (question y sql), ddl, o documentation")
    
    def add_question_sql(self, question: str, sql: str, topic: str) -> str:
        _, _, sql_collection = self._get_collections(topic)
        doc_id = f"sql-{uuid.uuid4()}"
        document = json.dumps({"question": question, "sql": sql})
        
        sql_collection.add(documents=[document], ids=[doc_id], metadatas=[{"question": question}])
        logger.info(f"✅ Agregado Q&A SQL (Topic: {topic}): {doc_id}")
        return doc_id
    
    def add_ddl(self, ddl: str, topic: str) -> str:
        _, ddl_collection, _ = self._get_collections(topic)
        doc_id = f"ddl-{uuid.uuid4()}"
        ddl_collection.add(documents=[ddl], ids=[doc_id])
        logger.info(f"✅ Agregado DDL (Topic: {topic}): {doc_id}")
        return doc_id
    
    def add_documentation(self, documentation: str, topic: str) -> str:
        doc_collection, _, _ = self._get_collections(topic)
        doc_id = f"doc-{uuid.uuid4()}"
        doc_collection.add(documents=[documentation], ids=[doc_id])
        logger.info(f"✅ Agregada documentación (Topic: {topic}): {doc_id}")
        return doc_id
    
    # ===== MÉTODOS DE BÚSQUEDA/RECUPERACIÓN =====
    
    def get_similar_question_sql(self, question: str, topic: str) -> List[Dict]:
        _, _, sql_collection = self._get_collections(topic)
        results = sql_collection.query(query_texts=[question], n_results=self.n_results_sql)
        return [json.loads(doc) for doc in results['documents'][0]] if results['documents'][0] else []
    
    def get_related_ddl(self, question: str, topic: str) -> List[str]:
        _, ddl_collection, _ = self._get_collections(topic)
        results = ddl_collection.query(query_texts=[question], n_results=self.n_results_ddl)
        return results['documents'][0] if results['documents'][0] else []
    
    def get_related_documentation(self, question: str, topic: str) -> List[str]:
        doc_collection, _, _ = self._get_collections(topic)
        results = doc_collection.query(query_texts=[question], n_results=self.n_results_documentation)
        return results['documents'][0] if results['documents'][0] else []
    def get_available_topics(self) -> list:
        """Escanea las colecciones y devuelve una lista de tópicos disponibles."""
        collections = self.chroma_client.list_collections()
        # Usamos un set para evitar duplicados y extraemos el tópico del metadato
        topics = {c.metadata.get("topic") for c in collections if c.metadata and "topic" in c.metadata}
        return list(topics)

    def get_topic_for_question(self, question: str) -> str:
        """
        Usa el LLM para clasificar la pregunta del usuario en uno de los tópicos disponibles.
        Esta es nuestra 'recepcionista inteligente'.
        """
        available_topics = self.get_available_topics()
        
        if not available_topics:
            # Si no hay tópicos entrenados, no se puede clasificar nada.
            raise ValueError("No hay tópicos entrenados. Por favor, entrena el sistema primero.")
        
        # Si solo hay un tópico, lo devolvemos directamente para ahorrar una llamada al LLM.
        if len(available_topics) == 1:
            return available_topics[0]

        system_prompt = f"""
        Tu única tarea es clasificar la pregunta del usuario en una de las siguientes categorías (tópicos).
        Las categorías disponibles son: {', '.join(available_topics)}.
        Responde ÚNICAMENTE con el nombre exacto de la categoría, sin explicaciones ni texto adicional.
        """

        response = self.llm_client.chat.completions.create(
            model="gpt-4o", # Podemos usar un modelo rápido para esta tarea
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            temperature=0,
            max_tokens=10 # El nombre de un tópico no debería ser más largo
        )
        
        # La respuesta del LLM debería ser directamente el nombre del tópico.
        topic = response.choices[0].message.content.strip()

        # Verificación para asegurarnos de que el LLM devolvió un tópico válido
        if topic in available_topics:
            logger.info(f"🤖 Pregunta clasificada en el tópico: '{topic}'")
            return topic
        else:
            # Si el LLM responde algo inesperado, usamos "general" como fallback seguro.
            logger.warning(f"Clasificación de tópico fallida. Usando 'general' como fallback.")
            return "general"

    # ===== MÉTODO PRINCIPAL: GENERACIÓN DE SQL =====
    
    def generate_sql(self, question: str, topic: str) -> str:
        """
        Genera SQL a partir de una pregunta en lenguaje natural.
        Este es el método principal que los usuarios llamarán.
        """
        if not topic:
            raise ValueError("El 'topic' es obligatorio para generar SQL.")

        # Obtener contexto relevante
        ddl_list = self.get_related_ddl(question, topic = topic)
        doc_list = self.get_related_documentation(question, topic = topic)
        sql_list = self.get_similar_question_sql(question, topic = topic)
        
        # Construir prompt
        prompt = self._construct_prompt(question, ddl_list, doc_list, sql_list)
        
        current_year = datetime.now().year

        # Se ha añadido una instrucción para que el modelo use el formato markdown
        system_prompt = f"""
            Eres un experto asistente de SQL. Tu tarea es generar una única consulta SQL basada en la pregunta del usuario y el contexto proporcionado.
            Siempre debes devolver la consulta SQL dentro de un bloque de código markdown, como en este ejemplo: ```sql\nSELECT * FROM tabla;\n```

            REGLAS IMPORTANTES:
            1. Si una pregunta implica una fecha pero no se especifica el año, asume que se refiere al año actual: {current_year}.
            2. Analiza el esquema de la base de datos y los ejemplos para usar los nombres correctos de tablas y columnas.
            3. Nunca busques o respondas contraseñas, claves(EXCEPTO DNI, CORREOS o IDS).
            4. Siempre normalizar fechas relativas a absolutas usando TZ "America/Argentina/Cordoba"; usar rango semiabierto [start_date, end_next) o cerrado con '00:00:00' y '23:59:59'; evitar funciones MONTH/YEAR en columnas para no romper índices.
            5. En TODA consulta que cuente solicitudes, excluir eliminadas lógicamente con r.deleted_at IS NULL
            """
        
        # Llamar al LLM
        response = self.llm_client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=800
        )
        
        # Obtener la respuesta de la IA
        ai_response = response.choices[0].message.content.strip()
        
        # --- INICIO DE LA SECCIÓN CORREGIDA ---
        # Se utiliza una expresión regular para extraer de forma segura el contenido del bloque de código SQL.
        match = re.search(r"```sql\n(.*?)\n```", ai_response, re.DOTALL)
        
        if match:
            # Si se encuentra el patrón, se extrae el SQL.
            sql = match.group(1).strip()
        else:
            # Si no se encuentra el patrón, se usa la respuesta completa como fallback.
            # Esto evita que la aplicación se caiga y la hace más robusta.
            sql = ai_response
        # --- FIN DE LA SECCIÓN CORREGIDA ---
            
        return sql    

    def _construct_prompt(self, question: str, ddl_list: List[str], 
                         doc_list: List[str], sql_list: List[Dict]) -> str:
        """Construye el prompt para el LLM con todo el contexto."""
        prompt_parts = []
        
        # Agregar DDLs si existen
        if ddl_list:
            prompt_parts.append("DATABASE SCHEMA:")
            for ddl in ddl_list[:3]:  # Limitar a 3 más relevantes
                prompt_parts.append(ddl)
            prompt_parts.append("")
        
        # Agregar documentación si existe
        if doc_list:
            prompt_parts.append("BUSINESS CONTEXT:")
            for doc in doc_list[:3]:  # Limitar a 3 más relevantes
                prompt_parts.append(f"- {doc}")
            prompt_parts.append("")
        
        # Agregar ejemplos SQL si existen
        if sql_list:
            prompt_parts.append("SIMILAR EXAMPLES:")
            for item in sql_list[:5]:  # Limitar a 5 más relevantes
                prompt_parts.append(f"Question: {item['question']}")
                prompt_parts.append(f"SQL: {item['sql']}")
                prompt_parts.append("")
        
        # Agregar la pregunta actual
        prompt_parts.append(f"QUESTION: {question}")
        prompt_parts.append("SQL:")
        
        return "\n".join(prompt_parts)
    
    # ===== MÉTODO COMBINADO: ASK (pregunta -> SQL -> resultados) =====
    
    def ask(self, question: str, topic: str , print_results: bool = True) -> pd.DataFrame:
        """
        Método de alto nivel: genera SQL y ejecuta la consulta.
        Retorna el DataFrame con resultados.
        """
        try:
            # Generar SQL
            sql = self.generate_sql(question, topic)
            if print_results:
                print(f"Generated SQL:\n{sql}\n")
            
            # Ejecutar SQL
            df = self.run_sql(sql)
            
            if print_results and df is not None:
                print(f"Results ({len(df)} rows):")
                print(df)
                
            return df
            
        except Exception as e:
            logger.error(f"Error en ask(): {e}")
            if print_results:
                print(f"Error: {e}")
            return None
    
    # ===== MÉTODOS DE GESTIÓN =====
    
    def get_training_data(self) -> pd.DataFrame:
        """Obtiene TODOS los datos de entrenamiento de TODOS los tópicos."""
        all_collections = self.chroma_client.list_collections()
        data = []
        
        for coll in all_collections:
            topic = coll.metadata.get("topic", "desconocido")
            coll_data = coll.get()

            if coll.name.startswith('sql_'):
                for i, doc_id in enumerate(coll_data['ids']):
                    doc = json.loads(coll_data['documents'][i])
                    data.append({'id': doc_id, 'type': 'sql', 'topic': topic, 'question': doc.get('question'), 'content': doc.get('sql')})
            
            elif coll.name.startswith('ddl_'):
                for i, doc_id in enumerate(coll_data['ids']):
                    data.append({'id': doc_id, 'type': 'ddl', 'topic': topic, 'question': None, 'content': coll_data['documents'][i]})

            elif coll.name.startswith('documentation_'):
                 for i, doc_id in enumerate(coll_data['ids']):
                    data.append({'id': doc_id, 'type': 'documentation', 'topic': topic, 'question': None, 'content': coll_data['documents'][i]})
        
        return pd.DataFrame(data)
    
    def remove_training_data(self, id: str, topic: str) -> bool:
        """Elimina un elemento del training data por ID y TÓPICO."""
        try:
            if not topic:
                raise ValueError("El 'topic' es obligatorio para eliminar datos.")

            doc_collection, ddl_collection, sql_collection = self._get_collections(topic)
            
            if id.startswith('sql-'):
                sql_collection.delete(ids=[id])
            elif id.startswith('ddl-'):
                ddl_collection.delete(ids=[id])
            elif id.startswith('doc-'):
                doc_collection.delete(ids=[id])
            else:
                return False
            
            logger.info(f"✅ Eliminado {id} del tópico {topic}")
            return True
            
        except Exception as e:
            logger.error(f"Error eliminando {id} del tópico {topic}: {e}")
            return False
    
    # ===== MÉTODOS ÚTILES ADICIONALES =====
    
    def get_table_names(self) -> List[str]:
        """Obtiene lista de tablas en la base de datos."""
        df = self.run_sql("SHOW TABLES")
        return df.iloc[:, 0].tolist() if df is not None else []
    
    def get_table_ddl(self, table_name: str) -> str:
        """Obtiene el DDL de una tabla específica."""
        df = self.run_sql(f"SHOW CREATE TABLE `{table_name}`")
        return df.iloc[0, 1] if df is not None and not df.empty else ""
    
    def train_on_ddl_from_database(self, topic: str, tables: List[str] = None):
        if not topic:
            raise ValueError("El 'topic' es obligatorio.")
        if tables is None:
            tables = self.get_table_names()
        for table in tables:
            try:
                ddl = self.get_table_ddl(table)
                if ddl:
                    self.add_ddl(ddl, topic)
                    logger.info(f"✅ Entrenado con DDL de tabla: {table} (Topic: {topic})")
            except Exception as e:
                logger.error(f"Error con tabla {table} (Topic: {topic}): {e}")


# ===== EJEMPLO DE USO =====
if __name__ == "__main__":
    # Inicializar Vanna
    vn = VannaChromaDB()
    
    # Entrenar con algunos ejemplos
    vn.train(
        question="¿Cuántos usuarios hay en total?",
        sql="SELECT COUNT(*) as total_users FROM users"
    )
    
    vn.train(
        documentation="La tabla 'users' contiene información de todos los usuarios registrados. "
                     "Los usuarios activos tienen status = 'active'."
    )
    
    # Hacer una pregunta
    df = vn.ask("¿Cuántos usuarios activos tenemos?")