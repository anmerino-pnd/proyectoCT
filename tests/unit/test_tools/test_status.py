"""
Tests for order status tool.

These tests verify that the status_tool correctly:
- Determines search field based on factura format
- Filters by client for non-CTIN users
- Returns appropriate messages for each status
- Handles timezone conversion for 'Transito' status
- Queries ESD download counts from MySQL
"""

import re
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
import pytz
import mysql.connector
from pymongo import ASCENDING


@pytest.mark.unit
class TestDescargasEnviadas:
    """Tests for descargas_enviadas function."""
    
    @patch("ct.tools.status.mysql.connector.connect")
    def test_descargas_enviadas_returns_count(self, mock_connect):
        """Test successful query returns download count."""
        from ct.tools.status import descargas_enviadas
        
        # Setup mock
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (5,)  # 5 downloads
        
        mock_cnx = MagicMock()
        mock_cnx.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_cnx
        
        # Execute
        result = descargas_enviadas("FAC-001")
        
        # Assert
        assert result == 5
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        assert "esd_licencias_usuarios" in call_args[0][0]
        assert call_args[0][1] == ("FAC-001",)
    
    @patch("ct.tools.status.mysql.connector.connect")
    def test_descargas_enviadas_returns_none_if_no_result(self, mock_connect):
        """Test when no download records found."""
        from ct.tools.status import descargas_enviadas
        
        # Setup mock
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        
        mock_cnx = MagicMock()
        mock_cnx.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_cnx
        
        # Execute
        result = descargas_enviadas("FAC-001")
        
        # Assert - function doesn't return anything when no result
        assert result is None
    
    @patch("ct.tools.status.mysql.connector.connect")
    def test_descargas_enviadas_handles_database_error(self, mock_connect):
        """Test handling of database errors."""
        from ct.tools.status import descargas_enviadas
        
        mock_connect.side_effect = mysql.connector.Error("Connection refused")
        
        result = descargas_enviadas("FAC-001")
        
        assert "Error de base de datos" in result
    
    @patch("ct.tools.status.mysql.connector.connect")
    def test_descargas_enviadas_handles_unexpected_error(self, mock_connect):
        """Test handling of unexpected errors."""
        from ct.tools.status import descargas_enviadas
        
        mock_connect.side_effect = Exception("Unexpected error")
        
        result = descargas_enviadas("FAC-001")
        
        assert "Ocurrió un error inesperado" in result


@pytest.mark.unit
class TestStatusTool:
    """Tests for status_tool function."""
    
    @pytest.fixture
    def mock_runtime(self):
        """Create a mock runtime with UserContext."""
        runtime = MagicMock()
        runtime.context.session_id = "HMO4536_test_user"
        return runtime
    
    @pytest.fixture
    def mock_pedidos_collection(self):
        """Create a mock MongoDB collection."""
        return MagicMock()
    
    def _create_mock_pedido(self, status_key, status_data=None):
        """Helper to create mock pedido data."""
        pedido = {
            "estatus": {status_key: status_data or {}},
            "pedido": {
                "encabezado": {"cliente": "HMO4536"},
                "detalle": {"producto": []}
            }
        }
        return pedido
    
    @patch("ct.tools.status.pedidos")
    def test_status_uses_folio_field_for_w_prefix(self, mock_pedidos, mock_runtime):
        """Test that W-prefixed factura searches in folio field."""
        from ct.tools.status import status_tool
        
        # Setup
        mock_pedidos.find_one.return_value = None
        
        # Execute
        status_tool.func("WXX-12345", runtime=mock_runtime)
        
        # Assert
        call_args = mock_pedidos.find_one.call_args
        query = call_args[0][0]
        assert "pedido.encabezado.folio" in str(query)
    
    @patch("ct.tools.status.pedidos")
    def test_status_uses_factura_field_for_regular(self, mock_pedidos, mock_runtime):
        """Test that regular factura searches in Facturado field."""
        from ct.tools.status import status_tool
        
        # Setup
        mock_pedidos.find_one.return_value = None
        
        # Execute
        status_tool.func("FAC-12345", runtime=mock_runtime)
        
        # Assert
        call_args = mock_pedidos.find_one.call_args
        query = call_args[0][0]
        assert "estatus.Facturado.folioFactura" in str(query)
    
    @patch("ct.tools.status.pedidos")
    def test_status_filters_by_client_for_non_ctin(self, mock_pedidos, mock_runtime):
        """Test that non-CTIN users can only see their own orders."""
        from ct.tools.status import status_tool
        
        # Setup
        mock_pedidos.find_one.return_value = None
        mock_runtime.context.session_id = "HMO4536_user@example.com"
        
        # Execute
        status_tool.func("FAC-12345", runtime=mock_runtime)
        
        # Assert
        call_args = mock_pedidos.find_one.call_args
        query = call_args[0][0]
        assert "HMO4536" in str(query)
    
    @patch("ct.tools.status.pedidos")
    def test_status_no_client_filter_for_ctin(self, mock_pedidos):
        """Test that CTIN users can see any order."""
        from ct.tools.status import status_tool
        
        # Setup
        mock_pedidos.find_one.return_value = None
        mock_runtime = MagicMock()
        mock_runtime.context.session_id = "01CTIN_user@example.com"
        
        # Execute
        status_tool.func("FAC-12345", runtime=mock_runtime)
        
        # Assert
        call_args = mock_pedidos.find_one.call_args
        query = call_args[0][0]
        # Should not have client filter
        assert "pedido.encabezado.cliente" not in str(query)
    
    @patch("ct.tools.status.pedidos")
    def test_status_returns_not_found_message(self, mock_pedidos, mock_runtime):
        """Test message when order not found."""
        from ct.tools.status import status_tool
        
        # Setup
        mock_pedidos.find_one.return_value = None
        
        # Execute
        result = status_tool.func("INVALID-001", runtime=mock_runtime)
        
        # Assert
        assert "no se encontró el pedido" in result
    
    @patch("ct.tools.status.pedidos")
    def test_status_pendiente(self, mock_pedidos, mock_runtime):
        """Test status message for 'Pendiente'."""
        from ct.tools.status import status_tool
        
        # Setup
        mock_pedidos.find_one.return_value = {
            "estatus": {"Pendiente": {}},
            "pedido": {"encabezado": {}, "detalle": {"producto": []}}
        }
        
        # Execute
        result = status_tool.func("FAC-001", runtime=mock_runtime)
        
        # Assert
        assert result == "Pedido en generación"
    
    @patch("ct.tools.status.pedidos")
    def test_status_confirmado(self, mock_pedidos, mock_runtime):
        """Test status message for 'Confirmado'."""
        from ct.tools.status import status_tool
        
        # Setup
        mock_pedidos.find_one.return_value = {
            "estatus": {"Confirmado": {}},
            "pedido": {"encabezado": {}, "detalle": {"producto": []}}
        }
        
        # Execute
        result = status_tool.func("FAC-001", runtime=mock_runtime)
        
        # Assert
        assert result == "Pedido creado"
    
    @patch("ct.tools.status.pedidos")
    def test_status_facturado(self, mock_pedidos, mock_runtime):
        """Test status message for 'Facturado'."""
        from ct.tools.status import status_tool
        
        # Setup
        mock_pedidos.find_one.return_value = {
            "estatus": {"Facturado": {"folioFactura": "FAC-001"}},
            "pedido": {"encabezado": {}, "detalle": {"producto": []}}
        }
        
        # Execute
        result = status_tool.func("FAC-001", runtime=mock_runtime)
        
        # Assert
        assert "factura" in result.lower()
        assert "generada" in result.lower()
    
    @patch("ct.tools.status.pedidos")
    def test_status_enviado(self, mock_pedidos, mock_runtime):
        """Test status message for 'Enviado'."""
        from ct.tools.status import status_tool
        
        # Setup
        mock_pedidos.find_one.return_value = {
            "estatus": {"Enviado": {}},
            "pedido": {"encabezado": {}, "detalle": {"producto": []}}
        }
        
        # Execute
        result = status_tool.func("FAC-001", runtime=mock_runtime)
        
        # Assert
        assert "guía" in result.lower()
        assert "generada" in result.lower()
    
    @patch("ct.tools.status.descargas_enviadas")
    @patch("ct.tools.status.pedidos")
    def test_status_terminado(self, mock_pedidos, mock_descargas, mock_runtime):
        """Test status message for 'Terminado' with ESD products."""
        from ct.tools.status import status_tool
        
        # Setup
        mock_pedidos.find_one.return_value = {
            "estatus": {"Terminado": {}},
            "pedido": {
                "encabezado": {},
                "detalle": {
                    "producto": [
                        {"cantidad": 2},
                        {"cantidad": 3}
                    ]
                }
            }
        }
        mock_descargas.return_value = 2
        
        # Execute
        result = status_tool.func("FAC-001", runtime=mock_runtime)
        
        # Assert
        assert "ESD totales: 5" in result
        assert "total de descargas enviadas: 2" in result
    
    @patch("ct.tools.status.descargas_enviadas")
    @patch("ct.tools.status.pedidos")
    def test_status_factura_esd_actualizada(self, mock_pedidos, mock_descargas, mock_runtime):
        """Test status message for 'FacturaESDActualizada'."""
        from ct.tools.status import status_tool
        
        # Setup
        mock_pedidos.find_one.return_value = {
            "estatus": {"FacturaESDActualizada": {}},
            "pedido": {
                "encabezado": {},
                "detalle": {
                    "producto": [{"cantidad": 1}]
                }
            }
        }
        mock_descargas.return_value = 1
        
        # Execute
        result = status_tool.func("FAC-001", runtime=mock_runtime)
        
        # Assert
        assert "ESD totales: 1" in result
    
    @patch("ct.tools.status.pedidos")
    def test_status_preautorizado(self, mock_pedidos, mock_runtime):
        """Test status message for 'Preautorizado'."""
        from ct.tools.status import status_tool
        
        # Setup
        mock_pedidos.find_one.return_value = {
            "estatus": {"Preautorizado": {}},
            "pedido": {"encabezado": {}, "detalle": {"producto": []}}
        }
        
        # Execute
        result = status_tool.func("FAC-001", runtime=mock_runtime)
        
        # Assert
        assert "Procesando tu pedido" in result
    
    @patch("ct.tools.status.pedidos")
    def test_status_autorizado(self, mock_pedidos, mock_runtime):
        """Test status message for 'Autorizado'."""
        from ct.tools.status import status_tool
        
        # Setup
        mock_pedidos.find_one.return_value = {
            "estatus": {"Autorizado": {}},
            "pedido": {"encabezado": {}, "detalle": {"producto": []}}
        }
        
        # Execute
        result = status_tool.func("FAC-001", runtime=mock_runtime)
        
        # Assert
        assert "Procesando tu pedido" in result
    
    @patch("ct.tools.status.pedidos")
    def test_status_transito(self, mock_pedidos, mock_runtime):
        """Test status message for 'Transito' with timezone conversion."""
        from ct.tools.status import status_tool
        
        # Setup - UTC time
        utc_time = datetime(2024, 1, 15, 12, 30, 0)
        
        mock_pedidos.find_one.return_value = {
            "estatus": {
                "Transito": {
                    "fecha": utc_time
                }
            },
            "pedido": {"encabezado": {}, "detalle": {"producto": []}}
        }
        
        # Execute
        result = status_tool.func("FAC-001", runtime=mock_runtime)
        
        # Assert
        assert "salió en movimiento" in result
        assert "15 de enero del 2024" in result or "15 de enero de 2024" in result
        assert "horario Ciudad de México" in result
    
    @patch("ct.tools.status.pedidos")
    def test_status_entregado(self, mock_pedidos, mock_runtime):
        """Test status message for 'Entregado'."""
        from ct.tools.status import status_tool
        
        # Setup
        mock_pedidos.find_one.return_value = {
            "estatus": {"Entregado": {}},
            "pedido": {"encabezado": {}, "detalle": {"producto": []}}
        }
        
        # Execute
        result = status_tool.func("FAC-001", runtime=mock_runtime)
        
        # Assert
        assert result == "Pedido entregado al domicilio"
    
    @patch("ct.tools.status.pedidos")
    def test_status_rechazado(self, mock_pedidos, mock_runtime):
        """Test status message for 'Rechazado'."""
        from ct.tools.status import status_tool
        
        # Setup
        mock_pedidos.find_one.return_value = {
            "estatus": {"Rechazado": {}},
            "pedido": {"encabezado": {}, "detalle": {"producto": []}}
        }
        
        # Execute
        result = status_tool.func("FAC-001", runtime=mock_runtime)
        
        # Assert
        assert "revisando tu pedido" in result
        assert "gracias por la paciencia" in result.lower()
    
    @patch("ct.tools.status.pedidos")
    def test_status_cancelado(self, mock_pedidos, mock_runtime):
        """Test status message for 'Cancelado'."""
        from ct.tools.status import status_tool
        
        # Setup
        mock_pedidos.find_one.return_value = {
            "estatus": {"Cancelado": {}},
            "pedido": {"encabezado": {}, "detalle": {"producto": []}}
        }
        
        # Execute
        result = status_tool.func("FAC-001", runtime=mock_runtime)
        
        # Assert
        assert result == "El pedido ha sido cancelado"
    
    @patch("ct.tools.status.pedidos")
    def test_status_unknown_status(self, mock_pedidos, mock_runtime):
        """Test message for unknown status."""
        from ct.tools.status import status_tool
        
        # Setup
        mock_pedidos.find_one.return_value = {
            "estatus": {"UnknownStatus": {}},
            "pedido": {"encabezado": {}, "detalle": {"producto": []}}
        }
        
        # Execute
        result = status_tool.func("FAC-001", runtime=mock_runtime)
        
        # Assert
        assert result == "Estamos trabajando en su pedido"
