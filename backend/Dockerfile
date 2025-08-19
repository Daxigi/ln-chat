# 1. Imagen base (asegúrate que coincida con tu pyproject.toml)
FROM python:3.12-slim

# 2. Instala herramientas de compilación
RUN apt-get update && apt-get install -y build-essential

# 3. Directorio de trabajo principal
WORKDIR /app

# 4. Instala Poetry
RUN pip install poetry

# 5. Copia archivos de dependencias
COPY pyproject.toml poetry.lock* /app/

# 6. Instala dependencias
RUN poetry config virtualenvs.create false && poetry install --no-root

# 7. Copia tu código
COPY ./backend /app/backend

# 8. CAMBIO IMPORTANTE: Establece el directorio de trabajo final
WORKDIR /app/backend

# 9. Expone el puerto
EXPOSE 8000

# 10. CAMBIO IMPORTANTE: Comando de inicio simplificado
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]