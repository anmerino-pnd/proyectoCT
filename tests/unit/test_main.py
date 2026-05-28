import pytest
from fastapi.testclient import TestClient

# Importamos la app de forma diferida o dentro de un fixture para 
# asegurar que los mocks de variables de entorno (de conftest.py) se 
# apliquen ANTES de que se evalúe ct.settings.clients
@pytest.fixture
def client(mock_env_vars, mock_mongodb_client):
    from ct.main import app
    return TestClient(app)

def test_logs_endpoint_no_id(client):
    """
    Prueba básica para asegurar que el endpoint /logs
    responde correctamente (código 200) cuando no se le
    pasa un ID.
    """
    response = client.get("/logs")
    assert response.status_code == 200
    # Verificamos que la respuesta sea HTML (por el Jinja2Templates)
    assert "text/html" in response.headers["content-type"]
