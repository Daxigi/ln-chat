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
]

# Documentación de negocio
DOCUMENTATION = [
    "La tabla 'users' contiene la información de todos los usuarios registrados en el sistema.",
    "Los usuarios con el campo 'deleted_at' en NULL son considerados usuarios activos.",
    "La tabla 'requests' almacena todas las solicitudes de trámites iniciadas por los usuarios.",
    "La tabla 'procedures' es el catálogo de los tipos de trámites que se pueden solicitar.",
    "Los trámites con 'procedure_status_id' = 1 son trámites activos que los usuarios pueden iniciar.",
    "La tabla 'request_states' describe los posibles estados de una solicitud (ej: 'Iniciado', 'En proceso', 'Finalizado').",
    "La tabla 'request_state_records' guarda el historial de cambios de estado para cada solicitud.",
    "El estado actual de una solicitud se determina por su registro más reciente en la tabla 'request_state_records'."
]

# Ejemplos de preguntas y SQL
SQL_EXAMPLES = [
    {
        "question": "¿Cuántos usuarios hay en total?",
        "sql": "SELECT COUNT(*) as total_users FROM users"
    },
    {
        "question": "¿Cuántos usuarios totales hay registrados en el sistema?",
        "sql": "SELECT COUNT(*) AS total_usuarios FROM users;"
    },
    {
        "question": "¿Cuántos usuarios activos (no eliminados lógicamente) hay?",
        "sql": "SELECT COUNT(*) AS total_usuarios_activos FROM users WHERE deleted_at IS NULL;"
    },
    {
        "question": "¿Cuántos usuarios nuevos se registraron entre dos fechas específicas (ej: 01/01/2024 y 31/01/2024)?",
        "sql": "SELECT COUNT(*) AS total_usuarios_nuevos FROM users WHERE created_at BETWEEN '2024-01-01 00:00:00' AND '2024-01-31 23:59:59';"
    },
    {
        "question": "Obtener el listado de usuarios (ID, nombre, email) que se registraron en un período de tiempo determinado.",
        "sql": "SELECT id, name, surname, email, created_at FROM users WHERE created_at BETWEEN '2024-01-01 00:00:00' AND '2024-01-31 23:59:59';"
    },
    
    {
        "question": "¿Cuántas solicitudes se publicaron (iniciaron) en un rango de fechas?",
        "sql": "SELECT COUNT(*) AS total_solicitudes_publicadas FROM requests WHERE start_date BETWEEN '2024-01-01 00:00:00' AND '2024-01-31 23:59:59';"
    },
    {
        "question": "¿Cuál es el recuento de todas las solicitudes agrupadas por su estado actual (el más reciente)?",
        "sql": "SELECT rs.description AS estado_actual, COUNT(r.id) AS cantidad\nFROM requests r\nINNER JOIN (\n    -- Subconsulta para obtener el ID del último estado de cada solicitud\n    SELECT rsr.request_id, rsr.request_status_id\n    FROM request_state_records rsr\n    INNER JOIN (\n        SELECT request_id, MAX(date) AS max_date\n        FROM request_state_records\n        GROUP BY request_id\n    ) latest_rsr ON rsr.request_id = latest_rsr.request_id AND rsr.date = latest_rsr.max_date\n) current_status ON r.id = current_status.request_id\nINNER JOIN request_states rs ON current_status.request_status_id = rs.id\nGROUP BY rs.description\nORDER BY cantidad DESC;"
    },
    {
        "question": "Listar las solicitudes iniciadas en un rango de fechas que actualmente se encuentran en un estado específico (ej: 'En proceso').",
        "sql": "SELECT r.id AS solicitud_id, r.start_date, p.name AS tramite, u.email AS solicitante, rs.description as estado_actual\nFROM requests r\nINNER JOIN (\n    -- Subconsulta para obtener el ID del último estado de cada solicitud\n    SELECT rsr.request_id, rsr.request_status_id\n    FROM request_state_records rsr\n    INNER JOIN (\n        SELECT request_id, MAX(date) AS max_date\n        FROM request_state_records\n        GROUP BY request_id\n    ) latest_rsr ON rsr.request_id = latest_rsr.request_id AND rsr.date = latest_rsr.max_date\n) current_status ON r.id = current_status.request_id\nINNER JOIN request_states rs ON current_status.request_status_id = rs.id\nINNER JOIN procedures p ON r.procedure_id = p.id\nINNER JOIN users u ON r.user_id = u.id\nWHERE r.start_date BETWEEN '2024-01-01 00:00:00' AND '2024-01-31 23:59:59' AND rs.description = 'En proceso';"
    },
    {
        "question": "¿Cuántas solicitudes hay por cada tipo de trámite activo (no en borrador)?",
        "sql": "SELECT p.name AS tipo_de_tramite, COUNT(r.id) AS cantidad_solicitudes\nFROM requests r\nINNER JOIN procedures p ON r.procedure_id = p.id\nWHERE p.procedure_status_id = 1 -- Asumiendo que el estado 1 es 'publicado' o 'activo'\nGROUP BY p.name\nORDER BY cantidad_solicitudes DESC;"
    },
    {
        "question": "¿Cuántas solicitudes se iniciaron entre dos fechas, agrupadas por tipo de trámite?",
        "sql": "SELECT p.name AS tipo_de_tramite, COUNT(r.id) AS cantidad_solicitudes\nFROM requests r\nINNER JOIN procedures p ON r.procedure_id = p.id\nWHERE r.start_date BETWEEN '2024-01-01 00:00:00' AND '2024-01-31 23:59:59' AND p.procedure_status_id = 1\nGROUP BY p.name\nORDER BY cantidad_solicitudes DESC;"
    },
    {
        "question": "¿Cuántas solicitudes del trámite 'Licencia de Conducir' se iniciaron en un período de tiempo?",
        "sql": "SELECT COUNT(r.id) AS cantidad_licencias\nFROM requests r\nINNER JOIN procedures p ON r.procedure_id = p.id\nWHERE p.name = 'Licencia de Conducir' -- Usar el nombre exacto del trámite\nAND r.start_date BETWEEN '2024-01-01 00:00:00' AND '2024-01-31 23:59:59';"
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