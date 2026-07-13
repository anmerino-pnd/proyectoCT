"""Tests del endurecimiento de seguridad (ct.settings.security).

Cubre CORS fail-safe, verificación de Origin/Referer, la guarda admin y el
rate-limit por ventana deslizante. Son unitarios: construyen un Request falso
mínimo, sin levantar la app ni tocar red.
"""
import pytest
from fastapi import HTTPException

from ct.settings import security

pytestmark = pytest.mark.unit


class FakeRequest:
    """Stub mínimo de starlette.Request para las dependencias de seguridad."""

    def __init__(self, headers=None, query_params=None, method="POST",
                 client_host="1.2.3.4", body=None):
        self.headers = headers or {}
        self.query_params = query_params or {}
        self.method = method
        self.client = type("Client", (), {"host": client_host})()
        self._body = body

    async def json(self):
        if self._body is None:
            raise ValueError("sin cuerpo JSON")
        return self._body


@pytest.fixture(autouse=True)
def _clean_env_and_state(monkeypatch):
    """Cada test parte de un estado limpio de env y del buffer de rate-limit."""
    for var in ("CHATBOT_ALLOWED_ORIGINS", "CHATBOT_OPEN_CORS", "CHATBOT_ADMIN_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    security._hits.clear()
    security._last_prune = 0.0
    yield
    security._hits.clear()


# --------------------------- cors_origins --------------------------- #

def test_cors_sin_allowlist_falla_cerrado():
    assert security.cors_origins() == []


def test_cors_open_flag_abre_wildcard(monkeypatch):
    monkeypatch.setenv("CHATBOT_OPEN_CORS", "1")
    assert security.cors_origins() == ["*"]


def test_cors_con_allowlist(monkeypatch):
    monkeypatch.setenv("CHATBOT_ALLOWED_ORIGINS", "https://a.com, https://b.com/")
    assert security.cors_origins() == ["https://a.com", "https://b.com"]


# --------------------------- verify_origin --------------------------- #

async def test_verify_origin_sin_allowlist_permite():
    # Modo pre-dominio: sin allowlist no se verifica nada.
    await security.verify_origin(FakeRequest(headers={}))


async def test_verify_origin_match_ok(monkeypatch):
    monkeypatch.setenv("CHATBOT_ALLOWED_ORIGINS", "https://ok.com")
    await security.verify_origin(FakeRequest(headers={"origin": "https://ok.com"}))


async def test_verify_origin_no_permitido(monkeypatch):
    monkeypatch.setenv("CHATBOT_ALLOWED_ORIGINS", "https://ok.com")
    with pytest.raises(HTTPException) as exc:
        await security.verify_origin(FakeRequest(headers={"origin": "https://evil.com"}))
    assert exc.value.status_code == 403


async def test_verify_origin_referer_fallback(monkeypatch):
    monkeypatch.setenv("CHATBOT_ALLOWED_ORIGINS", "https://ok.com")
    await security.verify_origin(FakeRequest(headers={"referer": "https://ok.com/página"}))


async def test_verify_origin_sin_cabeceras_rechaza(monkeypatch):
    # Cierre del bypass server-to-server: con allowlist activa y sin Origin/Referer.
    monkeypatch.setenv("CHATBOT_ALLOWED_ORIGINS", "https://ok.com")
    with pytest.raises(HTTPException) as exc:
        await security.verify_origin(FakeRequest(headers={}))
    assert exc.value.status_code == 403


# --------------------------- verify_admin --------------------------- #

async def test_verify_admin_sin_token_configurado_503():
    with pytest.raises(HTTPException) as exc:
        await security.verify_admin(FakeRequest(headers={}))
    assert exc.value.status_code == 503


async def test_verify_admin_token_incorrecto_403(monkeypatch):
    monkeypatch.setenv("CHATBOT_ADMIN_TOKEN", "secreto")
    with pytest.raises(HTTPException) as exc:
        await security.verify_admin(FakeRequest(headers={"x-admin-token": "malo"}))
    assert exc.value.status_code == 403


async def test_verify_admin_header_ok(monkeypatch):
    monkeypatch.setenv("CHATBOT_ADMIN_TOKEN", "secreto")
    await security.verify_admin(FakeRequest(headers={"x-admin-token": "secreto"}))


async def test_verify_admin_query_ok(monkeypatch):
    monkeypatch.setenv("CHATBOT_ADMIN_TOKEN", "secreto")
    await security.verify_admin(FakeRequest(headers={}, query_params={"token": "secreto"}))


# --------------------------- rate limit --------------------------- #

async def test_rate_limit_bloquea_tras_tope():
    req = FakeRequest(method="POST", body={"user_id": "u1"})
    # Dos permitidas, la tercera excede el tope.
    await security._enforce_rate(req, max_hits=2, bucket_prefix="test")
    await security._enforce_rate(req, max_hits=2, bucket_prefix="test")
    with pytest.raises(HTTPException) as exc:
        await security._enforce_rate(req, max_hits=2, bucket_prefix="test")
    assert exc.value.status_code == 429


async def test_rate_limit_buckets_por_usuario_independientes():
    r1 = FakeRequest(method="POST", body={"user_id": "u1"})
    r2 = FakeRequest(method="POST", body={"user_id": "u2"})
    await security._enforce_rate(r1, max_hits=1, bucket_prefix="test")
    # u2 no debe verse afectado por el consumo de u1.
    await security._enforce_rate(r2, max_hits=1, bucket_prefix="test")
    with pytest.raises(HTTPException):
        await security._enforce_rate(r1, max_hits=1, bucket_prefix="test")


async def test_rate_limit_get_sin_cuerpo_no_falla():
    # GET/DELETE no leen cuerpo; se limita por IP sin lanzar por falta de JSON.
    req = FakeRequest(method="GET")
    await security._enforce_rate(req, max_hits=5, bucket_prefix="light")
