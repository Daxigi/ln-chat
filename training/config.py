# --- FASE 1: SELECCIÓN DE ESQUEMAS (TABLAS) ---
# El script de entrenamiento buscará el 'CREATE TABLE' solo para estas tablas.
SELECTED_TABLES = [
    "users",
    "requests",
    "procedures",
    # "otra_tabla_importante",
    # "productos",
]


# --- FASE 2: DOCUMENTACIÓN DE NEGOCIO ---
DOCUMENTATION = [
    "La tabla `users` contiene todos los usuarios del sistema. El rol se encuentra en `current_role`.",
    "La tabla `procedures` define los tipos de trámites disponibles en la plataforma. Es una tabla de catálogo.",
    "La tabla `requests` guarda cada solicitud o trámite iniciado por un usuario. Se relaciona con `users` a través de `user_id` y con `procedures` a través de `procedure_id`.",
    "El estado 'completed' en la tabla `requests` significa que el trámite ha finalizado exitosamente.",
    "Los usuarios con `current_role` = 'admin' son administradores con permisos totales."
]


# --- FASE 3: EJEMPLOS DE PREGUNTAS Y SQL ---
SQL_EXAMPLES = [
    {"question": "¿Cuántos usuarios hay en total?", "sql": "SELECT COUNT(*) FROM users;"},
    {"question": "¿Cuántos trámites se han solicitado?", "sql": "SELECT COUNT(*) FROM requests;"},
    {"question": "¿Número de usuarios administradores?", "sql": "SELECT COUNT(*) FROM users WHERE current_role = 'admin';"},

    {"question": "¿Cuáles son los 5 trámites más recientes?", "sql": "SELECT * FROM requests ORDER BY created_at DESC LIMIT 5;"},
    {"question": "Muéstrame los usuarios que no son administradores", "sql": "SELECT id, email, current_role FROM users WHERE current_role != 'admin';"},
    {"question": "Lista los trámites completados", "sql": "SELECT * FROM requests WHERE status = 'completed';"},

    {
        "question": "Muéstrame el nombre del trámite y el email del usuario para las 10 últimas solicitudes",
        "sql": """
            SELECT
                u.email,
                p.name AS procedure_name,
                r.created_at
            FROM requests AS r
            JOIN users AS u ON r.user_id = u.id
            JOIN procedures AS p ON r.procedure_id = p.id
            ORDER BY r.created_at DESC
            LIMIT 10;
        """
    },
    {
        "question": "¿Cuántos trámites ha iniciado el usuario con email 'test@example.com'?",
        "sql": """
            SELECT COUNT(r.id)
            FROM requests AS r
            JOIN users AS u ON r.user_id = u.id
            WHERE u.email = 'test@example.com';
        """
    },
     {
        "question": "dame el nombre y apellido de los usuarios que iniciaron tramites",
        "sql": """
         SELECT u.name, u.lastname FROM users u JOIN requests r ON u.id = r.user_id;

        """
    }
]