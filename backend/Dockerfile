# 1. Usa una imagen base de Python
FROM python:3.11-slim

# 2. Establece el directorio de trabajo dentro del contenedor
WORKDIR /app

# 3. Instala Poetry en el sistema
RUN pip install poetry

# 4. Copia solo los archivos de configuración de dependencias
# Usamos un * al final de poetry.lock para que no falle si el archivo no existe al principio
COPY pyproject.toml poetry.lock* /app/

# 5. Instala las dependencias del proyecto usando Poetry
#    - virtualenvs.create false: Instala los paquetes en el entorno principal del contenedor, no en un .venv
#    - --no-root: No instala el proyecto en sí, solo sus dependencias
RUN poetry config virtualenvs.create false && poetry install --no-root --no-interaction --no-ansi

# 6. Copia el resto del código de tu aplicación
COPY ./backend /app/backend
COPY ./frontend /app/frontend

# 7. Expone el puerto que tu API usa
EXPOSE 8000

# 8. El comando para correr la aplicación al iniciar el contenedor
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]