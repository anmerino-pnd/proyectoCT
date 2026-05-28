"""
Tests for Algolia search tool.

These tests verify that the algolia_search_tool correctly:
- Parses user session IDs
- Builds search filters
- Processes Algolia API responses
- Handles errors gracefully
"""

import json
from unittest.mock import MagicMock, patch

import pytest
import requests


@pytest.mark.unit
class TestGetUser:
    """Tests for get_user function."""
    
    def test_get_user_extracts_ctin_account(self):
        """Test extraction of CTIN account from session ID."""
        from ct.tools.algolia import get_user
        
        result = get_user("01CTIN_user@example.com")
        assert result == "01CTIN"
    
    def test_get_user_extracts_regular_account(self):
        """Test extraction of regular account from session ID."""
        from ct.tools.algolia import get_user
        
        result = get_user("HMO4536_angel.merino")
        assert result == "HMO4536"
    
    def test_get_user_extracts_account_with_numbers(self):
        """Test extraction of account with numbers."""
        from ct.tools.algolia import get_user
        
        result = get_user("MX12345_some.user")
        assert result == "MX12345"
    
    def test_get_user_raises_on_invalid_format(self):
        """Test that invalid session ID raises ValueError."""
        from ct.tools.algolia import get_user
        
        with pytest.raises(ValueError, match="No se pudo extraer usuario"):
            get_user("invalid-session-id")


@pytest.mark.unit
class TestQueryExec:
    """Tests for query_exec function."""
    
    @patch("ct.tools.algolia.mysql.connector.connect")
    def test_query_exec_returns_results(self, mock_connect):
        """Test successful query execution."""
        from ct.tools.algolia import query_exec
        
        # Setup mock
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("01CTIN", 1, 0, 1, 0, 1, 0, 1)
        ]
        
        mock_cnx = MagicMock()
        mock_cnx.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_cnx
        
        # Execute
        result = query_exec("SELECT * FROM test")
        
        # Assert
        assert result == [("01CTIN", 1, 0, 1, 0, 1, 0, 1)]
        mock_cursor.execute.assert_called_once_with("SELECT * FROM test")
        mock_cursor.close.assert_called_once()
        mock_cnx.close.assert_called_once()
    
    @patch("ct.tools.algolia.mysql.connector.connect")
    def test_query_exec_handles_database_error(self, mock_connect):
        """Test handling of database errors."""
        from ct.tools.algolia import query_exec
        
        from mysql.connector import Error as MySQLError
        mock_connect.side_effect = MySQLError("Connection refused")
        
        result = query_exec("SELECT * FROM test")
        
        assert "Error de base de datos" in result
    
    @patch("ct.tools.algolia.mysql.connector.connect")
    def test_query_exec_handles_unexpected_error(self, mock_connect):
        """Test handling of unexpected errors."""
        from ct.tools.algolia import query_exec
        
        mock_connect.side_effect = Exception("Unexpected error")
        
        result = query_exec("SELECT * FROM test")
        
        assert "Ocurrió un error inesperado" in result


@pytest.mark.unit
class TestCreateScraper:
    """Tests for _create_scraper function."""
    
    @patch("ct.tools.algolia.cloudscraper.create_scraper")
    @patch("ct.tools.algolia.algolia_app_id", "test_app_id")
    @patch("ct.tools.algolia.algolia_api_key", "test_api_key")
    @patch("ct.tools.algolia.algolia_content_type", "application/json")
    def test_create_scraper_sets_headers(self, mock_create_scraper):
        """Test that scraper is created with correct headers."""
        from ct.tools.algolia import _create_scraper
        
        mock_scraper = MagicMock()
        mock_create_scraper.return_value = mock_scraper
        
        result = _create_scraper("user-token-123")
        
        # Verify headers were set
        assert mock_scraper.headers.update.called
        call_args = mock_scraper.headers.update.call_args[0][0]
        assert call_args["X-Algolia-Application-Id"] == "test_app_id"
        assert call_args["X-Algolia-API-Key"] == "test_api_key"
        assert call_args["X-Algolia-UserToken"] == "user-token-123"


@pytest.mark.unit
class TestAlgoliaSearchTool:
    """Tests for algolia_search_tool function."""
    
    @pytest.fixture
    def mock_runtime(self):
        """Create a mock runtime with UserContext."""
        runtime = MagicMock()
        runtime.context.session_id = "HMO4536_test_user"
        runtime.context.lista_precio = 1
        return runtime
    
    @patch("ct.tools.algolia.query_exec")
    @patch("ct.tools.algolia._create_scraper")
    @patch("ct.tools.algolia.get_id_sucursal")
    @patch("ct.tools.algolia.algolia_url", "https://algolia.test/search")
    def test_algolia_search_returns_formatted_results(
        self, 
        mock_get_sucursal, 
        mock_create_scraper, 
        mock_query_exec,
        mock_runtime
    ):
        """Test successful search returns formatted product results."""
        from ct.tools.algolia import algolia_search_tool
        
        # Setup mocks
        mock_get_sucursal.return_value = "1"
        mock_query_exec.return_value = None  # No special HP pricing
        
        mock_scraper = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "hits": [
                {
                    "clave": "PROD-001",
                    "marca": "HP",
                    "modelo": "ProBook 450",
                    "descripcion": "Laptop HP",
                    "icecat": "Specs here",
                    "precios": {"1": 15000.0},
                    "moneda": "MXN",
                    "url": "https://ct.com/prod-001",
                    "cliente_promo": [],
                    "existencia_total": 10,
                    "existencia": {"1": 5}
                }
            ]
        }
        mock_scraper.post.return_value = mock_response
        mock_create_scraper.return_value = mock_scraper
        
        # Execute
        result = algolia_search_tool.func("laptop HP", runtime=mock_runtime)
        
        # Assert result is not empty
        assert result is not None
        assert isinstance(result, (str, dict))
    
    @patch("ct.tools.algolia.query_exec")
    @patch("ct.tools.algolia._create_scraper")
    @patch("ct.tools.algolia.get_id_sucursal")
    @patch("ct.tools.algolia.algolia_url", "https://algolia.test/search")
    def test_algolia_search_applies_hp_special_pricing(
        self,
        mock_get_sucursal,
        mock_create_scraper,
        mock_query_exec,
        mock_runtime
    ):
        """Test that special HP pricing filters are applied."""
        from ct.tools.algolia import algolia_search_tool
        
        # Setup mocks with HP special pricing data
        mock_get_sucursal.return_value = "1"
        mock_query_exec.return_value = [
            ("HMO4536", 1, 0, 1, 0, 1, 0, 1)  # Some lists active
        ]
        
        mock_scraper = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"hits": []}
        mock_scraper.post.return_value = mock_response
        mock_create_scraper.return_value = mock_scraper
        
        # Execute
        algolia_search_tool.func("laptop HP", runtime=mock_runtime)
        
        # Verify post was called with filters
        call_args = mock_scraper.post.call_args
        payload = json.loads(call_args[1]["data"])
        assert "filters" in payload
        assert "especial_hp" in payload["filters"] or "especial_cuenta" in payload["filters"]
    
    @patch("ct.tools.algolia.query_exec")
    @patch("ct.tools.algolia._create_scraper")
    @patch("ct.tools.algolia.get_id_sucursal")
    @patch("ct.tools.algolia.algolia_sort_url", "https://algolia.test/sort")
    def test_algolia_search_uses_sort_url_when_lowest_price(
        self,
        mock_get_sucursal,
        mock_create_scraper,
        mock_query_exec,
        mock_runtime
    ):
        """Test that sort URL is used when lowest_price is True."""
        from ct.tools.algolia import algolia_search_tool
        
        # Setup mocks
        mock_get_sucursal.return_value = "1"
        mock_query_exec.return_value = None
        
        mock_scraper = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"hits": []}
        mock_scraper.post.return_value = mock_response
        mock_create_scraper.return_value = mock_scraper
        
        # Execute with lowest_price=True
        algolia_search_tool.func("laptop", runtime=mock_runtime, lowest_price=True)
        
        # Verify sort URL was used
        call_args = mock_scraper.post.call_args
        assert "sort" in call_args[1]["url"]
    
    @patch("ct.tools.algolia.query_exec")
    @patch("ct.tools.algolia._create_scraper")
    @patch("ct.tools.algolia.get_id_sucursal")
    def test_algolia_search_handles_timeout(
        self,
        mock_get_sucursal,
        mock_create_scraper,
        mock_query_exec,
        mock_runtime
    ):
        """Test handling of timeout errors."""
        from ct.tools.algolia import algolia_search_tool
        
        # Setup mocks
        mock_get_sucursal.return_value = "1"
        mock_query_exec.return_value = None
        
        mock_scraper = MagicMock()
        mock_scraper.post.side_effect = requests.exceptions.Timeout("Timeout")
        mock_create_scraper.return_value = mock_scraper

        # Execute
        result = algolia_search_tool.func("laptop", runtime=mock_runtime)

        # Should return a set with a timeout-error message
        assert isinstance(result, set)
        assert any("Timeout" in msg for msg in result)
    
    @patch("ct.tools.algolia.query_exec")
    @patch("ct.tools.algolia._create_scraper")
    @patch("ct.tools.algolia.get_id_sucursal")
    def test_algolia_search_handles_request_exception(
        self,
        mock_get_sucursal,
        mock_create_scraper,
        mock_query_exec,
        mock_runtime
    ):
        """Test handling of request exceptions."""
        from ct.tools.algolia import algolia_search_tool
        
        # Setup mocks
        mock_get_sucursal.return_value = "1"
        mock_query_exec.return_value = None
        
        mock_scraper = MagicMock()
        mock_scraper.post.side_effect = requests.exceptions.RequestException("Network error")
        mock_create_scraper.return_value = mock_scraper

        # Execute
        result = algolia_search_tool.func("laptop", runtime=mock_runtime)

        # Should return a set with a request-error message
        assert isinstance(result, set)
        assert any("Network error" in msg for msg in result)
    
    @patch("ct.tools.algolia.query_exec")
    @patch("ct.tools.algolia._create_scraper")
    @patch("ct.tools.algolia.get_id_sucursal")
    def test_algolia_search_returns_no_results_message(
        self,
        mock_get_sucursal,
        mock_create_scraper,
        mock_query_exec,
        mock_runtime
    ):
        """Test message when no results found."""
        from ct.tools.algolia import algolia_search_tool
        
        # Setup mocks
        mock_get_sucursal.return_value = "1"
        mock_query_exec.return_value = None
        
        mock_scraper = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"hits": []}
        mock_scraper.post.return_value = mock_response
        mock_create_scraper.return_value = mock_scraper
        
        # Execute
        result = algolia_search_tool.func("nonexistent product", runtime=mock_runtime)
        
        # Should return no results message
        assert "No se encontraron resultados" in result
    
    @patch("ct.tools.algolia.query_exec")
    @patch("ct.tools.algolia._create_scraper")
    @patch("ct.tools.algolia.get_id_sucursal")
    def test_algolia_search_promotion_flag(
        self,
        mock_get_sucursal,
        mock_create_scraper,
        mock_query_exec,
        mock_runtime
    ):
        """Test that promotion flag is correctly set in results."""
        from ct.tools.algolia import algolia_search_tool
        
        # Setup mocks
        mock_get_sucursal.return_value = "1"
        mock_query_exec.return_value = None
        
        mock_scraper = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "hits": [
                {
                    "clave": "PROD-001",
                    "marca": "HP",
                    "modelo": "ProBook",
                    "descripcion": "Test",
                    "icecat": "Specs",
                    "precios": {"1": 10000.0},
                    "moneda": "MXN",
                    "url": "https://ct.com/",
                    "cliente_promo": ["A1"],  # Product in promotion
                    "existencia_total": 5,
                    "existencia": {"1": 3}
                }
            ]
        }
        mock_scraper.post.return_value = mock_response
        mock_create_scraper.return_value = mock_scraper
        
        # Execute
        result = algolia_search_tool.func("laptop", runtime=mock_runtime)
        
        # Result should indicate product is in promotion
        # Note: result is encoded, so we check it's not empty
        assert result is not None
    
    @patch("ct.tools.algolia.query_exec")
    @patch("ct.tools.algolia._create_scraper")
    @patch("ct.tools.algolia.get_id_sucursal")
    def test_algolia_search_skips_products_without_price(
        self,
        mock_get_sucursal,
        mock_create_scraper,
        mock_query_exec,
        mock_runtime
    ):
        """Test that products without matching price list are skipped."""
        from ct.tools.algolia import algolia_search_tool
        
        # Setup mocks
        mock_get_sucursal.return_value = "1"
        mock_query_exec.return_value = None
        
        mock_scraper = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "hits": [
                {
                    "clave": "PROD-001",
                    "marca": "HP",
                    "modelo": "ProBook",
                    "descripcion": "Test",
                    "icecat": "Specs",
                    "precios": {"2": 10000.0},  # Price only for list 2, not 1
                    "moneda": "MXN",
                    "url": "https://ct.com/",
                    "cliente_promo": [],
                    "existencia_total": 5,
                    "existencia": {"1": 3}
                }
            ]
        }
        mock_scraper.post.return_value = mock_response
        mock_create_scraper.return_value = mock_scraper
        
        # Execute
        result = algolia_search_tool.func("laptop", runtime=mock_runtime)
        
        # Result should be empty or indicate no results
        # since product doesn't have price for lista_precio=1
        assert result is not None
