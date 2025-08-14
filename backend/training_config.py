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
    "FACT: ROLES => 1=Administrador, 2=Editor, 3=Visualizador, 4=Agente, 5=Vecino Nivel 1, 6=Vecino Nivel 2, 7=Vecino Nivel 3, 8=Vecino Nivel 4, 9=Supervisor, 16=Tractas, 17=Obras.",
    "FACT: REQUEST_STATES (CANONICO) => 1=Borrador, 2=Publicado, 3=En proceso, 4=Finalizado, 5=Rechazado, 6=Revocado (usar estos nombres exactamente).",
    "FACT: MODEL_HAS_ROLES => tabla polimórfica; para usuarios unir por mhr.model_id = users.id Y mhr.model_type='App\\\\Models\\\\User'.",
    "FACT: REQUEST_STATE_RECORDS => historial de estados por solicitud; estado actual = registro con mayor fecha (MAX(date)) o ROW_NUMBER() rn=1 (ORDER BY date DESC) | ANCHOR: USE_ROW_NUMBER_RN_1.",
    "FACT: REQUEST_STATES_DESC => catálogo textual de estados; usar 'Borrador','Publicado','En proceso','Finalizado','Rechazado','Revocado'.",
    "FACT: PROCEDURES => los trámites activos tienen procedure_status_id=1 (relevantes por defecto).",
    "FACT: PROCEDURES_DESC => catálogo de tipos de trámites (p.name).",
    "FACT: REQUESTS => almacena todas las solicitudes de trámites; requests.deleted_at IS NULL = no eliminada (no confundir con estado).",
    "FACT: USERS => users.current_role = rol activo en sesión; para todos los roles usar model_has_roles.",
    "FACT: USERS_ACTIVE => users.deleted_at IS NULL = usuario activo.",
    "FACT: USERS_DESC => información de usuarios; DNI = users.dni.",
    "RULE: SOFT_DELETE (STRICT: ALWAYS | ANCHOR: SOFT_DELETE) => en TODA consulta a requests incluir SIEMPRE r.deleted_at IS NULL (si no hay alias: requests.deleted_at IS NULL).",
    "RULE: NO_NAMED_PARAMS (STRICT: ALWAYS) => la SQL generada NO debe usar placeholders con dos puntos (:start_date/:end_next); usar literales o el placeholder correcto del driver (%s, ?).",
    "RULE: RANGE_SEMIABIERTO (ANCHOR: RANGE_SEMIABIERTO) => filtrar fechas con r.col >= '[INICIO] 00:00:00' Y r.col < '[FIN+1] 00:00:00'; evitar MONTH()/YEAR(col) para preservar índices.",
    "RULE: NUMBER_IS_DNI (STRICT: ALWAYS) => si la pregunta incluye un número y no dice 'expediente/reference/id', interpretarlo como users.dni; NO usar r.user_id ni r.reference_number.",
    "RULE: REQUIRE_USERS_JOIN (STRICT: ALWAYS) => si se filtra por DNI, unir SIEMPRE users u (r.user_id=u.id) y filtrar por u.dni='[DNI]'.",
    "RULE: REQUIRE_PROCEDURE_FILTER (STRICT: ALWAYS) => si la pregunta menciona un trámite, filtrar SIEMPRE por procedures.name (= o LIKE).",
    "RULE: FECHAS_RELATIVAS => normalizar 'hoy/ayer/últimos N días/mes pasado...' a fechas absolutas (TZ America/Argentina/Cordoba) antes de generar SQL; exponer [INICIO] y [FIN+1].",
    "INTENT: SOLICITUDES_POR_TRAMITE_RANGO | ANCHOR: SOFT_DELETE RANGE_SEMIABIERTO | STRICT: ALWAYS => contar requests por p.name (= o LIKE) con r.start_date en rango semiabierto; incluir SIEMPRE r.deleted_at IS NULL; agrupar por p.name; ordenar por cantidad DESC.",
    "INTENT: ESTADO_FINAL_POR_TRAMITE | ANCHOR: USE_ROW_NUMBER_RN_1 SOFT_DELETE | STRICT: ALWAYS => usar SOLO último estado por request (ROW_NUMBER PARTITION BY r.id ORDER BY rsr.date DESC; rn=1), filtrar periodo por r.created_at, excluir r.deleted_at IS NULL, agrupar por p.name y rs.description; NO usar rsr.deleted_at ni rsr.procedure_id.",
    "INTENT: ULTIMO_ESTADO_ULTIMA_SOLICITUD | ANCHOR: USE_SUBQUERY_LAST_REQUEST USE_ROW_NUMBER_RN_1 SOFT_DELETE | STRICT: ALWAYS => dado un DNI y un trámite (= o LIKE), unir r–u–p; filtrar por u.dni y p.name; excluir r.deleted_at IS NULL; elegir SOLO la última solicitud (ORDER BY r.created_at DESC LIMIT 1) y devolver el ÚLTIMO estado (rn=1 o MAX(date)).",
    "INTENT: BACKLOG_ABIERTAS | ANCHOR: SOFT_DELETE | STRICT: ALWAYS => contar requests con finish_date IS NULL y r.start_date en rango (semiabierto); incluir r.deleted_at IS NULL; opcionalmente r.start_date <= (fecha_actual - (days+1)).",
    "INTENT: TRAMITES_ATENDIDOS_POR_AGENTE | ANCHOR: AGENT_RSR | STRICT: PREFER => contar en request_state_records rsr donde rsr.user_id = users.id del AGENTE (por DNI); unir a requests r y procedures p para nombres de trámite; aplicar reglas de fechas y SOFT_DELETE en requests si corresponde.",
    "VOCAB: sinonimos => 'solicitudes/tickets/casos'→requests; 'trámite'→procedures.name; 'estado'→request_states.description; 'dni/documento'→users.dni; 'expediente/nro solicitud/reference'→requests.reference_number; 'última'→ORDER BY r.created_at DESC LIMIT 1; 'estado actual'→ROW_NUMBER rn=1 por fecha en request_state_records."
]

# Ejemplos de preguntas y SQL
SQL_EXAMPLES = [
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