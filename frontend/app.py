import streamlit as st
import requests
import pandas as pd
import json
from typing import Dict, Any, List
import time
import uuid

# Configuración
st.set_page_config(
    page_title="Consultas Inteligentes - Trámites Digitales",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

API_BASE_URL = "http://localhost:8000"

# Funciones de utilidad
def make_api_request(endpoint: str, method: str = "GET", data: Dict = None, token: str = None) -> Dict[str, Any]:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    url = f"{API_BASE_URL}{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            headers["Content-Type"] = "application/json"
            response = requests.post(url, json=data, headers=headers)
        
        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        else:
            return {"success": False, "error": f"Error {response.status_code}: {response.text}"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "No se puede conectar con el servidor"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def initialize_session_state():
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'token' not in st.session_state:
        st.session_state.token = None
    if 'username' not in st.session_state:
        st.session_state.username = None
    if 'mysql_tables' not in st.session_state:
        st.session_state.mysql_tables = []
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    if 'chat_session_id' not in st.session_state:
        st.session_state.chat_session_id = str(uuid.uuid4())
    if 'system_ready' not in st.session_state:
        st.session_state.system_ready = None
    if 'current_database' not in st.session_state:
        st.session_state.current_database = "digitalform"
    if 'active_tab' not in st.session_state:
        st.session_state.active_tab = 0

def check_system_status():
    """Verificar estado del sistema"""
    try:
        health_result = make_api_request("/health", "GET")
        
        if health_result["success"]:
            health = health_result["data"]
            # Verifica tanto mindsdb_connected como vanna_connected
            system_ready = health.get("mindsdb_connected", False) or health.get("vanna_connected", False)
            st.session_state.system_ready = system_ready
            return system_ready
        
        st.session_state.system_ready = False
        return False
    except:
        st.session_state.system_ready = False
        return False

def login_page():
    st.title("🤖 Sistema de Consultas Inteligentes")
    st.subheader("Acceso a Información de Trámites Digitales")
    
    # Columnas para centrar el formulario
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        # Información de credenciales para desarrollo
        with st.expander("ℹ️ Credenciales de prueba"):
            st.info("**Usuario:** admin  \n**Contraseña:** admin123")
        
        with st.form("login_form"):
            username = st.text_input("Usuario", placeholder="Ingresa tu usuario")
            password = st.text_input("Contraseña", type="password", placeholder="Ingresa tu contraseña")
            submit_button = st.form_submit_button("🔐 Ingresar", type="primary", use_container_width=True)
            
            if submit_button:
                if not username or not password:
                    st.error("Por favor ingresa usuario y contraseña")
                else:
                    with st.spinner("Verificando credenciales..."):
                        try:
                            # El backend espera form data, no JSON
                            response = requests.post(
                                f"{API_BASE_URL}/auth/login",
                                data={  # Importante: usar 'data' no 'json'
                                    "username": username,
                                    "password": password
                                },
                                headers={"Content-Type": "application/x-www-form-urlencoded"}
                            )
                            
                            if response.status_code == 200:
                                token_data = response.json()
                                st.session_state.authenticated = True
                                st.session_state.token = token_data["access_token"]
                                st.session_state.username = username
                                st.success("✅ ¡Bienvenido! Redirigiendo...")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("❌ Usuario o contraseña incorrectos")
                                
                        except requests.exceptions.ConnectionError:
                            st.error("❌ No se puede conectar con el servidor")
                            st.info("Asegúrate de que el servidor esté ejecutándose:")
                            st.code("cd backend && uvicorn main:app --reload", language="bash")
                        except Exception as e:
                            st.error(f"❌ Error inesperado: {str(e)}")

def load_mysql_info():
    """Cargar información de MySQL"""
    try:
        tables_result = make_api_request("/mysql/tables", "GET", token=st.session_state.token)
        if tables_result["success"]:
            st.session_state.mysql_tables = tables_result["data"]["tables"]
        return True
    except:
        return False

def smart_sidebar():
    """Sidebar simplificado"""
    st.sidebar.header("🎛️ Panel de Control")
    
    # Información del usuario
    st.sidebar.info(f"👤 Usuario: **{st.session_state.username}**")
    
    # Indicador de estado
    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 Estado del Sistema")
    
    if st.session_state.system_ready:
        st.sidebar.success("✅ Sistema Conectado")
    elif st.session_state.system_ready is False:
        st.sidebar.error("❌ Sistema Desconectado")
        if st.sidebar.button("🔄 Reintentar Conexión"):
            check_system_status()
            st.rerun()
    else:
        st.sidebar.info("🔍 Verificando conexión...")
    
    # Información de la base de datos
    st.sidebar.markdown("---")
    st.sidebar.subheader("🗄️ Base de Datos")
    st.sidebar.text(f"📁 {st.session_state.current_database}")
    st.sidebar.text(f"📋 {len(st.session_state.mysql_tables)} tablas")
    
    # Estadísticas
    st.sidebar.markdown("---")
    st.sidebar.subheader("📈 Actividad")
    total_chat = len([m for m in st.session_state.chat_history if m["role"] == "user"])
    st.sidebar.metric("Preguntas realizadas", total_chat)
    
    # Indicador de memoria conversacional
    if total_chat > 0:
        st.sidebar.info("🧠 Memoria activa: Puedo recordar nuestra conversación")
    
    # Acciones
    st.sidebar.markdown("---")
    st.sidebar.subheader("🛠️ Acciones")
    
    if st.sidebar.button("🗑️ Limpiar Conversación", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.chat_session_id = str(uuid.uuid4())
        st.rerun()
    
    if st.sidebar.button("🔄 Recargar Tablas", use_container_width=True):
        load_mysql_info()
        st.sidebar.success("✅ Tablas actualizadas")
    
    # Logout
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Cerrar Sesión", type="secondary", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

def display_chat_interface():
    """Mostrar la interfaz de chat sin el input"""
    st.header("💬 Asistente Inteligente")
    st.markdown("Pregunta lo que necesites saber sobre los trámites digitales en lenguaje natural")
    
    # Verificar si el sistema está listo
    if st.session_state.system_ready is None:
        with st.spinner("Conectando con el sistema..."):
            check_system_status()
        st.rerun()
    
    if not st.session_state.system_ready:
        st.error("❌ No se puede conectar con el sistema de consultas")
        st.info("Verifica que el servicio esté funcionando y que Vanna esté entrenado")
        if st.button("🔄 Reintentar"):
            check_system_status()
            st.rerun()
        return
    
    # Ejemplos de preguntas
    with st.expander("💡 Ejemplos de preguntas que puedes hacer"):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            **Consultas básicas:**
            - ¿Cuántos usuarios están registrados?
            - ¿Cuántos formularios hay?
            - Muéstrame las tablas disponibles
            - ¿Cuántos trámites se enviaron hoy?
            
            **Preguntas de seguimiento:**
            - ¿Y cuántos fueron hombres?
            - ¿Cuáles fueron creados este mes?
            - Muéstrame los primeros 10
            - ¿Y del año pasado?
            """)
        with col2:
            st.markdown("""
            **Consultas avanzadas:**
            - Usuarios que nunca iniciaron sesión
            - ¿Cuáles son los formularios más usados?
            - Trámites pendientes de los últimos 7 días
            - Estadísticas de usuarios por mes
            
            **Comparaciones:**
            - Compara con el mes anterior
            - ¿Cuál es la diferencia con 2023?
            - ¿Qué porcentaje representa?
            """)
    
    # Historial de chat
    chat_container = st.container()
    
    with chat_container:
        for message in st.session_state.chat_history:
            with st.chat_message(message["role"]):
                st.write(message["content"])
                
                # Si es del asistente y tiene SQL, mostrarlo
                if message["role"] == "assistant" and "sql" in message:
                    with st.expander("Ver SQL generado"):
                        st.code(message["sql"], language="sql")

def process_chat_input(prompt):
    """Procesar el input del chat con memoria conversacional"""
    # Agregar mensaje del usuario
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    
    # Preparar historial de conversación para el backend
    # Solo enviar las últimas 5 interacciones para no sobrecargar
    conversation_history = []
    for msg in st.session_state.chat_history[-10:]:  # Últimas 10 mensajes (5 pares pregunta-respuesta)
        if msg["role"] == "user":
            # Buscar la respuesta correspondiente
            user_idx = st.session_state.chat_history.index(msg)
            if user_idx + 1 < len(st.session_state.chat_history):
                assistant_msg = st.session_state.chat_history[user_idx + 1]
                if assistant_msg["role"] == "assistant":
                    conversation_history.append({
                        "question": msg["content"],
                        "answer": assistant_msg["content"],
                        "sql": assistant_msg.get("sql", "")
                    })
    
    # Procesar con Vanna incluyendo el historial
    result = make_api_request("/mindsdb/chat", "POST", {
        "query": prompt,
        "session_id": st.session_state.chat_session_id,
        "conversation_history": conversation_history
    }, st.session_state.token)
    
    if result["success"] and result["data"].get("success"):
        answer = result["data"].get("answer", "No pude procesar tu pregunta")
        sql = result["data"].get("sql", None)
        
        # Agregar al historial
        message_data = {
            "role": "assistant", 
            "content": answer
        }
        if sql:
            message_data["sql"] = sql
        
        st.session_state.chat_history.append(message_data)
        
    else:
        error_msg = "❌ No pude procesar tu pregunta. Intenta reformularla de manera más específica."
        
        st.session_state.chat_history.append({
            "role": "assistant", 
            "content": error_msg + "\n\n💡 Tips: Menciona nombres de tablas específicas o usa términos como 'usuarios', 'formularios', 'trámites'"
        })

def data_explorer():
    """Explorador de datos mejorado"""
    st.header("🔍 Explorador de Datos")
    st.markdown("Explora la estructura y contenido de las tablas disponibles")
    
    if not st.session_state.mysql_tables:
        st.info("Cargando información de las tablas...")
        if st.button("🔄 Cargar Tablas"):
            load_mysql_info()
            st.rerun()
        return
    
    # Selector de tabla
    selected_table = st.selectbox(
        "Selecciona una tabla para explorar:",
        [""] + st.session_state.mysql_tables,
        format_func=lambda x: "Selecciona una tabla..." if x == "" else x
    )
    
    if selected_table:
        tab1, tab2, tab3 = st.tabs(["📋 Estructura", "📊 Muestra de Datos", "❓ Consulta Personalizada"])
        
        with tab1:
            with st.spinner(f"Cargando estructura de {selected_table}..."):
                result = make_api_request(f"/mysql/table/{selected_table}", "GET", token=st.session_state.token)
                if result["success"]:
                    if 'data' in result["data"] and result["data"]['data']:
                        # Convertir a DataFrame con nombres de columnas correctos
                        columns = ['Field', 'Type', 'Null', 'Key', 'Default', 'Extra']
                        df = pd.DataFrame(result["data"]['data'], columns=columns)
                        
                        # Mostrar información resumida
                        st.metric("Total de campos", len(df))
                        
                        # Mostrar tabla formateada
                        st.dataframe(
                            df,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "Field": st.column_config.TextColumn("Campo", width="medium"),
                                "Type": st.column_config.TextColumn("Tipo", width="medium"),
                                "Null": st.column_config.TextColumn("Nulo", width="small"),
                                "Key": st.column_config.TextColumn("Llave", width="small"),
                                "Default": st.column_config.TextColumn("Default", width="small"),
                                "Extra": st.column_config.TextColumn("Extra", width="small"),
                            }
                        )
        
        with tab2:
            num_rows = st.slider("Número de registros a mostrar:", 5, 50, 10)
            if st.button("📥 Cargar Muestra"):
                with st.spinner(f"Cargando datos de {selected_table}..."):
                    result = make_api_request("/mysql/query", "POST", {
                        "query": f"SELECT * FROM {selected_table} LIMIT {num_rows}"
                    }, st.session_state.token)
                    
                    if result["success"] and result["data"].get("success"):
                        if result["data"]['data']:
                            df = pd.DataFrame(result["data"]['data'])
                            st.dataframe(df, use_container_width=True, hide_index=True)
                            
                            # Opción de descarga
                            csv = df.to_csv(index=False)
                            st.download_button(
                                label="📥 Descargar CSV",
                                data=csv,
                                file_name=f"{selected_table}_sample.csv",
                                mime="text/csv"
                            )
                        else:
                            st.info("La tabla está vacía")
                    else:
                        st.error("Error al cargar los datos")
        
        with tab3:
            st.markdown("**Escribe una consulta SQL personalizada:**")
            custom_query = st.text_area(
                "SQL Query",
                value=f"SELECT * FROM {selected_table} WHERE ",
                height=100
            )
            
            if st.button("▶️ Ejecutar Consulta"):
                with st.spinner("Ejecutando consulta..."):
                    result = make_api_request("/mysql/query", "POST", {
                        "query": custom_query
                    }, st.session_state.token)
                    
                    if result["success"] and result["data"].get("success"):
                        if result["data"]['data']:
                            df = pd.DataFrame(result["data"]['data'])
                            st.success(f"✅ {len(df)} registros encontrados")
                            st.dataframe(df, use_container_width=True, hide_index=True)
                        else:
                            st.info("La consulta no devolvió resultados")
                    else:
                        st.error(f"Error: {result['data'].get('error', 'Error desconocido')}")

def display_history():
    """Mostrar historial de conversación"""
    st.header("📜 Historial de Conversación")
    
    if st.session_state.chat_history:
        # Estadísticas
        col1, col2, col3 = st.columns(3)
        with col1:
            user_questions = [m for m in st.session_state.chat_history if m["role"] == "user"]
            st.metric("Total de preguntas", len(user_questions))
        with col2:
            assistant_responses = [m for m in st.session_state.chat_history if m["role"] == "assistant"]
            st.metric("Respuestas generadas", len(assistant_responses))
        with col3:
            sql_queries = [m for m in st.session_state.chat_history if m.get("sql")]
            st.metric("Consultas SQL", len(sql_queries))
        
        st.markdown("---")
        
        # Exportar conversación
        if st.button("📥 Exportar Conversación"):
            conversation_text = ""
            for msg in st.session_state.chat_history:
                role = "Usuario" if msg["role"] == "user" else "Asistente"
                conversation_text += f"{role}: {msg['content']}\n"
                if msg.get("sql"):
                    conversation_text += f"SQL: {msg['sql']}\n"
                conversation_text += "\n"
            
            st.download_button(
                label="Descargar TXT",
                data=conversation_text,
                file_name=f"conversacion_{st.session_state.chat_session_id[:8]}.txt",
                mime="text/plain"
            )
        
        # Mostrar historial
        st.subheader("Conversación Completa")
        for i, message in enumerate(st.session_state.chat_history):
            if message["role"] == "user":
                st.markdown(f"**🧑 Usuario:** {message['content']}")
            else:
                st.markdown(f"**🤖 Asistente:** {message['content']}")
                if message.get("sql"):
                    with st.expander("Ver SQL"):
                        st.code(message["sql"], language="sql")
            st.markdown("---")
    else:
        st.info("No hay conversaciones aún. Ve a la pestaña Asistente y comienza haciendo una pregunta.")

def main_interface():
    st.title(f"👋 Hola, {st.session_state.username}")
    st.markdown("### Sistema de Consultas Inteligentes para Trámites Digitales")
    
    # Verificar estado del sistema
    if st.session_state.system_ready is None:
        check_system_status()
    
    # Sidebar
    smart_sidebar()
    
    # Pestañas principales
    tabs = st.tabs([
        "💬 Asistente", 
        "🔍 Explorar Datos", 
        "📜 Historial"
    ])
    
    # Guardar qué tab está activo
    for i, tab in enumerate(tabs):
        with tab:
            if i == 0:  # Tab Asistente
                display_chat_interface()
            elif i == 1:  # Tab Explorador
                data_explorer()
            elif i == 2:  # Tab Historial
                display_history()
    
    # Chat input FUERA de los tabs - solo visible cuando estamos en el tab del asistente
    if st.session_state.get('active_tab', 0) == 0 or True:  # Siempre visible por simplicidad
        prompt = st.chat_input("Escribe tu pregunta aquí...")
        if prompt:
            process_chat_input(prompt)
            st.rerun()

def main():
    initialize_session_state()
    
    if not st.session_state.authenticated:
        login_page()
    else:
        # Cargar datos iniciales
        if not st.session_state.mysql_tables:
            load_mysql_info()
        
        main_interface()

if __name__ == "__main__":
    main()