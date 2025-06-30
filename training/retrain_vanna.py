# training/retrain_vanna.py
import os
import sys
from dotenv import load_dotenv
import shutil

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))
load_dotenv()

print("=== RE-ENTRENAMIENTO COMPLETO DE VANNA ===\n")

response = input("⚠️  Esto borrará todo el entrenamiento actual. ¿Continuar? (s/n): ")
if response.lower() != 's':
    print("Cancelado")
    exit(0)

# Importar después de confirmar
from vanna_service import VannaService
import vanna as vn

print("\n📦 Re-inicializando Vanna...")
service = VannaService()

if not service.connected:
    print("❌ Error al inicializar VannaService. Revisa los logs.")
    exit(1)

print("✅ Vanna reinicializada\n")

# 3. Entrenar esquema
print("📊 Entrenando con esquema de base de datos...")
try:
    tables_df = vn.run_sql("SHOW TABLES")
    column_name = tables_df.columns[0]
    
    for table_name in tables_df[column_name]:
        print(f"  - Tabla: {table_name}")
        ddl_result = vn.run_sql(f"SHOW CREATE TABLE {table_name}")
        if ddl_result is not None and not ddl_result.empty:
            ddl = ddl_result.iloc[0, 1]
            service.train(ddl=ddl)
    
    print("✅ Esquema entrenado\n")
except Exception as e:
    print(f"❌ Error entrenando esquema: {e}")
    
# 4. Entrenar documentación
print("📚 Entrenando documentación...")
docs = [
    "Cuando pidan 'el primer usuario', usar ORDER BY id LIMIT 1",
    "Cuando pidan 'mostrar usuarios', usar SELECT * FROM users",
    "Las tablas principales son: users, forms, submissions, form_fields, submission_values",
    "Los estados posibles de submissions son: PENDING, IN_PROGRESS, APPROVED, REJECTED, CANCELLED",
    "Los roles de usuario son: admin y user"
]

for doc in docs:
    service.train(documentation=doc)
print("✅ Documentación entrenada\n")

# 5. Entrenar ejemplos SQL
print("🎯 Entrenando ejemplos SQL...")
examples = [
    ("¿Cuántos usuarios hay?", "SELECT COUNT(*) as total FROM users"),
    ("Mostrar todos los usuarios", "SELECT * FROM users"),
    ("¿Cuántos formularios activos hay?", "SELECT COUNT(*) as total FROM forms WHERE is_active = 1"),
    ("¿Cuáles son los últimos 5 trámites?", """
        SELECT s.id, u.name as usuario, f.name as formulario, s.status, s.created_at 
        FROM submissions s 
        JOIN users u ON s.user_id = u.id 
        JOIN forms f ON s.form_id = f.id 
        ORDER BY s.created_at DESC 
        LIMIT 5
    """),
    ("Usuarios administradores", "SELECT * FROM users WHERE role = 'admin'"),
    ("¿Cuántos trámites están pendientes?", "SELECT COUNT(*) as total FROM submissions WHERE status = 'PENDING'")
]

trained = 0
for question, sql in examples:
    if service.train(question=question, sql=sql):
        trained += 1
        print(f"✅ {question}")
    else:
        print(f"❌ Error: {question}")
        
print(f"\n✅ Entrenados {trained} de {len(examples)} ejemplos\n")

# 6. Verificación final
print("🧪 Verificando entrenamiento...")
test_question = "¿Cuántos usuarios hay en total?"
result = service.ask(test_question)

if result["success"]:
    print(f"✅ Pregunta: {test_question}")
    print(f"✅ SQL generado: {result['sql']}")
    print(f"✅ Resultado: {result['result']}")
    print("\n🎉 ¡Entrenamiento completado exitosamente!")
else:
    print(f"❌ Error en verificación: {result.get('error', 'Unknown error')}")
    print("⚠️  El entrenamiento se completó pero la verificación falló")