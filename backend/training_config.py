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
        "question": "¿Cuántos usuarios hay?",
        "sql": "SELECT COUNT(*) AS total_usuarios_activos FROM users WHERE deleted_at IS NULL;"
    },
    {
        "question": "¿Cuántos usuarios nuevos se registraron entre dos fechas específicas (ej: 01/01/2024 y 31/01/2024)?",
        "sql": "SELECT COUNT(*) AS total_usuarios_nuevos FROM users WHERE created_at BETWEEN '2024-01-01 00:00:00' AND '2024-01-31 23:59:59';"
    },
    {
        "question":"Dame un reporte que desglose por tipo de trámite y por estado final, cuántas solicitudes se iniciaron el mes pasado.",
        "sql":"WITH ultimo_estado AS (SELECT r.id AS request_id, p.name AS tramite, rs.description AS estado, ROW_NUMBER() OVER (PARTITION BY r.id ORDER BY rsr.date DESC) AS rn FROM requests r JOIN request_state_records rsr ON rsr.request_id = r.id JOIN request_states rs ON rsr.request_status_id = rs.id JOIN procedures p ON p.id = r.procedure_id WHERE DATE(r.created_at) BETWEEN :fecha_inicio AND :fecha_fin) SELECT tramite, SUM(CASE WHEN estado = 'Borrador' THEN 1 ELSE 0 END) AS borrador, SUM(CASE WHEN estado = 'Publicado' THEN 1 ELSE 0 END) AS publicado, SUM(CASE WHEN estado = 'En proceso' THEN 1 ELSE 0 END) AS en_proceso, SUM(CASE WHEN estado = 'Finalizado' THEN 1 ELSE 0 END) AS finalizado, SUM(CASE WHEN estado = 'Rechazado' THEN 1 ELSE 0 END) AS rechazado, SUM(CASE WHEN estado = 'Revocado' THEN 1 ELSE 0 END) AS revocado, COUNT(*) AS total FROM ultimo_estado WHERE rn = 1 GROUP BY tramite ORDER BY tramite;"
    },
    {
        "question":"Muéstrame un resumen general del estado actual de todas las solicitudes en el sistema, agrupadas por cada estado.",
        "sql":"WITH ultimo_estado AS (SELECT r.id AS request_id, rs.description AS estado, ROW_NUMBER() OVER (PARTITION BY r.id ORDER BY rsr.date DESC) AS rn FROM requests r JOIN request_state_records rsr ON rsr.request_id = r.id JOIN request_states rs ON rsr.request_status_id = rs.id) SELECT estado, COUNT(request_id) AS total_solicitudes FROM ultimo_estado WHERE rn = 1 GROUP BY estado ORDER BY total_solicitudes DESC;"
    },
    {
        "question":"Quiero saber el estado actual de la solicitud más reciente del trámite 'Licencia de Conducir' para el usuario con DNI 12345678.",
        "sql":"SELECT u.name AS usuario, p.name AS tramite, r.start_date AS fecha_inicio, rs.description AS estado_actual FROM requests r JOIN users u ON r.user_id = u.id JOIN procedures p ON r.procedure_id = p.id JOIN (SELECT rsr1.request_id, rsr1.request_status_id FROM request_state_records rsr1 JOIN (SELECT request_id, MAX(date) AS max_date FROM request_state_records GROUP BY request_id) latest ON rsr1.request_id = latest.request_id AND rsr1.date = latest.max_date) rsr ON rsr.request_id = r.id JOIN request_states rs ON rs.id = rsr.request_status_id WHERE u.dni = :dni_usuario AND p.name LIKE :nombre_tramite_similar AND r.id = (SELECT r2.id FROM requests r2 JOIN users u2 ON r2.user_id = u2.id JOIN procedures p2 ON r2.procedure_id = p2.id WHERE u2.dni = :dni_usuario AND p2.name LIKE :nombre_tramite_similar ORDER BY r2.created_at DESC LIMIT 1);"
    },
    {
        "question":"Necesito el desglose día por día de cuántas solicitudes activas se iniciaron la semana pasada para todos los trámites con el nombre similar a 'Licencia de Conducir'.",
        "sql":"SELECT DATE(r.start_date) AS fecha, COUNT(r.id) AS cantidad_solicitudes FROM requests r INNER JOIN procedures p ON r.procedure_id = p.id INNER JOIN (SELECT rsr.request_id, rsr.request_status_id FROM request_state_records rsr INNER JOIN (SELECT request_id, MAX(date) AS max_date FROM request_state_records GROUP BY request_id) latest_rsr ON rsr.request_id = latest_rsr.request_id AND rsr.date = latest_rsr.max_date) current_status ON r.id = current_status.request_id WHERE current_status.request_status_id != 1 AND p.procedure_status_id = 1 AND p.name LIKE :nombre_tramite_similar AND DATE(r.start_date) BETWEEN :fecha_inicio AND :fecha_fin GROUP BY fecha ORDER BY fecha ASC;"
    },
    {
        "question":"¿Cuál fue el volumen de trabajo del agente con DNI 12345678? Quiero saber cuántas solicitudes atendió o cambió de estado cada día durante este mes.",
        "sql":"SELECT u.name AS agente, u.dni, p.name AS tramite, rs.description AS estado_cambiado, COUNT(*) AS cantidad_cambios FROM request_state_records rsr JOIN users u ON u.id = rsr.user_id JOIN request_states rs ON rs.id = rsr.request_status_id JOIN requests r ON r.id = rsr.request_id JOIN procedures p ON p.id = r.procedure_id JOIN model_has_roles mhr ON mhr.model_id = u.id JOIN roles ro ON ro.id = mhr.role_id WHERE ro.id = :id_rol AND u.dni = :dni_agente AND DATE(rsr.created_at) BETWEEN :fecha_inicio AND :fecha_fin AND rs.id IN (:lista_de_estados_atendidos) GROUP BY u.name, u.dni, p.name, rs.description;"
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