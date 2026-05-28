"""
Configuration and fixtures for pytest.

This module provides shared fixtures for all tests including:
- Mock database connections
- Sample data fixtures
- Mock external service clients
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ============================================
# Path Fixtures
# ============================================


@pytest.fixture
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent.resolve()


@pytest.fixture
def data_dir(project_root: Path) -> Path:
    """Return the data directory."""
    return project_root / "datos"


# ============================================
# Sample Data Fixtures
# ============================================


@pytest.fixture
def sample_product():
    """Return a sample product for testing."""
    return {
        "objectID": "TEST-001",
        "marca": "Test Brand",
        "modelo": "Test Model X1",
        "descripcion": "A test product for unit testing",
        "ficha_tecnica": "Specifications: CPU i7, RAM 16GB",
        "precio": 1000.0,
        "existencias": 50,
        "moneda": "MXN",
        "promocion": False,
        "url": "https://example.com/product/test-001",
    }


@pytest.fixture
def sample_products():
    """Return a list of sample products."""
    return [
        {
            "objectID": "PROD-001",
            "marca": "HP",
            "modelo": "ProBook 450 G8",
            "descripcion": "Laptop empresarial HP",
            "ficha_tecnica": "Intel Core i5, 8GB RAM, 256GB SSD",
            "precio": 15000.0,
            "existencias": 10,
            "moneda": "MXN",
            "promocion": True,
            "url": "https://ct.com/product/hp-probook-450",
        },
        {
            "objectID": "PROD-002",
            "marca": "Dell",
            "modelo": "Latitude 5420",
            "descripcion": "Laptop Dell para negocios",
            "ficha_tecnica": "Intel Core i7, 16GB RAM, 512GB SSD",
            "precio": 18000.0,
            "existencias": 5,
            "moneda": "MXN",
            "promocion": False,
            "url": "https://ct.com/product/dell-latitude-5420",
        },
        {
            "objectID": "PROD-003",
            "marca": "Lenovo",
            "modelo": "ThinkPad T14",
            "descripcion": "Laptop Lenovo premium",
            "ficha_tecnica": "AMD Ryzen 7, 16GB RAM, 1TB SSD",
            "precio": 22000.0,
            "existencias": 0,
            "moneda": "MXN",
            "promocion": False,
            "url": "https://ct.com/product/lenovo-thinkpad-t14",
        },
    ]


@pytest.fixture
def sample_order():
    """Return a sample order for testing."""
    return {
        "folio": "F-2024-001",
        "factura": "FAC-12345",
        "estatus": "Enviado",
        "fecha": "2024-01-15",
        "total": 25000.0,
        "productos": [
            {"sku": "PROD-001", "cantidad": 1, "precio": 15000.0},
            {"sku": "PROD-002", "cantidad": 1, "precio": 10000.0},
        ],
    }


@pytest.fixture
def sample_sales_rules():
    """Return sample sales rules/promotions."""
    return [
        {
            "id_promocion": "PROMO-001",
            "nombre": "Descuento HP",
            "marca": "HP",
            "descuento_porcentaje": 10,
            "descuento_monto": None,
            "fecha_inicio": "2024-01-01",
            "fecha_fin": "2024-12-31",
            "compra_minima": 10000.0,
            "regalo": None,
        },
        {
            "id_promocion": "PROMO-002",
            "nombre": "Compra 2 lleva 3",
            "marca": None,
            "descuento_porcentaje": None,
            "descuento_monto": None,
            "fecha_inicio": "2024-01-01",
            "fecha_fin": "2024-06-30",
            "compra_minima": 5000.0,
            "regalo": {"tipo": "producto_extra", "cantidad": 1},
        },
    ]


@pytest.fixture
def sample_sucursal():
    """Return a sample branch office."""
    return {
        "sucursal": "Matriz",
        "ubicacion": "Guadalajara",
        "direccion": "Av. Principal 123, Col. Centro",
        "telefono": "33-1234-5678",
        "horario": "Lunes a Viernes 9:00-18:00",
        "puesto": "Gerente de Ventas",
        "nombre": "Juan Perez",
        "correo": "juan.perez@ct.com",
    }


# ============================================
# Mock Fixtures
# ============================================


@pytest.fixture
def mock_mongodb_client(mocker):
    """Return a mocked MongoDB client."""
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_client.__getitem__ = MagicMock(return_value=mock_db)
    mock_client.get_database = MagicMock(return_value=mock_db)
    
    with patch("pymongo.MongoClient", return_value=mock_client):
        yield mock_client


@pytest.fixture
def mock_mongodb_collection(mocker, mock_mongodb_client):
    """Return a mocked MongoDB collection."""
    mock_collection = MagicMock()
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_db.get_collection = MagicMock(return_value=mock_collection)
    mock_mongodb_client.__getitem__ = MagicMock(return_value=mock_db)
    mock_mongodb_client.get_database = MagicMock(return_value=mock_db)
    
    yield mock_collection


@pytest.fixture
def mock_mysql_connection(mocker):
    """Return a mocked MySQL connection."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    
    with patch("mysql.connector.connect", return_value=mock_conn):
        yield mock_conn, mock_cursor


@pytest.fixture
def mock_algolia_client(mocker):
    """Return a mocked Algolia search client."""
    mock_client = MagicMock()
    mock_index = MagicMock()
    mock_client.init_index.return_value = mock_index
    
    with patch("algoliasearch.search_client.SearchClient.create", return_value=mock_client):
        yield mock_client, mock_index


@pytest.fixture
def mock_openai(mocker):
    """Return mocked OpenAI client."""
    mock_client = MagicMock()
    mock_chat = MagicMock()
    mock_completions = MagicMock()
    
    mock_client.chat.completions.create = mock_chat
    
    with patch("openai.OpenAI", return_value=mock_client):
        yield mock_client


# ============================================
# Environment Fixtures
# ============================================


@pytest.fixture
def mock_env_vars(mocker):
    """Set up mock environment variables for testing."""
    env_vars = {
        "OPENAI_API_KEY": "sk-test-key-123456789",
        "GOOGLE_API_KEY": "google-test-key-123456789",
        "MONGO_URI": "mongodb://localhost:27017/test_db",
        "MONGO_DB": "test_db",
        "ALGOLIA_APP_ID": "TESTAPP123",
        "ALGOLIA_API_KEY": "test-api-key-123456789",
        "MYSQL_HOST": "localhost",
        "MYSQL_USER": "test_user",
        "MYSQL_PASSWORD": "test_password",
        "MYSQL_DATABASE": "test_database",
    }
    
    with patch.dict("os.environ", env_vars, clear=False):
        yield env_vars


# ============================================
# Custom Markers
# ============================================

def pytest_configure(config):
    """Add custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests (fast, isolated)")
    config.addinivalue_line("markers", "integration: Integration tests (requires external services)")
    config.addinivalue_line("markers", "slow: Slow tests (> 1 second)")
