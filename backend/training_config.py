# training_config.py (Versión Refactorizada)

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
    "general": {
        "documentation": [
            # -- REGLAS Y HECHOS GENERALES --
            "FACT: ROLES => 1=Administrador, 2=Editor, 3=Visualizador, 4=Agente, 5=Vecino Nivel 1, 6=Vecino Nivel 2, 7=Vecino Nivel 3, 8=Vecino Nivel 4, 9=Supervisor, 16=Tractas, 17=Obras.",
            "FACT: REQUEST_STATES (CANONICO) => 1=Borrador, 2=Publicado, 3=En proceso, 4=Finalizado, 5=Rechazado, 6=Revocado (usar estos nombres exactamente).",
            "FACT: MODEL_HAS_ROLES => tabla polimórfica; para usuarios unir por mhr.model_id = users.id Y mhr.model_type='App\\\\Models\\\\User'.",
            "RULE: SOFT_DELETE (STRICT: ALWAYS | ANCHOR: SOFT_DELETE) => en TODA consulta a requests incluir SIEMPRE r.deleted_at IS NULL.",
            "RULE: NO_NAMED_PARAMS (STRICT: ALWAYS) => la SQL generada NO debe usar placeholders con dos puntos.",
            "VOCAB: sinonimos => 'solicitudes/tickets/casos'→requests; 'trámite'→procedures.name; 'estado'→request_states.description; 'dni/documento'→users.dni.",
        ],
        "sql_examples": []
    },
    
    "solicitudes": {
        "documentation": [
            # -- REGLAS Y HECHOS ESPECÍFICOS PARA SOLICITUDES --
            "FACT: REQUEST_STATE_RECORDS => historial de estados por solicitud; estado actual = registro con mayor fecha (MAX(date)) o ROW_NUMBER() rn=1.",
            "INTENT: SOLICITUDES_POR_TRAMITE_RANGO => contar requests por p.name en rango de fechas.",
            "INTENT: ESTADO_FINAL_POR_TRAMITE => usar SOLO último estado por request (ROW_NUMBER rn=1).",
            "INTENT: ULTIMO_ESTADO_ULTIMA_SOLICITUD => dado un DNI y un trámite, elegir SOLO la última solicitud (LIMIT 1) y devolver el ÚLTIMO estado (rn=1).",
        ],
        "sql_examples": [
            # Puedes agregar aquí ejemplos de Pregunta/SQL específicos de solicitudes
        ]
    },
    
    # -- PUEDES AGREGAR MÁS TÓPICOS AQUÍ --
    # "finanzas": {
    #     "documentation": ["..."],
    #     "sql_examples": [...]
    # }
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