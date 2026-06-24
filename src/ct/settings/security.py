"""Endurecimiento ligero para exponer el servidor directo a internet.

Todo es opt-in por variables de entorno, de modo que en desarrollo / antes de tener
el dominio el comportamiento es el de hoy (abierto). La restricción se activa sola
cuando se define `CHATBOT_ALLOWED_ORIGINS` en el cutover del dominio.

Variables:
- CHATBOT_ALLOWED_ORIGINS : orígenes permitidos, separados por coma
                            (p.ej. "https://www.ctonline.mx,https://ctdev.ctonline.mx").
                            Vacío => modo abierto, sin verificación de origen.
- CHATBOT_RATE_MAX        : nº máx. de peticiones a /chat por ventana (default 20).
- CHATBOT_RATE_WINDOW     : tamaño de la ventana en segundos (default 60).

Nota: el rate limiting es en memoria por proceso. Con gunicorn multi-worker el límite
es por worker; para un límite global compartido habría que respaldarlo en Redis
(ya disponible vía PODMAN_REDIS_URL) en una iteración posterior.
"""
import os
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


def get_allowed_origins() -> list[str]:
    raw = os.getenv("CHATBOT_ALLOWED_ORIGINS", "").strip()
    if not raw:
        return []
    return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]


def cors_origins() -> list[str]:
    """Lista para el CORSMiddleware. Sin allowlist configurada => '*' (como hoy)."""
    allowed = get_allowed_origins()
    return allowed if allowed else ["*"]


async def verify_origin(request: Request) -> None:
    """Rechaza orígenes no permitidos (defensa principal al ser endpoint público).

    Si no hay allowlist configurada, no aplica (modo pre-dominio). Las peticiones
    sin cabecera Origin (curl, server-to-server) se permiten: un ataque CSRF desde
    el navegador siempre envía Origin.
    """
    allowed = get_allowed_origins()
    if not allowed:
        return

    origin = request.headers.get("origin")
    if origin is not None:
        if origin.rstrip("/") not in allowed:
            raise HTTPException(status_code=403, detail="Origen no permitido.")
        return

    referer = request.headers.get("referer")
    if referer is not None and not any(referer.startswith(o) for o in allowed):
        raise HTTPException(status_code=403, detail="Origen no permitido.")


_RATE_MAX = int(os.getenv("CHATBOT_RATE_MAX", "20"))
_RATE_WINDOW = int(os.getenv("CHATBOT_RATE_WINDOW", "60"))
_hits: dict[str, deque] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    # Detrás de Cloudflare la IP real llega en CF-Connecting-IP / X-Forwarded-For.
    for header in ("cf-connecting-ip", "x-forwarded-for"):
        value = request.headers.get(header)
        if value:
            return value.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def rate_limit(request: Request) -> None:
    """Limita /chat por (IP + user_id) con ventana deslizante en memoria."""
    ip = _client_ip(request)
    user_id = ""
    try:
        body = await request.json()  # Starlette cachea el body; el endpoint lo reusa
        user_id = str(body.get("user_id", ""))
    except Exception:
        pass

    key = f"{ip}:{user_id}"
    now = time.monotonic()
    bucket = _hits[key]
    while bucket and now - bucket[0] > _RATE_WINDOW:
        bucket.popleft()
    if len(bucket) >= _RATE_MAX:
        raise HTTPException(status_code=429, detail="Demasiadas solicitudes. Espera un momento.")
    bucket.append(now)
