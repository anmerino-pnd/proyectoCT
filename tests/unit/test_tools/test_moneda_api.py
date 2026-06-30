"""
Tests for currency conversion tool.

These tests verify that the dolar_convertion_tool correctly:
- Fetches exchange rate from MySQL (vía el pool de conexiones)
- Performs USD to MXN conversion
- Formats the result
- Handles database errors

Nota: el tipo de cambio ahora se cachea con TTL en `_fx_cache`. La fixture autouse
`_reset_fx_cache` lo limpia antes de cada test para que cada caso pegue a la (mock) DB.
"""

from unittest.mock import MagicMock, patch

import pytest
import mysql.connector


@pytest.fixture(autouse=True)
def _reset_fx_cache():
    """Limpia el cache del tipo de cambio para aislar cada test."""
    import ct.tools.moneda_api as m
    m._fx_cache["rate"] = None
    m._fx_cache["ts"] = 0.0
    yield
    m._fx_cache["rate"] = None
    m._fx_cache["ts"] = 0.0


@pytest.mark.unit
class TestDolarConversionTool:
    """Tests for dolar_convertion_tool function."""

    @patch("ct.tools.moneda_api.get_mysql_connection")
    def test_successful_conversion(self, mock_get_conn):
        """Test successful USD to MXN conversion."""
        from ct.tools.moneda_api import dolar_convertion_tool

        # Setup mock - exchange rate is 17.5 MXN per USD
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1.0, 17.5)  # (dolar, peso_mexicano)

        mock_cnx = MagicMock()
        mock_cnx.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_cnx

        # Execute - use func attribute to access the underlying function
        result = dolar_convertion_tool.func(100.0)

        # Assert
        assert "100.0 USD" in result
        assert "1750.000 MXN" in result  # 100 * 17.5
        mock_cursor.execute.assert_called_once()
        mock_cursor.close.assert_called_once()
        mock_cnx.close.assert_called_once()

    @patch("ct.tools.moneda_api.get_mysql_connection")
    def test_conversion_with_different_rate(self, mock_get_conn):
        """Test conversion with different exchange rate."""
        from ct.tools.moneda_api import dolar_convertion_tool

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1.0, 18.2)

        mock_cnx = MagicMock()
        mock_cnx.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_cnx

        result = dolar_convertion_tool.func(50.0)

        assert "50.0 USD" in result
        assert "910.000 MXN" in result  # 50 * 18.2

    @patch("ct.tools.moneda_api.get_mysql_connection")
    def test_conversion_with_decimal_amount(self, mock_get_conn):
        """Test conversion with decimal USD amount."""
        from ct.tools.moneda_api import dolar_convertion_tool

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1.0, 17.0)

        mock_cnx = MagicMock()
        mock_cnx.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_cnx

        result = dolar_convertion_tool.func(99.99)

        assert "99.99 USD" in result
        assert "1699.830 MXN" in result  # 99.99 * 17.0

    @patch("ct.tools.moneda_api.get_mysql_connection")
    def test_conversion_with_zero_amount(self, mock_get_conn):
        """Test conversion with zero USD amount."""
        from ct.tools.moneda_api import dolar_convertion_tool

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1.0, 17.5)

        mock_cnx = MagicMock()
        mock_cnx.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_cnx

        result = dolar_convertion_tool.func(0.0)

        assert "0.0 USD" in result
        assert "0.000 MXN" in result

    @patch("ct.tools.moneda_api.get_mysql_connection")
    def test_conversion_with_very_small_amount(self, mock_get_conn):
        """Test conversion with very small USD amount."""
        from ct.tools.moneda_api import dolar_convertion_tool

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1.0, 17.5)

        mock_cnx = MagicMock()
        mock_cnx.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_cnx

        result = dolar_convertion_tool.func(0.01)

        assert "0.01 USD" in result
        assert "0.175 MXN" in result

    @patch("ct.tools.moneda_api.get_mysql_connection")
    def test_conversion_with_large_amount(self, mock_get_conn):
        """Test conversion with large USD amount."""
        from ct.tools.moneda_api import dolar_convertion_tool

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1.0, 17.5)

        mock_cnx = MagicMock()
        mock_cnx.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_cnx

        result = dolar_convertion_tool.func(10000.0)

        assert "10000.0 USD" in result
        assert "175000.000 MXN" in result

    @patch("ct.tools.moneda_api.get_mysql_connection")
    def test_no_exchange_rate_found(self, mock_get_conn):
        """Test behavior when no exchange rate is found."""
        from ct.tools.moneda_api import dolar_convertion_tool

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None

        mock_cnx = MagicMock()
        mock_cnx.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_cnx

        result = dolar_convertion_tool.func(100.0)

        # Sin tipo de cambio (ni cacheado) -> el tool no devuelve conversión
        assert result is None

    @patch("ct.tools.moneda_api.get_mysql_connection")
    def test_database_connection_error(self, mock_get_conn):
        """Test handling of database connection errors."""
        from ct.tools.moneda_api import dolar_convertion_tool

        # El pool/conexión falla al obtenerse
        mock_get_conn.side_effect = mysql.connector.Error("Connection refused")

        result = dolar_convertion_tool.func(100.0)

        assert "Error de base de datos" in result
        assert "Connection refused" in result

    @patch("ct.tools.moneda_api.get_mysql_connection")
    def test_database_query_error(self, mock_get_conn):
        """Test handling of database query errors."""
        from ct.tools.moneda_api import dolar_convertion_tool

        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = mysql.connector.Error("Table not found")

        mock_cnx = MagicMock()
        mock_cnx.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_cnx

        result = dolar_convertion_tool.func(100.0)

        assert "Error de base de datos" in result

    @patch("ct.tools.moneda_api.get_mysql_connection")
    def test_result_format_has_three_decimals(self, mock_get_conn):
        """Test that result is formatted with 3 decimal places."""
        from ct.tools.moneda_api import dolar_convertion_tool

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1.0, 17.1234)  # Rate with many decimals

        mock_cnx = MagicMock()
        mock_cnx.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_cnx

        result = dolar_convertion_tool.func(10.0)

        import re
        assert re.search(r"\.\d{3} MXN", result), f"Expected 3-decimal format, got: {result}"

    @patch("ct.tools.moneda_api.get_mysql_connection")
    def test_exchange_rate_is_cached(self, mock_get_conn):
        """El tipo de cambio se cachea: una 2ª conversión no vuelve a pegarle a la DB."""
        from ct.tools.moneda_api import dolar_convertion_tool

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1.0, 17.5)
        mock_cnx = MagicMock()
        mock_cnx.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_cnx

        dolar_convertion_tool.func(100.0)
        dolar_convertion_tool.func(200.0)

        # Solo una obtención de conexión pese a dos conversiones
        mock_get_conn.assert_called_once()

    def test_query_contains_correct_fields(self):
        """Test that the SQL query includes required fields."""
        from ct.tools.moneda_api import query

        assert "dolar" in query
        assert "filtro" in query
        assert "peso_mexicano" in query or "AS peso_mexicano" in query
        assert "monedas_api" in query
