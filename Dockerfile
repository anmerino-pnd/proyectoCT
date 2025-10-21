# Usamos Python 3.13 (ajusta si usas otra versión)
FROM python:3.13-slim

WORKDIR /app

# Copia archivos de dependencias (incluyendo lockfile si existe)
COPY pyproject.toml uv.lock* ./

# Instala uv
RUN pip install --no-cache-dir uv

# Sync de dependencias (usa el lockfile)
RUN uv sync 

# Copia el código
COPY . .

EXPOSE 8000

CMD ["uv", "run", "gunicorn", "ct.main:app", \
     "--workers", "4", \
     "--bind", "0.0.0.0:8000", \
     "--certfile", "static/ssl/cert.pem", \
     "--keyfile", "static/ssl/key.pem", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]