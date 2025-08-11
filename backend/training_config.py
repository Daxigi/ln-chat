"""
Este archivo es OPCIONAL. Contiene ejemplos de datos de entrenamiento
que puedes usar para entrenar Vanna inicialmente.

Uso:
    from training_config import train_initial_data
    from vanna_service import VannaChromaDB
    
    vn = VannaChromaDB()
    train_initial_data(vn)
"""

# Tablas a entrenar (modifica según tu base de datos)
SELECTED_TABLES = [
    "users",
    "requests", 
    "request_states",
    "procedures",
    "request_state_records",
    "request_actions",
    "actions",
    "roles",
    "model_has_roles",
    "procedures_statuses",
]

# Documentación de negocio
DOCUMENTATION = [
    "USERS: La tabla 'users' contiene la información de todos los usuarios registrados en el sistema.",
    "Los usuarios con el campo 'deleted_at' en NULL son considerados usuarios activos.",
    "REQUESTS: La tabla 'requests' almacena todas las solicitudes de trámites iniciadas por los usuarios.",
    "PROCEDURES: La tabla 'procedures' es el catálogo de los tipos de trámites que se pueden solicitar.",
    "Los trámites con 'procedure_status_id' = 1 son trámites activos que los usuarios pueden iniciar.",
    "REQUEST_STATES: La tabla 'request_states' describe los posibles estados de una solicitud (ej: 'Iniciado', 'En proceso', 'Finalizado').",
    "REQUEST_STATE_RECORDS: La tabla 'request_state_records' guarda el historial de cambios de estado para cada solicitud.",
    "El estado actual de una solicitud se determina por su registro más reciente en la tabla 'request_state_records'.",
    "Siempre que se hable de solicitudes, se deben excluir aquellas cuyo campo 'deleted_at' no sea NULL.",
    "El campo 'current_role' de un usuario solo representa el rol activo mientras está logueado en la página. Un usuario puede tener múltiples roles asociados a través de la tabla intermedia 'model_has_roles'.",
    "Relaciones: 'users.id' → 'requests.user_id', 'procedures.id' → 'requests.procedure_id', 'request_states.id' → 'request_state_records.request_state_id', 'requests.id' → 'request_state_records.request_id'.",
    "Una 'solicitud con último estado borrador' es aquella cuyo registro más reciente en 'request_state_records' tenga 'request_state_id' correspondiente a 'borrador'.",
    "Para obtener las solicitudes que hizo un usuario en un periodo, se debe filtrar por 'users.dni' y 'requests.created_at' dentro del rango de fechas especificado.",
    "Las solicitudes con 'deleted_at' distinto de NULL deben ser excluidas de todos los conteos y listados.",
    "Al contar solicitudes por estado, se debe considerar el último estado registrado para cada solicitud, no todos los históricos.",
    "Si se solicita 'todas las solicitudes que hizo un DNI en un periodo', se debe hacer join entre 'users', 'requests' y 'procedures', filtrando por 'users.dni' y rango de fechas en 'requests.created_at'.",
]

# Ejemplos de preguntas y SQL
SQL_EXAMPLES = [
    {
        "question": "¿Cuántos usuarios hay?",
        "sql": "SELECT COUNT(*) FROM users WHERE deleted_at IS NULL;"
    },
    {
        "question": "¿Cuántos usuarios nuevos se registraron entre dos fechas específicas (ej: 01/01/2024 y 31/01/2024)?",
        "sql": "SELECT COUNT(*) AS total_usuarios_nuevos FROM users WHERE created_at BETWEEN '2024-01-01 00:00:00' AND '2024-01-31 23:59:59';"
    },
    {
        "question": "¿Qué usuarios tienen el rol de 'Agente'?",
        "sql": "SELECT u.name, u.dni FROM users u JOIN model_has_roles mhr ON u.id = mhr.model_id WHERE mhr.role_id = 4;"
    },
    {
        "question": "¿Cuántos cambios de estado realizó en total el agente con DNI 12345678?",
        "sql": "SELECT COUNT(*) FROM request_state_records rsr JOIN users u ON rsr.user_id = u.id WHERE u.dni = '12345678';"
    },
    {
        "question": "¿Cuántas veces el agente con ID 5 cambió un estado a 'Finalizado' (ID 4)?",
        "sql": "SELECT COUNT(*) FROM request_state_records WHERE user_id = 5 AND request_status_id = 4;"
    },
    {
        "question": "cuantas solicitudes se crearon hoy?",
        "sql": "SELECT COUNT(*) FROM requests WHERE DATE(created_at) = CURDATE();"
    },
    {
        "question": "Cuantas solicitudes hay actualmente en cada estado?",
        "sql" : "WITH ultimo_estado AS ( SELECT request_status_id, ROW_NUMBER() OVER (PARTITION BY request_id ORDER BY date DESC) AS rn FROM request_state_records ) SELECT rs.description, COUNT(*) AS total FROM ultimo_estado ue JOIN request_states rs ON ue.request_status_id = rs.id WHERE ue.rn = 1 GROUP BY rs.description;"
    },
    {
        "question": "Cuantas solicitudes estan en estado En Proceso?",
        "sql": "WITH ultimo_estado AS (SELECT request_status_id, ROW_NUMBER() OVER (PARTITION BY request_id ORDER BY date DESC) AS rn FROM request_state_records ) SELECT COUNT(*) FROM ultimo_estado WHERE rn = 1 AND request_status_id = 3;"
    },
]


def train_initial_data(vn):
    """
    Función helper para entrenar Vanna con los datos iniciales.
    
    Args:
        vn: Instancia de VannaChromaDB
    """
    print("🚀 Iniciando entrenamiento...")
    
    # 1. Entrenar con DDLs de las tablas
    print("\n📊 Entrenando DDLs...")
    for table in SELECTED_TABLES:
        try:
            ddl = vn.get_table_ddl(table)
            if ddl:
                vn.train(ddl=ddl)
                print(f"  ✅ {table}")
        except Exception as e:
            print(f"  ❌ {table}: {e}")
    
    # 2. Entrenar con documentación
    print("\n📚 Entrenando documentación...")
    for doc in DOCUMENTATION:
        vn.train(documentation=doc)
        print(f"  ✅ Agregada documentación")
    
    # 3. Entrenar con ejemplos SQL
    print("\n💾 Entrenando ejemplos SQL...")
    for example in SQL_EXAMPLES:
        vn.train(question=example['question'], sql=example['sql'])
        print(f"  ✅ {example['question'][:50]}...")
    
    print("\n✨ ¡Entrenamiento completado!")


# Script para ejecutar directamente
if __name__ == "__main__":
    from vanna_service import VannaChromaDB
    
    vn = VannaChromaDB()
    train_initial_data(vn)