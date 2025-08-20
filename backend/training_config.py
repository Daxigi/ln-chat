# training_config.py (Versión Refactorizada y Actualizada)

from vanna_service import VannaChromaDB

# ==============================================================================
# == 1. DEFINE LAS TABLAS Y LOS DATOS DE ENTRENAMIENTO POR TÓPICO
# ==============================================================================

# Tablas base que son relevantes para TODOS los tópicos.
# El script entrenará estas tablas en cada uno de los tópicos que definas abajo.
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

# Aquí es donde organizas tu entrenamiento.
# Crea una entrada por cada área de negocio que quieras separar.
TRAINING_DATA_BY_TOPIC = {
    # --- TÓPICO: general ---
    # Contiene reglas y definiciones que aplican a casi todas las consultas.
    "general": {
        "documentation": [
            "SOLICITUDES: Siempre excluir las eliminadas usando 'deleted_at IS NULL'.",
            "ESTADOS DE SOLICITUD: Los códigos de estado son: 1 = Borrador, 2 = Publicado, 3 = En Proceso, 4 = Finalizado, 5 = Rechazado, 6 = Revocado.",
        ],
        "sql_examples": []
    },
    
    # --- TÓPICO: usuarios_y_roles ---
    # Todo lo relacionado con usuarios, permisos y roles.
    "usuarios_y_roles": {
        "documentation": [
            "USERS: Contiene la información de todos los usuarios registrados en el sistema.",
            "USERS: Los usuarios con el campo 'deleted_at' en NULL son considerados usuarios activos.",
            "USERS: El campo 'current_role' representa el rol activo mientras un usuario está logueado.",
            "ROLES: Los roles existentes son: 1 = Administrador, 2 = Editor, 3 = Visualizador, 4 = Agente, 5 = Vecino Nivel 1, 6 = Vecino Nivel 2, 7 = Vecino Nivel 3, 8 = Vecino Nivel 4, 9 = Supervisor, 16 = Tractas, 17 = Obras.",
            "MODEL_HAS_ROLES: Tabla intermedia que asocia usuarios con roles. Un usuario puede tener más de un rol.",
            "MODEL_HAS_ROLES: El campo model_id se asocia con users.id.",
            "ROLES: Para filtrar por agentes, usar roles con id = 4.",
            "ROLES: Para vecinos, usar ids entre 5 y 8.",
            "MODEL_HAS_ROLES: Validar que model_type = 'App\\\\Models\\\\User' para usuarios normales.",
        ],
        "sql_examples": [
            {
                "question": "¿Qué roles tiene asignado un usuario según su DNI?",
                "sql": "SELECT r.id AS rol_id, r.name AS rol FROM users u JOIN model_has_roles mhr ON mhr.model_id = u.id AND mhr.model_type = 'App\\\\Models\\\\User' JOIN roles r ON r.id = mhr.role_id WHERE u.dni = :dni;"
            }
        ]
    },
    
    # --- TÓPICO: solicitudes_y_tramites ---
    # El corazón del negocio: solicitudes, trámites y sus estados.
    "solicitudes_y_tramites": {
        "documentation": [
            "REQUESTS: Almacena todas las solicitudes de trámites iniciadas por los usuarios.",
            "REQUESTS: Las solicitudes con 'deleted_at' en NULL están vigentes (no eliminadas).",
            "REQUESTS: Para contar solicitudes abiertas, usar 'finish_date IS NULL'.",
            "REQUESTS: Para contar solicitudes en un rango, usar 'start_date BETWEEN :inicio AND :fin'.",
            "REQUESTS: start_date = fecha en que inicia el trámite.",
            "REQUESTS: finish_date = fecha en que finaliza (puede ser NULL si sigue en curso).",
            "PROCEDURES: Es el catálogo de los tipos de trámites disponibles.",
            "PROCEDURES: Los trámites con 'procedure_status_id' = 1 son los activos por defecto.",
            "REQUEST_STATES: Describe los posibles estados de una solicitud (Borrador, Publicado, En Proceso, Finalizado, Rechazado, Revocado).",
            "REQUEST_STATE_RECORDS: Guarda el historial de cambios de estado para cada solicitud.",
            "REQUEST_STATE_RECORDS: El estado actual de una solicitud es su registro más reciente (por fecha).",
            "REQUEST_STATE_RECORDS: Para saber qué agente atendió un trámite, buscar el user_id en el último registro de esta tabla.",
            "TRÁMITES: Para contar solicitudes por trámite y estado, usar el último estado de cada request (ROW_NUMBER OVER PARTITION BY).",
            "CONSULTA SOLICITUD: Dado un DNI y nombre parcial del trámite, unir requests con users (por user_id) y procedures (por procedure_id).",
            "CONSULTA SOLICITUD: Filtrar por u.dni='[DNI]' y p.name LIKE '%[TRÁMITE]%'.",
            "CONSULTA SOLICITUD: Excluir eliminadas con r.deleted_at IS NULL.",
            "CONSULTA SOLICITUD: Tomar solo la última solicitud del usuario para ese trámite (ORDER BY created_at DESC LIMIT 1).",
            "CONSULTA SOLICITUD: Obtener el estado actual usando el último cambio en request_state_records (por fecha DESC)."
        ],
        "sql_examples": [
            {
                "question": "¿Cuántas solicitudes tuvo cada trámite por estado en un rango de fechas?",
                "sql": "WITH ultimo_estado AS (SELECT r.id AS request_id, p.name AS tramite, rs.description AS estado, r.created_at, ROW_NUMBER() OVER (PARTITION BY r.id ORDER BY rsr.date DESC) AS rn FROM requests r JOIN request_state_records rsr ON rsr.request_id = r.id JOIN request_states rs ON rsr.request_status_id = rs.id JOIN procedures p ON p.id = r.procedure_id WHERE r.created_at BETWEEN :inicio AND :fin AND r.deleted_at IS NULL) SELECT tramite, SUM(CASE WHEN estado = 'Borrador' THEN 1 ELSE 0 END) AS borrador, SUM(CASE WHEN estado = 'Publicado' THEN 1 ELSE 0 END) AS publicado, SUM(CASE WHEN estado = 'En proceso' THEN 1 ELSE 0 END) AS en_proceso, SUM(CASE WHEN estado = 'Finalizado' THEN 1 ELSE 0 END) AS finalizado, SUM(CASE WHEN estado = 'Rechazado' THEN 1 ELSE 0 END) AS rechazado, SUM(CASE WHEN estado = 'Revocado' THEN 1 ELSE 0 END) AS revocado, COUNT(*) AS total FROM ultimo_estado WHERE rn = 1 GROUP BY tramite ORDER BY tramite;"
            },
            {
                "question": "¿Cuál es el estado actual de la última solicitud de un usuario según su DNI y un nombre parcial del trámite?",
                "sql": "SELECT u.name AS usuario, p.name AS tramite, r.start_date AS fecha_inicio, r.finish_date AS fecha_fin, rs.description AS estado_actual FROM requests r JOIN users u ON r.user_id = u.id JOIN procedures p ON r.procedure_id = p.id JOIN (SELECT rsr1.* FROM request_state_records rsr1 JOIN (SELECT request_id, MAX(date) AS max_date FROM request_state_records GROUP BY request_id) latest ON rsr1.request_id = latest.request_id AND rsr1.date = latest.max_date) rsr ON rsr.request_id = r.id JOIN request_states rs ON rs.id = rsr.request_status_id WHERE u.dni = :dni AND p.name LIKE CONCAT('%', :tramite, '%') AND r.id = (SELECT r2.id FROM requests r2 JOIN procedures p2 ON r2.procedure_id = p2.id WHERE r2.user_id = u.id AND p2.name LIKE CONCAT('%', :tramite, '%') ORDER BY r2.created_at DESC LIMIT 1);"
            },
            {
                "question": "¿Cuántas veces un agente cambió el estado de trámites en un rango de fechas, filtrando por su DNI y ciertos estados específicos?",
                "sql": "SELECT u.name AS agente, u.dni, p.name AS tramite, COUNT(*) AS cantidad_cambios FROM request_state_records rsr JOIN users u ON u.id = rsr.user_id JOIN request_states rs ON rs.id = rsr.request_status_id JOIN requests r ON r.id = rsr.request_id JOIN procedures p ON p.id = r.procedure_id JOIN model_has_roles mhr ON mhr.model_id = u.id JOIN roles ro ON ro.id = mhr.role_id WHERE ro.id = 4 AND u.dni = :dni AND rsr.created_at BETWEEN :inicio AND :fin AND rs.id IN (:estado_ids) GROUP BY u.name, u.dni, p.name, rs.description;"
            },
            {
                "question": "¿Qué trámites activos están retrasados según su fecha de inicio y un rango de demora configurable?",
                "sql": "SELECT p.name AS nombre_del_tramite, COUNT(r.id) AS cantidad_de_retrasos FROM procedures p JOIN requests r ON r.procedure_id = p.id WHERE p.procedure_status_id = 1 AND r.finish_date IS NULL AND r.start_date BETWEEN DATE_SUB(:current_date, INTERVAL :delay_end_days DAY) AND DATE_SUB(:current_date, INTERVAL :delay_start_days DAY) AND r.start_date BETWEEN :filter_start_date AND :filter_end_date GROUP BY p.name HAVING COUNT(r.id) > 0;"
            }
        ]
    }
}


# ==============================================================================
# == 2. LÓGICA DE ENTRENAMIENTO (NO NECESITAS MODIFICAR ESTO)
# ==============================================================================

def train_topic_data(vn: VannaChromaDB, topic: str, tables: list, doc: list, sql: list):
    """
    Función helper que entrena los datos para UN tópico específico.
    """
    print("\n" + "="*50)
    print(f"🚀 Iniciando entrenamiento en el tópico: '{topic}'")
    print("="*50)
    
    # 1. Entrenar con DDLs de las tablas
    print("\n📊 Entrenando DDLs...")
    for table in tables:
        try:
            ddl = vn.get_table_ddl(table)
            if ddl:
                vn.train(ddl=ddl, topic=topic)
                print(f"  ✅ {table}")
        except Exception as e:
            print(f"  ❌ {table}: {e}")
    
    # 2. Entrenar con documentación
    print("\n📚 Entrenando documentación...")
    for d in doc:
        vn.train(documentation=d, topic=topic)
    print(f"  ✅ Agregados {len(doc)} documentos.")
    
    # 3. Entrenar con ejemplos SQL
    print("\n💾 Entrenando ejemplos SQL...")
    for example in sql:
        vn.train(question=example['question'], sql=example['sql'], topic=topic)
    print(f"  ✅ Agregados {len(sql)} ejemplos SQL.")
    
    print(f"\n✨ ¡Entrenamiento para el tópico '{topic}' completado!")


# Script para ejecutar directamente
if __name__ == "__main__":
    vn = VannaChromaDB()
    
    # Iterar sobre el diccionario y entrenar cada tópico
    for topic_name, training_content in TRAINING_DATA_BY_TOPIC.items():
        train_topic_data(
            vn=vn,
            topic=topic_name,
            tables=SELECTED_TABLES, # Usamos las mismas tablas para todos los tópicos
            doc=training_content.get("documentation", []),
            sql=training_content.get("sql_examples", [])
        )
    
    print("\n" + "="*50)
    print("🎉🎉🎉 TODO EL ENTRENAMIENTO HA FINALIZADO 🎉🎉🎉")
    print("="*50)