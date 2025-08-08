import streamlit as st
import requests
import pandas as pd
import json
from typing import Dict, Any, List, Optional
import time
import uuid
import os
from dotenv import load_dotenv

# Configuración
load_dotenv()

# Configuración de la página
st.set_page_config(
    page_title="Consultas Inteligentes SQL - Vanna AI",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuración de la API
API_BASE_URL = os.getenv("STREAMLIT_API_BASE_URL", "http://172.25.50.50:8000")

# Estilos CSS personalizados
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding-left: 20px;
        padding-right: 20px;
    }
    div[data-testid="metric-container"] {
        background-color: #f0f2f6;
        border: 1px solid #c3c3c3;
        padding: 10px;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)


# ============= FUNCIONES DE UTILIDAD =============

def make_api_request(endpoint: str, method: str = "GET", data: Dict = None) -> Dict[str, Any]:
    """Realizar petición a la API de Vanna"""
    url = f"{API_BASE_URL}{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url)
        elif method == "POST":
            response = requests.post(url, json=data)
        elif method == "DELETE":
            response = requests.delete(url)
        
        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        else:
            return {"success": False, "error": f"Error {response.status_code}: {response.text}"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "❌ No se puede conectar con el servidor Vanna"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def initialize_session_state():
    """Inicializar variables de sesión"""
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    if 'chat_session_id' not in st.session_state:
        st.session_state.chat_session_id = str(uuid.uuid4())
    if 'system_status' not in st.session_state:
        st.session_state.system_status = None
    if 'training_data' not in st.session_state:
        st.session_state.training_data = []
    if 'show_sql' not in st.session_state:
        st.session_state.show_sql = True
    if 'table_names' not in st.session_state:
        st.session_state.table_names = []


def check_system_status() -> bool:
    """Verificar el estado del sistema Vanna"""
    result = make_api_request("/health")
    if result["success"]:
        status = result["data"]
        st.session_state.system_status = status
        return status.get("database_connected", False)
    st.session_state.system_status = {"status": "unhealthy", "database_connected": False}
    return False


def get_table_names() -> List[str]:
    """Obtener nombres de tablas de la base de datos"""
    result = make_api_request("/run-sql", "POST", {"sql": "SHOW TABLES"})
    if result["success"] and result["data"].get("success"):
        df_data = result["data"]["results"]
        if df_data:
            # El resultado viene como lista de diccionarios, extraer el primer valor
            tables = [list(row.values())[0] for row in df_data]
            st.session_state.table_names = tables
            return tables
    return []


def get_table_schema(table_name: str) -> pd.DataFrame:
    """Obtener esquema de una tabla"""
    result = make_api_request("/run-sql", "POST", {"sql": f"DESCRIBE {table_name}"})
    if result["success"] and result["data"].get("success"):
        return pd.DataFrame(result["data"]["results"])
    return pd.DataFrame()


# ============= COMPONENTES DE LA INTERFAZ =============

def sidebar():
    """Sidebar con información y controles"""
    with st.sidebar:
        st.header("🎛️ Panel de Control")
        
        # Estado del sistema
        st.subheader("📊 Estado del Sistema")
        if st.session_state.system_status:
            if st.session_state.system_status.get("database_connected"):
                st.success("✅ Sistema Conectado")
            else:
                st.error("❌ Base de datos desconectada")
        else:
            st.info("🔍 Verificando conexión...")
        
        if st.button("🔄 Actualizar Estado", use_container_width=True):
            check_system_status()
            st.rerun()
        
        # Estadísticas
        st.markdown("---")
        st.subheader("📈 Estadísticas")
        
        # Contar preguntas del usuario
        user_questions = len([m for m in st.session_state.chat_history if m["role"] == "user"])
        st.metric("Preguntas realizadas", user_questions)
        
        # Cargar datos de entrenamiento
        if st.button("📚 Ver Datos de Entrenamiento", use_container_width=True):
            result = make_api_request("/training-data")
            if result["success"]:
                st.session_state.training_data = result["data"]["data"]
                st.success(f"✅ {result['data']['count']} elementos cargados")
        
        # Opciones
        st.markdown("---")
        st.subheader("⚙️ Opciones")
        st.session_state.show_sql = st.checkbox("Mostrar SQL generado", value=True)
        
        # Acciones
        st.markdown("---")
        st.subheader("🛠️ Acciones")
        
        if st.button("🗑️ Limpiar Conversación", use_container_width=True):
            st.session_state.chat_history = []
            st.session_state.chat_session_id = str(uuid.uuid4())
            st.success("✅ Conversación limpiada")
            st.rerun()
        
        if st.button("🔄 Recargar Tablas", use_container_width=True):
            get_table_names()
            st.success("✅ Tablas actualizadas")
        
        # Información
        st.markdown("---")
        st.caption("🤖 Powered by Vanna AI")
        st.caption("📊 ChromaDB + OpenAI")


def chat_interface():
    """Interfaz principal de chat"""
    st.header("💬 Asistente SQL Inteligente")
    st.markdown("Pregunta en lenguaje natural y obtén consultas SQL precisas")
    
    # Verificar estado del sistema
    if not st.session_state.system_status:
        with st.spinner("Conectando con Vanna..."):
            if not check_system_status():
                st.error("❌ No se puede conectar con el sistema")
                st.info("Asegúrate de que el servidor esté ejecutándose:")
                st.code("python main.py", language="bash")
                return
    
    # Ejemplos de preguntas
    with st.expander("💡 Ejemplos de preguntas"):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            **Consultas básicas:**
            - ¿Cuántos registros hay en la tabla users?
            - Muéstrame todos los usuarios activos
            - ¿Cuáles son las últimas 10 órdenes?
            - Lista todas las tablas disponibles
            """)
        with col2:
            st.markdown("""
            **Consultas avanzadas:**
            - ¿Cuál es el total de ventas por mes?
            - Usuarios que no han hecho pedidos
            - Top 5 productos más vendidos
            - Comparar ventas de este año vs el anterior
            """)
    
    # Mostrar historial de chat
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            
            # Mostrar SQL si está disponible
            if message["role"] == "assistant" and message.get("sql") and st.session_state.show_sql:
                with st.expander("🔍 Ver SQL generado"):
                    st.code(message["sql"], language="sql")
                    
                    # Botón para copiar SQL
                    st.button(
                        "📋 Copiar SQL", 
                        key=f"copy_{message.get('msg_id', '')}", 
                        on_click=lambda sql=message["sql"]: st.write(sql)
                    )
            
            # Mostrar resultados si existen
            if message.get("results_df") is not None:
                st.dataframe(message["results_df"], use_container_width=True)


def process_question(question: str):
    """Procesar pregunta del usuario"""
    # Agregar pregunta al historial
    st.session_state.chat_history.append({"role": "user", "content": question})
    
    # Mostrar mensaje del usuario
    with st.chat_message("user"):
        st.write(question)
    
    # Generar respuesta
    with st.chat_message("assistant"):
        with st.spinner("Pensando..."):
            # Llamar a la API ask que genera SQL y ejecuta
            result = make_api_request("/ask", "POST", {"question": question})
            
            if result["success"] and result["data"].get("success"):
                data = result["data"]
                sql = data.get("sql", "")
                results = data.get("results", [])
                row_count = data.get("row_count", 0)
                
                # Crear mensaje de respuesta
                if results:
                    response = f"Encontré {row_count} resultado{'s' if row_count != 1 else ''}. Aquí están los datos:"
                    df = pd.DataFrame(results)
                else:
                    response = "La consulta se ejecutó pero no devolvió resultados."
                    df = None
                
                st.write(response)
                
                # Mostrar SQL si está habilitado
                if sql and st.session_state.show_sql:
                    with st.expander("🔍 Ver SQL generado"):
                        st.code(sql, language="sql")
                
                # Mostrar resultados
                if df is not None:
                    st.dataframe(df, use_container_width=True)
                    
                    # Opción de descarga
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="📥 Descargar CSV",
                        data=csv,
                        file_name=f"resultados_{st.session_state.chat_session_id[:8]}.csv",
                        mime="text/csv",
                        key=f"download_{len(st.session_state.chat_history)}"
                    )
                
                # Agregar al historial
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": response,
                    "sql": sql,
                    "results_df": df,
                    "msg_id": str(uuid.uuid4())
                })
                
            else:
                error_msg = result.get("error", "Error desconocido")
                response = f"❌ No pude procesar tu pregunta: {error_msg}"
                st.error(response)
                
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": response
                })


def data_explorer():
    """Explorador de datos y esquemas"""
    st.header("🔍 Explorador de Base de Datos")
    
    # Obtener tablas si no están cargadas
    if not st.session_state.table_names:
        with st.spinner("Cargando tablas..."):
            get_table_names()
    
    if st.session_state.table_names:
        # Selector de tabla
        selected_table = st.selectbox(
            "Selecciona una tabla:",
            [""] + st.session_state.table_names,
            format_func=lambda x: "Selecciona una tabla..." if x == "" else x
        )
        
        if selected_table:
            # Tabs para diferentes vistas
            tab1, tab2, tab3 = st.tabs(["📋 Estructura", "📊 Datos", "🔧 SQL Personalizado"])
            
            with tab1:
                # Mostrar estructura de la tabla
                with st.spinner(f"Cargando estructura de {selected_table}..."):
                    schema_df = get_table_schema(selected_table)
                    if not schema_df.empty:
                        st.dataframe(schema_df, use_container_width=True)
                    else:
                        st.error("No se pudo cargar la estructura")
            
            with tab2:
                # Muestra de datos
                num_rows = st.number_input("Número de filas:", min_value=1, max_value=100, value=10)
                if st.button("📥 Cargar Datos"):
                    with st.spinner("Cargando datos..."):
                        result = make_api_request("/run-sql", "POST", {
                            "sql": f"SELECT * FROM {selected_table} LIMIT {num_rows}"
                        })
                        if result["success"] and result["data"].get("success"):
                            df = pd.DataFrame(result["data"]["results"])
                            st.dataframe(df, use_container_width=True)
                            
                            # Descargar
                            csv = df.to_csv(index=False)
                            st.download_button(
                                "📥 Descargar CSV",
                                csv,
                                f"{selected_table}_sample.csv",
                                "text/csv"
                            )
                        else:
                            st.error("Error al cargar datos")
            
            with tab3:
                # SQL personalizado
                st.markdown("**Escribe tu consulta SQL:**")
                custom_sql = st.text_area(
                    "SQL",
                    value=f"SELECT * FROM {selected_table} WHERE ",
                    height=150,
                    key="custom_sql"
                )
                
                col1, col2 = st.columns([1, 4])
                with col1:
                    if st.button("▶️ Ejecutar", type="primary"):
                        with st.spinner("Ejecutando..."):
                            result = make_api_request("/run-sql", "POST", {"sql": custom_sql})
                            if result["success"] and result["data"].get("success"):
                                df = pd.DataFrame(result["data"]["results"])
                                st.success(f"✅ {len(df)} filas")
                                st.dataframe(df, use_container_width=True)
                            else:
                                st.error(f"Error: {result.get('error', 'Error desconocido')}")
    else:
        st.warning("No se encontraron tablas en la base de datos")


def training_interface():
    """Interfaz para gestionar el entrenamiento"""
    st.header("🎓 Gestión de Entrenamiento")
    st.markdown("Entrena a Vanna con nuevos ejemplos para mejorar sus respuestas")
    
    # Tabs para diferentes tipos de entrenamiento
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📝 Pregunta-SQL", "🏗️ DDL", "📚 Documentación", "🗂️ Ver Datos", "🚀 Auto-Entrenamiento"])
    
    with tab1:
        st.subheader("Entrenar con pares Pregunta-SQL")
        with st.form("train_sql_form"):
            question = st.text_input("Pregunta en lenguaje natural:")
            sql = st.text_area("Consulta SQL correspondiente:", height=100)
            
            if st.form_submit_button("➕ Agregar Ejemplo", type="primary"):
                if question and sql:
                    result = make_api_request("/train", "POST", {
                        "question": question,
                        "sql": sql
                    })
                    if result["success"]:
                        st.success(f"✅ Ejemplo agregado con ID: {result['data']['id']}")
                        st.balloons()
                    else:
                        st.error("Error al agregar ejemplo")
                else:
                    st.warning("Por favor completa ambos campos")
    
    with tab2:
        st.subheader("Entrenar con DDL (Estructura de tablas)")
        with st.form("train_ddl_form"):
            ddl = st.text_area(
                "DDL (CREATE TABLE statement):",
                height=200,
                placeholder="CREATE TABLE users (\n  id INT PRIMARY KEY,\n  name VARCHAR(100)\n);"
            )
            
            if st.form_submit_button("➕ Agregar DDL", type="primary"):
                if ddl:
                    result = make_api_request("/train", "POST", {"ddl": ddl})
                    if result["success"]:
                        st.success(f"✅ DDL agregado con ID: {result['data']['id']}")
                    else:
                        st.error("Error al agregar DDL")
                else:
                    st.warning("Por favor ingresa el DDL")
    
    with tab3:
        st.subheader("Entrenar con Documentación")
        with st.form("train_doc_form"):
            documentation = st.text_area(
                "Documentación o contexto de negocio:",
                height=150,
                placeholder="La tabla 'users' contiene información de usuarios. Los usuarios activos tienen status='active'..."
            )
            
            if st.form_submit_button("➕ Agregar Documentación", type="primary"):
                if documentation:
                    result = make_api_request("/train", "POST", {"documentation": documentation})
                    if result["success"]:
                        st.success(f"✅ Documentación agregada con ID: {result['data']['id']}")
                    else:
                        st.error("Error al agregar documentación")
                else:
                    st.warning("Por favor ingresa la documentación")
    
    with tab4:
        st.subheader("Datos de Entrenamiento Actuales")
        
        # Botón para recargar
        if st.button("🔄 Actualizar Lista"):
            result = make_api_request("/training-data")
            if result["success"]:
                st.session_state.training_data = result["data"]["data"]
        
        if st.session_state.training_data:
            # Mostrar estadísticas
            df_training = pd.DataFrame(st.session_state.training_data)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                sql_count = len(df_training[df_training['type'] == 'sql'])
                st.metric("Ejemplos SQL", sql_count)
            with col2:
                ddl_count = len(df_training[df_training['type'] == 'ddl'])
                st.metric("DDLs", ddl_count)
            with col3:
                doc_count = len(df_training[df_training['type'] == 'documentation'])
                st.metric("Documentación", doc_count)
            
            # Mostrar datos
            st.dataframe(df_training, use_container_width=True)
            
            # Opción de eliminar
            if st.checkbox("Habilitar eliminación"):
                item_to_delete = st.selectbox(
                    "Selecciona elemento a eliminar:",
                    df_training['id'].tolist()
                )
                if st.button("🗑️ Eliminar", type="secondary"):
                    result = make_api_request(f"/training-data/{item_to_delete}", "DELETE")
                    if result["success"]:
                        st.success("✅ Elemento eliminado")
                        st.rerun()
                    else:
                        st.error("Error al eliminar")
        else:
            st.info("No hay datos de entrenamiento. Usa las pestañas anteriores para agregar.")
    
    with tab5:
        st.subheader("🚀 Entrenamiento Automático")
        st.markdown("Entrena automáticamente con todas las estructuras de tablas de tu base de datos")
        
        # Información
        st.info("""
        Esta función:
        - Detecta todas las tablas en tu base de datos
        - Extrae el DDL (CREATE TABLE) de cada una
        - Entrena a Vanna con estas estructuras
        
        ⚠️ Puede tomar tiempo si tienes muchas tablas
        """)
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🎯 Iniciar Entrenamiento Automático", type="primary", use_container_width=True):
                with st.spinner("Entrenando con DDLs de todas las tablas..."):
                    result = make_api_request("/train/auto-ddl", "POST", {})
                    
                    if result["success"] and result["data"]["success"]:
                        st.success(f"""
                        ✅ Entrenamiento completado!
                        - Tablas entrenadas: {result['data']['trained_tables']}
                        - Total de tablas: {result['data']['total_tables']}
                        """)
                        
                        if result['data'].get('errors'):
                            st.warning(f"Hubo {len(result['data']['errors'])} errores durante el proceso")
                            with st.expander("Ver errores"):
                                for error in result['data']['errors']:
                                    st.text(f"❌ {error['table']}: {error['error']}")
                        
                        st.balloons()
                    else:
                        st.error("Error durante el entrenamiento automático")
        
        with col2:
            # Botón para ver las tablas disponibles
            if st.button("📋 Ver Tablas Disponibles", use_container_width=True):
                result = make_api_request("/tables")
                if result["success"]:
                    tables = result["data"]["tables"]
                    st.write(f"**{len(tables)} tablas encontradas:**")
                    
                    # Mostrar en columnas para mejor visualización
                    cols = st.columns(3)
                    for i, table in enumerate(tables):
                        cols[i % 3].write(f"• {table}")
                else:
                    st.error("Error obteniendo lista de tablas")


# ============= APLICACIÓN PRINCIPAL =============

def main():
    initialize_session_state()
    
    # Título principal
    st.title("🤖 Vanna AI - Consultas SQL Inteligentes")
    st.markdown("Convierte preguntas en lenguaje natural a consultas SQL precisas")
    
    # Sidebar
    sidebar()
    
    # Verificar conexión inicial
    if st.session_state.system_status is None:
        check_system_status()
    
    # Tabs principales
    tab1, tab2, tab3 = st.tabs(["💬 Chat", "🔍 Explorador", "🎓 Entrenamiento"])
    
    with tab1:
        chat_interface()
    
    with tab2:
        data_explorer()
    
    with tab3:
        training_interface()
    
    # Input de chat (siempre visible en la parte inferior)
    question = st.chat_input("Escribe tu pregunta aquí...")
    if question:
        # Cambiar a la pestaña de chat
        st.session_state.active_tab = 0
        process_question(question)
        st.rerun()


if __name__ == "__main__":
    main()