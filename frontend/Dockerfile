# 1. Imagen base
FROM python:3.11-slim

# 2. Directorio de trabajo principal
WORKDIR /app

# 3. Instalar dependencias
COPY ./frontend/requirements.txt /app/
RUN pip install -r requirements.txt

# 4. Copiar el código del frontend
COPY ./frontend /app/frontend

# --- CAMBIO IMPORTANTE AQUÍ ---
# 5. Entra al directorio donde está tu app.py
WORKDIR /app/frontend

# 6. Expone el puerto de Streamlit
EXPOSE 8501

# 7. Ejecuta la aplicación
CMD ["streamlit", "run", "app.py"]