import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit

# Importamos la app de forma diferida o dentro de un fixture para
# asegurar que los mocks de variables de entorno (de conftest.py) se
# apliquen ANTES de que se evalúe ct.settings.clients
@pytest.fixture
def client(mock_env_vars, mock_mongodb_client):
    from ct.main import app
    return TestClient(app)


def test_logs_sin_token_deshabilitado(client, monkeypatch):
    """Sin CHATBOT_ADMIN_TOKEN el endpoint admin /logs falla cerrado (503)."""
    monkeypatch.delenv("CHATBOT_ADMIN_TOKEN", raising=False)
    response = client.get("/logs")
    assert response.status_code == 503


def test_logs_token_incorrecto_403(client, monkeypatch):
    monkeypatch.setenv("CHATBOT_ADMIN_TOKEN", "secreto")
    response = client.get("/logs", params={"token": "malo"})
    assert response.status_code == 403


def test_logs_token_correcto_ok(client, monkeypatch):
    """Con el token correcto y sin msg_id responde el HTML del buscador."""
    monkeypatch.setenv("CHATBOT_ADMIN_TOKEN", "secreto")
    response = client.get("/logs", params={"token": "secreto"})
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_reload_vectorstores_requiere_admin(client, monkeypatch):
    monkeypatch.delenv("CHATBOT_ADMIN_TOKEN", raising=False)
    response = client.post("/internal/reload_vectorstores")
    assert response.status_code == 503


def test_ui_event_meta_grande_se_descarta(client, monkeypatch):
    """Un meta desmesurado no debe romper el endpoint (protección anti disk-fill).

    En modo abierto (sin allowlist) verify_origin no bloquea; el evento se acepta
    (204) y la meta grande se descarta internamente."""
    monkeypatch.delenv("CHATBOT_ALLOWED_ORIGINS", raising=False)
    big_meta = {"blob": "x" * 5000}
    response = client.post("/ui-event", json={"event": "open", "user_id": "u1", "meta": big_meta})
    assert response.status_code == 204
