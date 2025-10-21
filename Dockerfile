# Usa Python 3.13 slim (puedes bajar a 3.12 si Torch da problemas)
FROM python:3.13-slim

WORKDIR /app

# Copiamos el pyproject y lock antes del código (para aprovechar la cache)
COPY pyproject.toml uv.lock* ./

# Instalamos uv (gestor de dependencias ultrarrápido)
RUN pip install --no-cache-dir uv

# Copiamos el código fuente
COPY src ./src
COPY static ./static
COPY datos ./datos

# Instalamos dependencias (usa el lockfile si existe)
RUN uv sync --frozen || uv sync

# Exponemos el puerto 8000
EXPOSE 8000

# Comando de ejecución
CMD ["uv", "run", "gunicorn", "ct.main:app", \
     "--workers", "4", \
     "--bind", "0.0.0.0:8000", \
     "--certfile", "static/ssl/cert.pem", \
     "--keyfile", "static/ssl/key.pem", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
