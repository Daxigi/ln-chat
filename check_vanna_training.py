#!/usr/bin/env python3
"""
Script para verificar el estado del entrenamiento de Vanna y agregar datos básicos si es necesario
"""

import requests
import json
import os
import sys
from dotenv import load_dotenv

# Asegurarnos de que estamos en el directorio correcto
if os.path.exists('backend'):
    os.chdir('backend')

load_dotenv()

API_URL = "http://localhost:8000"
USERNAME = "admin"
PASSWORD = "admin123"

def get_token():
    """Obtener token de autenticación"""
    response = requests.post(
        f"{API_URL}/auth/login",
        data={"username": USERNAME, "password": PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        print("❌ Error en login")
        return None

def check_training_data(token):
    """Verificar datos de entrenamiento actuales"""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{API_URL}/vanna/training-data", headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        print(f"📊 Datos de entrenamiento actuales:")
        
        # El endpoint devuelve una lista, no un diccionario con contadores
        if 'data' in data and isinstance(data['data'], list):
            training_items = data['data']
            print(f"   Total de items: {len(training_items)}")
            
            # Contar por tipo
            ddl_count = sum(1 for item in training_items if item.get('metadata', {}).get('type') == 'ddl')
            doc_count = sum(1 for item in training_items if item.get('metadata', {}).get('type') == 'documentation')
            sql_count = sum(1 for item in training_items if item.get('metadata', {}).get('type') == 'question_sql')
            
            print(f"   DDL: {ddl_count}")
            print(f"   Documentación: {doc_count}")
            print(f"   Ejemplos SQL: {sql_count}")
            
            # Mostrar algunos ejemplos si existen
            if len(training_items) > 0:
                print("\n📝 Algunos items de entrenamiento:")
                for i, item in enumerate(training_items[:3]):
                    metadata = item.get('metadata', {})
                    doc_preview = item.get('document', '')[:100] + '...' if len(item.get('document', '')) > 100 else item.get('document', '')
                    print(f"   {i+1}. Tipo: {metadata.get('type', 'unknown')}")
                    print(f"      Preview: {doc_preview}")
            
            return len(training_items)
        else:
            print("   No hay datos de entrenamiento")
            return 0
    else:
        print(f"❌ Error obteniendo datos: {response.status_code}")
        return 0

def train_basic_ddl(token):
    """Entrenar con DDL básico de las tablas principales"""
    headers = {"Authorization": f"Bearer {token}"}
    
    # DDL de la tabla users (la más importante)
    users_ddl = """
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    nombre VARCHAR(255),
    apellido VARCHAR(255),
    email VARCHAR(255) UNIQUE,
    sexo_id INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    ultima_conexion DATETIME,
    estado INT DEFAULT 1,
    FOREIGN KEY (sexo_id) REFERENCES sexo(id)
);

-- Tabla sexo
CREATE TABLE sexo (
    id INT PRIMARY KEY,
    nombre VARCHAR(50)
);
-- Valores: 1 = Masculino, 2 = Femenino

-- Tabla formularios
CREATE TABLE formularios (
    id INT PRIMARY KEY AUTO_INCREMENT,
    nombre VARCHAR(255),
    descripcion TEXT,
    uso_count INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Tabla tramites
CREATE TABLE tramites (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    formulario_id INT,
    estado VARCHAR(50) DEFAULT 'pendiente',
    fecha_envio DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (formulario_id) REFERENCES formularios(id)
);
"""
    
    print("\n🔧 Entrenando con DDL de tablas principales...")
    response = requests.post(
        f"{API_URL}/vanna/train",
        json={
            "training_type": "ddl",
            "ddl": users_ddl
        },
        headers=headers
    )
    
    if response.status_code == 200:
        print("✅ DDL agregado correctamente")
        return True
    else:
        print(f"❌ Error agregando DDL: {response.text}")
        return False

def train_documentation(token):
    """Entrenar con documentación sobre las tablas"""
    headers = {"Authorization": f"Bearer {token}"}
    
    documentation = """
DOCUMENTACIÓN DE LA BASE DE DATOS:

1. Tabla 'users': Contiene todos los usuarios registrados en el sistema de trámites digitales
   - id: Identificador único del usuario
   - nombre: Nombre del usuario
   - apellido: Apellido del usuario
   - email: Correo electrónico único
   - sexo_id: Género del usuario (1 = Masculino, 2 = Femenino)
   - created_at: Fecha y hora de registro del usuario
   - updated_at: Fecha y hora de última actualización
   - ultima_conexion: Última vez que el usuario inició sesión
   - estado: Estado del usuario (1 = Activo, 0 = Inactivo)

2. Tabla 'sexo': Catálogo de géneros
   - id: 1 = Masculino, 2 = Femenino
   - nombre: Descripción del género

3. Tabla 'formularios': Contiene los formularios/trámites disponibles
   - id: Identificador del formulario
   - nombre: Nombre del formulario/trámite
   - descripcion: Descripción del trámite
   - uso_count: Número de veces que se ha usado el formulario

4. Tabla 'tramites': Registro de trámites enviados
   - id: Identificador del trámite
   - user_id: Usuario que envió el trámite
   - formulario_id: Tipo de formulario/trámite
   - estado: Estado del trámite ('pendiente', 'completado', 'rechazado')
   - fecha_envio: Cuándo se envió el trámite

Notas importantes:
- Para contar usuarios por género, usar sexo_id (1=hombres, 2=mujeres)
- Las fechas están en formato DATETIME
- Los usuarios activos tienen estado = 1
"""
    
    print("\n📚 Entrenando con documentación...")
    response = requests.post(
        f"{API_URL}/vanna/train",
        json={
            "training_type": "documentation",
            "documentation": documentation
        },
        headers=headers
    )
    
    if response.status_code == 200:
        print("✅ Documentación agregada correctamente")
        return True
    else:
        print(f"❌ Error agregando documentación: {response.text}")
        return False

def train_example_queries(token):
    """Entrenar con ejemplos de consultas comunes"""
    headers = {"Authorization": f"Bearer {token}"}
    
    examples = [
        # Consultas básicas de conteo
        {
            "question": "¿Cuántos usuarios están registrados?",
            "sql": "SELECT COUNT(*) as total_usuarios FROM users"
        },
        {
            "question": "¿Cuántos usuarios hay?",
            "sql": "SELECT COUNT(*) as total FROM users"
        },
        {
            "question": "¿Cuántos usuarios existen?",
            "sql": "SELECT COUNT(*) as cantidad FROM users"
        },
        # Consultas por género
        {
            "question": "¿Cuántos usuarios mujeres se registraron en 2024?",
            "sql": "SELECT COUNT(*) as total FROM users WHERE sexo_id = 2 AND YEAR(created_at) = 2024"
        },
        {
            "question": "¿Cuántas mujeres se registraron en 2024?",
            "sql": "SELECT COUNT(*) as total FROM users WHERE sexo_id = 2 AND YEAR(created_at) = 2024"
        },
        {
            "question": "¿Cuántos usuarios hombres se registraron en 2024?",
            "sql": "SELECT COUNT(*) as total FROM users WHERE sexo_id = 1 AND YEAR(created_at) = 2024"
        },
        {
            "question": "¿Cuántas mujeres hay registradas?",
            "sql": "SELECT COUNT(*) as total_mujeres FROM users WHERE sexo_id = 2"
        },
        {
            "question": "¿Cuántos hombres hay?",
            "sql": "SELECT COUNT(*) as total FROM users WHERE sexo_id = 1"
        },
        # Consultas con listados
        {
            "question": "Lista los primeros 10 usuarios",
            "sql": "SELECT id, nombre, apellido, email, created_at FROM users ORDER BY created_at DESC LIMIT 10"
        },
        {
            "question": "Muéstrame los últimos 5 usuarios registrados",
            "sql": "SELECT id, nombre, apellido, email, created_at FROM users ORDER BY created_at DESC LIMIT 5"
        },
        # Consultas por fecha
        {
            "question": "¿Cuántos usuarios se registraron en 2023?",
            "sql": "SELECT COUNT(*) as total FROM users WHERE YEAR(created_at) = 2023"
        },
        {
            "question": "¿Cuántas mujeres se registraron en 2023?",
            "sql": "SELECT COUNT(*) as total FROM users WHERE sexo_id = 2 AND YEAR(created_at) = 2023"
        }
    ]
    
    print("\n💡 Entrenando con ejemplos de consultas...")
    success_count = 0
    for example in examples:
        response = requests.post(
            f"{API_URL}/vanna/train",
            json={
                "training_type": "sql",
                "question": example["question"],
                "sql": example["sql"]
            },
            headers=headers
        )
        
        if response.status_code == 200:
            print(f"✅ Ejemplo agregado: {example['question'][:50]}...")
            success_count += 1
        else:
            print(f"❌ Error agregando ejemplo: {response.text}")
    
    print(f"\n📊 Se agregaron {success_count} de {len(examples)} ejemplos")
    return success_count > 0

def test_query(token, question):
    """Probar una consulta"""
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"\n🧪 Probando: '{question}'")
    response = requests.post(
        f"{API_URL}/mindsdb/chat",
        json={
            "query": question,
            "session_id": "test-session",
            "conversation_history": []
        },
        headers=headers
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            print(f"✅ SQL generado: {data.get('sql')}")
            print(f"📝 Respuesta: {data.get('answer')[:200]}...")
        else:
            print(f"❌ Error: {data.get('answer')}")
    else:
        print(f"❌ Error HTTP: {response.status_code}")

def main():
    print("🔍 Verificando estado del entrenamiento de Vanna\n")
    
    # Verificar si se quiere forzar el re-entrenamiento
    force_retrain = '--force' in sys.argv or '-f' in sys.argv
    
    # 1. Obtener token
    token = get_token()
    if not token:
        print("\n❌ No se pudo obtener token de autenticación")
        print("Verifica que el backend esté ejecutándose en http://localhost:8000")
        return
    
    # 2. Verificar datos actuales
    total_data = check_training_data(token)
    
    # 3. Si no hay datos o se fuerza, entrenar
    if total_data == 0 or force_retrain:
        if force_retrain and total_data > 0:
            print(f"\n⚠️  Forzando re-entrenamiento (había {total_data} items)")
        else:
            print("\n⚠️  No hay datos de entrenamiento. Agregando información básica...")
        
        # Entrenar con DDL, documentación y ejemplos
        ddl_ok = train_basic_ddl(token)
        doc_ok = train_documentation(token)
        examples_ok = train_example_queries(token)
        
        if ddl_ok and doc_ok and examples_ok:
            print("\n✅ Entrenamiento básico completado exitosamente")
        else:
            print("\n⚠️  El entrenamiento se completó con algunos errores")
    else:
        print(f"\n✅ Ya hay {total_data} items de entrenamiento")
        print("💡 Usa --force o -f para forzar el re-entrenamiento")
    
    # 4. Probar algunas consultas
    print("\n" + "="*50)
    print("🧪 PRUEBAS DE CONSULTAS")
    print("="*50)
    
    test_queries = [
        "¿Cuántos usuarios están registrados?",
        "¿Cuántas mujeres se registraron en 2024?",
        "¿Cuántos usuarios existen?"
    ]
    
    for query in test_queries:
        test_query(token, query)
    
    print("\n✅ Verificación completada")
    
    # 5. Mostrar siguiente paso
    print("\n" + "="*50)
    print("🚀 SIGUIENTES PASOS")
    print("="*50)
    
    print("\n1. Si las consultas funcionaron, prueba en la UI:")
    print("   - Abre http://localhost:8501")
    print("   - Login con admin/admin123")
    print("   - Haz las mismas preguntas")
    
    print("\n2. Si NO funcionaron, verifica:")
    print("   - Que ChromaDB esté inicializado correctamente")
    print("   - Que tengas configurada OPENAI_API_KEY en .env")
    print("   - Los logs del backend para ver errores específicos")
    
    print("\n3. Para agregar más entrenamiento:")
    print("   - Modifica este script agregando más ejemplos")
    print("   - O usa la API directamente para entrenar con tus datos")
    
if __name__ == "__main__":
    main()