#!/usr/bin/env python3
"""
Script de diagnóstico rápido para identificar qué está fallando con Vanna
"""

import os
import sys
import requests
from dotenv import load_dotenv

# Cargar .env desde backend si existe
if os.path.exists('backend/.env'):
    load_dotenv('backend/.env')
else:
    load_dotenv()

def check_environment():
    """Verificar variables de entorno necesarias"""
    print("1️⃣ Verificando variables de entorno...")
    
    required_vars = {
        "OPENAI_API_KEY": "API Key de OpenAI",
        "MYSQL_HOST": "Host de MySQL",
        "MYSQL_USER": "Usuario de MySQL",
        "MYSQL_DATABASE": "Base de datos"
    }
    
    all_good = True
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            if var == "OPENAI_API_KEY":
                # Ocultar la API key
                display_value = f"{value[:7]}...{value[-4:]}" if len(value) > 11 else "***"
            else:
                display_value = value
            print(f"   ✅ {var}: {display_value}")
        else:
            print(f"   ❌ {var}: NO CONFIGURADO ({description})")
            all_good = False
    
    return all_good

def check_backend():
    """Verificar que el backend está funcionando"""
    print("\n2️⃣ Verificando backend...")
    
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Backend funcionando")
            print(f"   ✅ MySQL: {'Conectado' if data.get('mysql_connected') else '❌ Desconectado'}")
            print(f"   ✅ Vanna: {'Conectado' if data.get('vanna_connected') else '❌ Desconectado'}")
            return True
        else:
            print(f"   ❌ Backend respondió con error: {response.status_code}")
            return False
    except requests.ConnectionError:
        print("   ❌ No se puede conectar al backend")
        print("   💡 Ejecuta: cd backend && uvicorn main:app --reload")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def check_chromadb():
    """Verificar ChromaDB"""
    print("\n3️⃣ Verificando ChromaDB...")
    
    # Buscar posibles ubicaciones
    possible_paths = [
        os.path.expanduser("~/.vanna_chromadb"),
        "./chroma_db",
        "./backend/chroma_db",
    ]
    
    env_path = os.getenv("VANNA_VECTOR_DB_PATH")
    if env_path:
        possible_paths.insert(0, os.path.expanduser(env_path))
    
    found = False
    for path in possible_paths:
        if os.path.exists(path):
            found = True
            # Calcular tamaño
            size = sum(os.path.getsize(os.path.join(dirpath, filename)) 
                      for dirpath, dirnames, filenames in os.walk(path) 
                      for filename in filenames)
            size_mb = size / (1024 * 1024)
            print(f"   ✅ ChromaDB encontrado en: {path}")
            print(f"      Tamaño: {size_mb:.2f} MB")
            
            # Verificar si tiene archivos
            file_count = sum(len(files) for _, _, files in os.walk(path))
            if file_count < 5:
                print(f"   ⚠️  Pocos archivos ({file_count}), puede estar vacío")
            break
    
    if not found:
        print("   ⚠️  ChromaDB no encontrado (se creará al primer uso)")
    
    return True

def check_vanna_training():
    """Verificar datos de entrenamiento"""
    print("\n4️⃣ Verificando entrenamiento de Vanna...")
    
    try:
        # Login
        response = requests.post(
            "http://localhost:8000/auth/login",
            data={"username": "admin", "password": "admin123"},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if response.status_code != 200:
            print("   ❌ No se pudo autenticar")
            return False
        
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Verificar datos de entrenamiento
        response = requests.get("http://localhost:8000/vanna/training-data", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and isinstance(data['data'], list):
                count = len(data['data'])
                if count == 0:
                    print("   ❌ No hay datos de entrenamiento")
                    print("   💡 Ejecuta: python check_vanna_training.py")
                    return False
                else:
                    print(f"   ✅ {count} items de entrenamiento encontrados")
                    # Contar por tipo
                    types = {}
                    for item in data['data']:
                        t = item.get('metadata', {}).get('type', 'unknown')
                        types[t] = types.get(t, 0) + 1
                    
                    for t, c in types.items():
                        print(f"      - {t}: {c}")
                    return True
        
        print("   ❌ Error verificando entrenamiento")
        return False
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def test_simple_query():
    """Probar una consulta simple"""
    print("\n5️⃣ Probando consulta simple...")
    
    try:
        # Login
        response = requests.post(
            "http://localhost:8000/auth/login",
            data={"username": "admin", "password": "admin123"},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Probar consulta
        response = requests.post(
            "http://localhost:8000/mindsdb/chat",
            json={
                "query": "¿Cuántos usuarios hay?",
                "session_id": "test",
                "conversation_history": []
            },
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print(f"   ✅ Consulta exitosa")
                print(f"      SQL: {data.get('sql', 'N/A')}")
                answer = data.get('answer', '')[:100]
                print(f"      Respuesta: {answer}...")
                return True
            else:
                print(f"   ❌ Consulta falló: {data.get('answer', 'Error desconocido')}")
                return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def main():
    print("🔍 Diagnóstico de Vanna")
    print("="*50)
    
    results = {
        "environment": check_environment(),
        "backend": check_backend(),
        "chromadb": check_chromadb(),
    }
    
    # Solo verificar training y query si el backend está funcionando
    if results["backend"]:
        results["training"] = check_vanna_training()
        results["query"] = test_simple_query()
    else:
        results["training"] = False
        results["query"] = False
    
    # Resumen
    print("\n" + "="*50)
    print("📊 RESUMEN")
    print("="*50)
    
    all_good = all(results.values())
    
    if all_good:
        print("\n✅ ¡Todo está funcionando correctamente!")
    else:
        print("\n❌ Se encontraron problemas:")
        
        if not results["environment"]:
            print("\n1. Configurar variables de entorno faltantes en backend/.env")
        
        if not results["backend"]:
            print("\n2. Iniciar el backend:")
            print("   cd backend && uvicorn main:app --reload")
        
        if results["backend"] and not results["training"]:
            print("\n3. Entrenar Vanna:")
            print("   python check_vanna_training.py")
        
        if results["training"] and not results["query"]:
            print("\n4. Posible problema con OpenAI o ChromaDB")
            print("   - Verifica tu API key de OpenAI")
            print("   - Intenta resetear ChromaDB: python reset_chromadb.py")
    
    print("\n💡 Para más detalles, revisa los logs del backend")

if __name__ == "__main__":
    main()