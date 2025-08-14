# 1. Usa una imagen base de Python
FROM python:3.12-slim

# 2. Establece el directorio de trabajo dentro del contenedor
WORKDIR /app

# 3. Instala Poetry en el sistema
RUN pip install poetry

# 4. Copia solo los archivos de configuración de dependencias
COPY pyproject.toml poetry.lock* /app/

# 5. Instala las dependencias del proyecto usando Poetry
RUN poetry config virtualenvs.create false && poetry install --no-root --no-interaction --no-ansi

# 6. Copia el resto del código de tu aplicación
COPY ./backend /app/backend
COPY ./frontend /app/frontend

# --- CAMBIO 1: Entra al directorio de tu aplicación ---
WORKDIR /app/backend

# 7. Expone el puerto que tu API usa
EXPOSE 8000

# --- CAMBIO 2: Simplifica el comando de inicio ---
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]