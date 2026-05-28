"""
Tests for sales rules tool.

These tests verify that the sales_rules_tool correctly:
- Extracts branch office ID from session
- Queries promotion data from MySQL
- Formats promotion messages
- Handles different promotion types
"""

import json
from datetime import datetime, date
from unittest.mock import MagicMock, patch, mock_open

import pytest
import mysql.connector


@pytest.mark.unit
class TestGetIdSucursal:
    """Tests for get_id_sucursal function."""
    
    @pytest.fixture
    def mock_sucursales(self):
        """Sample sucursales data."""
        return [
            {"nemonico": "HMO", "idSucursal": 1},
            {"nemonico": "GDL", "idSucursal": 2},
            {"nemonico": "CDMX", "idSucursal": 3},
            {"nemonico": "MTY", "idSucursal": 4},
        ]
    
    @patch("ct.tools.sales_rules_tool.SUCURSALES", [
        {"nemonico": "HMO", "idSucursal": 1},
        {"nemonico": "GDL", "idSucursal": 2},
    ])
    def test_get_id_sucursal_from_ctin_session(self):
        """Test extraction from CTIN session ID."""
        from ct.tools.sales_rules_tool import get_id_sucursal
        
        result = get_id_sucursal("01CTIN_user@example.com")
        assert result == "1"
    
    @patch("ct.tools.sales_rules_tool.SUCURSALES", [
        {"nemonico": "HMO", "idSucursal": 1},
        {"nemonico": "GDL", "idSucursal": 2},
    ])
    def test_get_id_sucursal_from_regular_session(self):
        """Test extraction from regular session ID."""
        from ct.tools.sales_rules_tool import get_id_sucursal
        
        result = get_id_sucursal("HMO4536_test.user")
        assert result == "1"
    
    @patch("ct.tools.sales_rules_tool.SUCURSALES", [
        {"nemonico": "CDMX", "idSucursal": 3},
    ])
    def test_get_id_sucursal_different_branch(self):
        """Test extraction for different branch."""
        from ct.tools.sales_rules_tool import get_id_sucursal
        
        result = get_id_sucursal("CDMX1234_user@test.com")
        assert result == "3"
    
    @patch("ct.tools.sales_rules_tool.SUCURSALES", [
        {"nemonico": "HMO", "idSucursal": 1},
    ])
    def test_get_id_sucursal_invalid_session_raises(self):
        """Test that invalid session raises ValueError."""
        from ct.tools.sales_rules_tool import get_id_sucursal
        
        with pytest.raises(ValueError, match="No se pudo extraer nemonico"):
            get_id_sucursal("invalid-session-id")
    
    @patch("ct.tools.sales_rules_tool.SUCURSALES", [
        {"nemonico": "HMO", "idSucursal": 1},
    ])
    def test_get_id_sucursal_unknown_nemonico_raises(self):
        """Test that unknown nemonico raises ValueError."""
        from ct.tools.sales_rules_tool import get_id_sucursal
        
        with pytest.raises(ValueError, match="No se encontró idSucursal"):
            get_id_sucursal("XYZ1234_user@test.com")


@pytest.mark.unit
class TestQuerySales:
    """Tests for query_sales function."""
    
    def test_query_sales_returns_string(self):
        """Test that query_sales returns a SQL string."""
        from ct.tools.sales_rules_tool import query_sales
        
        result = query_sales()
        
        assert isinstance(result, str)
        assert "SELECT" in result.upper()
        assert "FROM promociones" in result
    
    def test_query_sales_includes_required_fields(self):
        """Test that query includes all required fields."""
        from ct.tools.sales_rules_tool import query_sales
        
        result = query_sales()
        
        # Check for key fields
        assert "precio_regular" in result
        assert "precio_oferta" in result
        assert "descuento" in result
        assert "EnCompraDE" in result
        assert "Unidades" in result
        assert "limitadoA" in result
        assert "fecha_inicio" in result
        assert "fecha_fin" in result
    
    def test_query_sales_has_date_filters(self):
        """Test that query filters by date."""
        from ct.tools.sales_rules_tool import query_sales
        
        result = query_sales()
        
        assert "fecha_fin" in result
        assert "fecha_inicio" in result
        assert "CURRENT_DATE" in result
    
    def test_query_sales_uses_parameters(self):
        """Test that query uses parameterized values."""
        from ct.tools.sales_rules_tool import query_sales
        
        result = query_sales()
        
        assert "%s" in result  # MySQL parameter placeholder


@pytest.mark.unit
class TestSalesRulesTool:
    """Tests for sales_rules_tool function."""
    
    @pytest.fixture
    def mock_runtime(self):
        """Create a mock runtime with UserContext."""
        runtime = MagicMock()
        runtime.context.session_id = "HMO4536_test_user"
        runtime.context.lista_precio = 1
        return runtime
    
    @patch("ct.tools.sales_rules_tool.mysql.connector.connect")
    @patch("ct.tools.sales_rules_tool.get_id_sucursal")
    def test_sales_rules_no_promotion_found(
        self, mock_get_sucursal, mock_connect, mock_runtime
    ):
        """Test message when no promotion is found."""
        from ct.tools.sales_rules_tool import sales_rules_tool
        
        # Setup mocks
        mock_get_sucursal.return_value = "1"
        
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None  # No promotion
        
        mock_cnx = MagicMock()
        mock_cnx.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_cnx
        
        # Execute
        result = sales_rules_tool.func("PROD-001", runtime=mock_runtime)
        
        # Assert
        assert "ya no se encuentra en promoción" in result
        mock_cursor.close.assert_called_once()
        mock_cnx.close.assert_called_once()
    
    @patch("ct.tools.sales_rules_tool.mysql.connector.connect")
    @patch("ct.tools.sales_rules_tool.get_id_sucursal")
    def test_sales_rules_future_promotion(
        self, mock_get_sucursal, mock_connect, mock_runtime
    ):
        """Test handling of future promotion."""
        from ct.tools.sales_rules_tool import sales_rules_tool
        
        # Setup mocks
        mock_get_sucursal.return_value = "1"
        
        future_date = datetime.now().date().replace(year=datetime.now().year + 1)
        
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (
            1000.0,    # precio_regular
            0.0,       # precio_oferta
            0.0,       # descuento
            0,         # EnCompraDE
            0,         # Unidades
            0,         # limitadoA
            None,      # ProductosGratis
            future_date,  # fecha_inicio (future)
            future_date,  # fecha_fin (future)
            1,         # moneda (MXN)
        )
        
        mock_cnx = MagicMock()
        mock_cnx.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_cnx
        
        # Execute
        result = sales_rules_tool.func("PROD-001", runtime=mock_runtime)
        
        # Assert
        assert "sin promoción vigente" in result
        assert "$1000.00" in result
    
    @patch("ct.tools.sales_rules_tool.mysql.connector.connect")
    @patch("ct.tools.sales_rules_tool.get_id_sucursal")
    def test_sales_rules_with_offer_price(
        self, mock_get_sucursal, mock_connect, mock_runtime
    ):
        """Test promotion with special offer price."""
        from ct.tools.sales_rules_tool import sales_rules_tool
        
        # Setup mocks
        mock_get_sucursal.return_value = "1"
        
        past_date = datetime.now().date().replace(year=datetime.now().year - 1)
        
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (
            1000.0,    # precio_regular
            800.0,     # precio_oferta (lower than regular)
            0.0,       # descuento
            0,         # EnCompraDE
            0,         # Unidades
            0,         # limitadoA
            None,      # ProductosGratis
            past_date, # fecha_inicio
            past_date, # fecha_fin
            1,         # moneda (MXN)
        )
        
        mock_cnx = MagicMock()
        mock_cnx.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_cnx
        
        # Execute
        result = sales_rules_tool.func("PROD-001", runtime=mock_runtime)
        
        # Assert
        assert "$800.00" in result
        assert "MXN" in result
    
    @patch("ct.tools.sales_rules_tool.mysql.connector.connect")
    @patch("ct.tools.sales_rules_tool.get_id_sucursal")
    def test_sales_rules_with_discount_percentage(
        self, mock_get_sucursal, mock_connect, mock_runtime
    ):
        """Test promotion with percentage discount."""
        from ct.tools.sales_rules_tool import sales_rules_tool
        
        # Setup mocks
        mock_get_sucursal.return_value = "1"
        
        past_date = datetime.now().date().replace(year=datetime.now().year - 1)
        
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (
            1000.0,    # precio_regular
            0.0,       # precio_oferta
            20.0,      # descuento (20% off)
            0,         # EnCompraDE
            0,         # Unidades
            0,         # limitadoA
            None,      # ProductosGratis
            past_date, # fecha_inicio
            past_date, # fecha_fin
            1,         # moneda (MXN)
        )
        
        mock_cnx = MagicMock()
        mock_cnx.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_cnx
        
        # Execute
        result = sales_rules_tool.func("PROD-001", runtime=mock_runtime)
        
        # Assert
        assert "$1000.00" in result
        assert "$800.00" in result  # 1000 - 20% = 800
        assert "20% desc" in result
    
    @patch("ct.tools.sales_rules_tool.mysql.connector.connect")
    @patch("ct.tools.sales_rules_tool.get_id_sucursal")
    def test_sales_rules_buy_x_get_y(
        self, mock_get_sucursal, mock_connect, mock_runtime
    ):
        """Test buy X get Y free promotion."""
        from ct.tools.sales_rules_tool import sales_rules_tool
        
        # Setup mocks
        mock_get_sucursal.return_value = "1"
        
        past_date = datetime.now().date().replace(year=datetime.now().year - 1)
        
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (
            1000.0,    # precio_regular
            0.0,       # precio_oferta
            0.0,       # descuento
            2,         # EnCompraDE (buy 2)
            1,         # Unidades (get 1 free)
            0,         # limitadoA
            None,      # ProductosGratis
            past_date, # fecha_inicio
            past_date, # fecha_fin
            1,         # moneda (MXN)
        )
        
        mock_cnx = MagicMock()
        mock_cnx.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_cnx
        
        # Execute
        result = sales_rules_tool.func("PROD-001", runtime=mock_runtime)
        
        # Assert
        assert "En compra de 2" in result
        assert "recibe 1 gratis" in result
    
    @patch("ct.tools.sales_rules_tool.mysql.connector.connect")
    @patch("ct.tools.sales_rules_tool.get_id_sucursal")
    def test_sales_rules_with_limit(
        self, mock_get_sucursal, mock_connect, mock_runtime
    ):
        """Test promotion with quantity limit."""
        from ct.tools.sales_rules_tool import sales_rules_tool
        
        # Setup mocks
        mock_get_sucursal.return_value = "1"
        
        past_date = datetime.now().date().replace(year=datetime.now().year - 1)
        
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (
            1000.0,    # precio_regular
            800.0,     # precio_oferta
            0.0,       # descuento
            0,         # EnCompraDE
            0,         # Unidades
            5,         # limitadoA (max 5 per customer)
            None,      # ProductosGratis
            past_date, # fecha_inicio
            past_date, # fecha_fin
            1,         # moneda (MXN)
        )
        
        mock_cnx = MagicMock()
        mock_cnx.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_cnx
        
        # Execute
        result = sales_rules_tool.func("PROD-001", runtime=mock_runtime)
        
        # Assert
        assert "Limitado a 5 unidades" in result
    
    @patch("ct.tools.sales_rules_tool.mysql.connector.connect")
    @patch("ct.tools.sales_rules_tool.get_id_sucursal")
    def test_sales_rules_with_end_date(
        self, mock_get_sucursal, mock_connect, mock_runtime
    ):
        """Test promotion with end date."""
        from ct.tools.sales_rules_tool import sales_rules_tool
        
        # Setup mocks
        mock_get_sucursal.return_value = "1"
        
        past_date = datetime.now().date().replace(year=datetime.now().year - 1)
        future_date = datetime.now().date().replace(year=datetime.now().year + 1)
        
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (
            1000.0,    # precio_regular
            800.0,     # precio_oferta
            0.0,       # descuento
            0,         # EnCompraDE
            0,         # Unidades
            0,         # limitadoA
            None,      # ProductosGratis
            past_date, # fecha_inicio
            future_date, # fecha_fin (valid until this date)
            1,         # moneda (MXN)
        )
        
        mock_cnx = MagicMock()
        mock_cnx.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_cnx
        
        # Execute
        result = sales_rules_tool.func("PROD-001", runtime=mock_runtime)
        
        # Assert
        assert "Vigente hasta el" in result
    
    @patch("ct.tools.sales_rules_tool.mysql.connector.connect")
    @patch("ct.tools.sales_rules_tool.get_id_sucursal")
    def test_sales_rules_price_increase(
        self, mock_get_sucursal, mock_connect, mock_runtime
    ):
        """Test handling of price increase (offer > regular)."""
        from ct.tools.sales_rules_tool import sales_rules_tool
        
        # Setup mocks
        mock_get_sucursal.return_value = "1"
        
        past_date = datetime.now().date().replace(year=datetime.now().year - 1)
        
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (
            1000.0,    # precio_regular
            1200.0,    # precio_oferta (higher - indicates price increase)
            0.0,       # descuento
            0,         # EnCompraDE
            0,         # Unidades
            0,         # limitadoA
            None,      # ProductosGratis
            past_date, # fecha_inicio
            past_date, # fecha_fin
            1,         # moneda (MXN)
        )
        
        mock_cnx = MagicMock()
        mock_cnx.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_cnx
        
        # Execute
        result = sales_rules_tool.func("PROD-001", runtime=mock_runtime)
        
        # Assert
        assert "Cambio de precio base" in result
        assert "$1200.00" in result
        assert "no se considera promoción" in result
    
    @patch("ct.tools.sales_rules_tool.mysql.connector.connect")
    @patch("ct.tools.sales_rules_tool.get_id_sucursal")
    def test_sales_rules_usd_currency(
        self, mock_get_sucursal, mock_connect, mock_runtime
    ):
        """Test promotion with USD currency."""
        from ct.tools.sales_rules_tool import sales_rules_tool
        
        # Setup mocks
        mock_get_sucursal.return_value = "1"
        
        past_date = datetime.now().date().replace(year=datetime.now().year - 1)
        
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (
            500.0,     # precio_regular
            400.0,     # precio_oferta
            0.0,       # descuento
            0,         # EnCompraDE
            0,         # Unidades
            0,         # limitadoA
            None,      # ProductosGratis
            past_date, # fecha_inicio
            past_date, # fecha_fin
            2,         # moneda (USD, not 1)
        )
        
        mock_cnx = MagicMock()
        mock_cnx.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_cnx
        
        # Execute
        result = sales_rules_tool.func("PROD-001", runtime=mock_runtime)
        
        # Assert
        assert "USD" in result
    
    @patch("ct.tools.sales_rules_tool.mysql.connector.connect")
    @patch("ct.tools.sales_rules_tool.get_id_sucursal")
    def test_sales_rules_database_error(
        self, mock_get_sucursal, mock_connect, mock_runtime
    ):
        """Test handling of database errors."""
        from ct.tools.sales_rules_tool import sales_rules_tool
        
        # Setup mocks
        mock_get_sucursal.return_value = "1"
        mock_connect.side_effect = mysql.connector.Error("Connection refused")
        
        # Execute
        result = sales_rules_tool.func("PROD-001", runtime=mock_runtime)
        
        # Assert
        assert "Error de base de datos" in result
    
    @patch("ct.tools.sales_rules_tool.mysql.connector.connect")
    @patch("ct.tools.sales_rules_tool.get_id_sucursal")
    def test_sales_rules_unexpected_error(
        self, mock_get_sucursal, mock_connect, mock_runtime
    ):
        """Test handling of unexpected errors."""
        from ct.tools.sales_rules_tool import sales_rules_tool
        
        # Setup mocks
        mock_get_sucursal.side_effect = Exception("Unexpected error")
        
        # Execute
        result = sales_rules_tool.func("PROD-001", runtime=mock_runtime)
        
        # Assert
        assert "Ocurrió un error inesperado" in result
