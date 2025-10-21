# Usamos Python 3.13 (ajusta si usas otra versión)
FROM python:3.13-slim

# Establece el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copia los archivos de dependencias
COPY pyproject.toml ./

# Instala uv para manejar dependencias
RUN pip install --no-cache-dir uv

# Instala las dependencias del proyecto
RUN uv pip install --system --no-cache -r pyproject.toml

# Copia todo el código de tu proyecto
COPY . .

# Puerto que expondrá tu aplicación
EXPOSE 8000

# Comando para iniciar gunicorn
CMD ["gunicorn", "ct.main:app", \
     "--workers", "4", \
     "--bind", "0.0.0.0:8000", \
     "--certfile", "static/ssl/cert.pem", \
     "--keyfile", "static/ssl/key.pem", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
