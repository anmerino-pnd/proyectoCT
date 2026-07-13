"""Endurecimiento ligero para exponer el servidor directo a internet.

Todo es opt-in por variables de entorno, de modo que en desarrollo / antes de tener
el dominio el comportamiento es el de hoy (abierto). La restricción se activa sola
cuando se define `CHATBOT_ALLOWED_ORIGINS` en el cutover del dominio.

Variables:
- CHATBOT_ALLOWED_ORIGINS : orígenes permitidos, separados por coma
                            (p.ej. "https://www.ctonline.mx,https://ctdev.ctonline.mx").
                            Vacío => se aplica el modo por defecto (ver CHATBOT_OPEN_CORS).
- CHATBOT_OPEN_CORS       : "1" para permitir CORS abierto ('*') cuando NO hay allowlist
                            (solo desarrollo). Sin este flag y sin allowlist, CORS falla
                            cerrado (no se permite ningún origen cruzado).
- CHATBOT_ADMIN_TOKEN     : token para endpoints administrativos (/logs, /internal). Sin
                            él, esos endpoints quedan deshabilitados (fallan cerrado).
- CHATBOT_RATE_MAX        : nº máx. de peticiones a /chat por ventana (default 20).
- CHATBOT_RATE_WINDOW     : tamaño de la ventana en segundos (default 60).

Nota: el rate limiting es en memoria por proceso. Con gunicorn multi-worker el límite
es por worker; para un límite global compartido habría que respaldarlo en Redis
(ya disponible vía PODMAN_REDIS_URL) en una iteración posterior.
"""
import os
import time
import secrets
from collections import defaultdict, deque

from fastapi import HTTPException, Request


def get_allowed_origins() -> list[str]:
    raw = os.getenv("CHATBOT_ALLOWED_ORIGINS", "").strip()
    if not raw:
        return []
    return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]


def cors_origins() -> list[str]:
    """Lista para el CORSMiddleware.

    - Con allowlist configurada => esa lista.
    - Sin allowlist y CHATBOT_OPEN_CORS=1 => '*' (modo desarrollo explícito).
    - Sin allowlist ni flag => [] (falla cerrado: ningún origen cruzado permitido).
    """
    allowed = get_allowed_origins()
    if allowed:
        return allowed
    if os.getenv("CHATBOT_OPEN_CORS", "").strip() == "1":
        return ["*"]
    return []


async def verify_origin(request: Request) -> None:
    """Rechaza orígenes no permitidos (defensa principal al ser endpoint público).

    Si no hay allowlist configurada, no aplica (modo pre-dominio / desarrollo).
    Con allowlist activa, el origen debe coincidir. Las peticiones sin cabecera
    Origin NI Referer se RECHAZAN cuando la allowlist está activa: así se cierra el
    bypass server-to-server (curl) que de otro modo saltaba la lista. El widget de
    navegador siempre envía Origin (fetch cruzado) o al menos Referer.
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
    if referer is not None:
        if not any(referer.startswith(o) for o in allowed):
            raise HTTPException(status_code=403, detail="Origen no permitido.")
        return

    # Ni Origin ni Referer con allowlist activa: petición no originada en navegador.
    raise HTTPException(status_code=403, detail="Origen no permitido.")


def _admin_token() -> str:
    return os.getenv("CHATBOT_ADMIN_TOKEN", "").strip()


async def verify_admin(request: Request) -> None:
    """Protege endpoints administrativos (/logs, /internal/reload_vectorstores).

    El token se acepta en la cabecera `X-Admin-Token` o en el query param `token`
    (práctico para abrir /logs en el navegador). Sin `CHATBOT_ADMIN_TOKEN`
    configurado, el endpoint queda deshabilitado (falla cerrado con 503).
    """
    expected = _admin_token()
    if not expected:
        raise HTTPException(status_code=503, detail="Endpoint administrativo no configurado.")
    provided = request.headers.get("x-admin-token") or request.query_params.get("token") or ""
    if not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=403, detail="No autorizado.")


import logging

logger = logging.getLogger(__name__)

_RATE_MAX = int(os.getenv("CHATBOT_RATE_MAX", "20"))
_RATE_WINDOW = int(os.getenv("CHATBOT_RATE_WINDOW", "60"))
# Límite holgado para endpoints ligeros (/ui-event, /history): protege contra abuso
# sin estorbar el uso normal del widget (varios usuarios pueden compartir IP tras NAT).
_RATE_MAX_LIGHT = int(os.getenv("CHATBOT_RATE_MAX_LIGHT", "120"))
_hits: dict[str, deque] = defaultdict(deque)
_last_prune: float = 0.0


def _prune(now: float) -> None:
    """Sweep amortizado: descarta buckets vencidos para que `_hits` no crezca sin
    límite (las llaves IP:user nunca se borraban). Corre ~1 vez por ventana."""
    global _last_prune
    if now - _last_prune < _RATE_WINDOW:
        return
    _last_prune = now
    for k in list(_hits.keys()):
        bucket = _hits[k]
        while bucket and now - bucket[0] > _RATE_WINDOW:
            bucket.popleft()
        if not bucket:
            del _hits[k]


def _client_ip(request: Request) -> str:
    # Detrás de Cloudflare la IP real llega en CF-Connecting-IP / X-Forwarded-For.
    for header in ("cf-connecting-ip", "x-forwarded-for"):
        value = request.headers.get(header)
        if value:
            return value.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _enforce_rate(request: Request, max_hits: int, bucket_prefix: str) -> None:
    """Ventana deslizante en memoria por (IP + user_id). Comparte `_hits` con un
    prefijo por endpoint para que los límites de /chat y los ligeros no se mezclen."""
    ip = _client_ip(request)
    user_id = ""
    if request.method not in ("GET", "HEAD", "DELETE"):
        try:
            body = await request.json()  # Starlette cachea el body; el endpoint lo reusa
            user_id = str(body.get("user_id", ""))
        except Exception:
            # Cuerpo ausente o no-JSON: se limita solo por IP. Es esperable en GET/DELETE.
            logger.debug("rate_limit: sin user_id en el cuerpo; se limita por IP")

    key = f"{bucket_prefix}:{ip}:{user_id}"
    now = time.monotonic()
    _prune(now)
    bucket = _hits[key]
    while bucket and now - bucket[0] > _RATE_WINDOW:
        bucket.popleft()
    if len(bucket) >= max_hits:
        raise HTTPException(status_code=429, detail="Demasiadas solicitudes. Espera un momento.")
    bucket.append(now)


async def rate_limit(request: Request) -> None:
    """Limita /chat por (IP + user_id) con ventana deslizante en memoria."""
    await _enforce_rate(request, _RATE_MAX, "chat")


async def rate_limit_light(request: Request) -> None:
    """Límite holgado para endpoints ligeros (/ui-event, /history)."""
    await _enforce_rate(request, _RATE_MAX_LIGHT, "light")
