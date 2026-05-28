"""
Tests for support information tool.

These tests verify that the get_support_info correctly:
- Loads FAISS vector store
- Creates retrievers with filters
- Searches documentation
- Handles special Directorio PM formatting
- Returns combined context from multiple filters
"""

from unittest.mock import MagicMock, patch, PropertyMock

import pytest


@pytest.mark.unit
class TestGetFaissRetriever:
    """Tests for get_faiss_retriever function."""
    
    @patch("ct.tools.support.vector_store")
    def test_retriever_created_with_similarity_search(self, mock_vector_store):
        """Test that retriever is created with similarity search."""
        from ct.tools.support import get_faiss_retriever
        
        # Setup
        mock_retriever = MagicMock()
        mock_vector_store.as_retriever.return_value = mock_retriever
        
        # Execute
        result = get_faiss_retriever("Compra en línea")
        
        # Assert
        mock_vector_store.as_retriever.assert_called_once()
        call_kwargs = mock_vector_store.as_retriever.call_args[1]
        assert call_kwargs["search_type"] == "similarity"
        assert call_kwargs["search_kwargs"]["k"] == 15
        assert call_kwargs["search_kwargs"]["filter"]["collection"] == "Compra en línea"
    
    @patch("ct.tools.support.vector_store")
    def test_retriever_with_different_filters(self, mock_vector_store):
        """Test retriever creation with different filter values."""
        from ct.tools.support import get_faiss_retriever
        
        # Setup
        mock_retriever = MagicMock()
        mock_vector_store.as_retriever.return_value = mock_retriever
        
        # Test various filters
        filters = [
            "Compra en línea",
            "ESD",
            "Terminos, condiciones y políticas",
            "PartnerCT",
            "CT Cloud",
        ]
        
        for filter_value in filters:
            mock_vector_store.as_retriever.reset_mock()
            get_faiss_retriever(filter_value)
            
            call_kwargs = mock_vector_store.as_retriever.call_args[1]
            assert call_kwargs["search_kwargs"]["filter"]["collection"] == filter_value


@pytest.mark.unit
class TestGetSupportInfo:
    """Tests for get_support_info function."""
    
    @patch("ct.tools.support.get_faiss_retriever")
    def test_single_filter_search(self, mock_get_retriever):
        """Test search with single filter."""
        from ct.tools.support import get_support_info
        
        # Setup
        mock_retriever = MagicMock()
        mock_doc = MagicMock()
        mock_doc.page_content = "Información sobre compras en línea"
        mock_retriever.invoke.return_value = [mock_doc]
        mock_get_retriever.return_value = mock_retriever
        
        # Execute
        result = get_support_info("¿Cómo compro en línea?", filters=["Compra en línea"])
        
        # Assert
        mock_get_retriever.assert_called_once_with(collection_filter="Compra en línea")
        mock_retriever.invoke.assert_called_once_with("¿Cómo compro en línea?")
        assert "Compra en línea" in result
        assert "Información sobre compras en línea" in result
    
    @patch("ct.tools.support.get_faiss_retriever")
    def test_multiple_filters_search(self, mock_get_retriever):
        """Test search with multiple filters."""
        from ct.tools.support import get_support_info
        
        # Setup
        mock_retriever = MagicMock()
        mock_doc1 = MagicMock()
        mock_doc1.page_content = "Info sobre compras"
        mock_doc2 = MagicMock()
        mock_doc2.page_content = "Info sobre ESD"
        
        mock_retriever.invoke.side_effect = [[mock_doc1], [mock_doc2]]
        mock_get_retriever.return_value = mock_retriever
        
        # Execute
        result = get_support_info(
            "información general",
            filters=["Compra en línea", "ESD"]
        )
        
        # Assert
        assert mock_get_retriever.call_count == 2
        assert "Compra en línea" in result
        assert "ESD" in result
        assert "Info sobre compras" in result
        assert "Info sobre ESD" in result
    
    @patch("ct.tools.support.get_faiss_retriever")
    def test_directorio_pm_special_formatting(self, mock_get_retriever):
        """Test special formatting for Directorio PM filter."""
        from ct.tools.support import get_support_info
        
        # Setup
        mock_retriever = MagicMock()
        mock_doc = MagicMock()
        mock_doc.page_content = "Gerente de Ventas"
        mock_doc.metadata = {
            "coordinador": "Juan Pérez",
            "correo": "juan@ct.com",
            "teams": "juan.perez",
            "extension": "1234"
        }
        mock_retriever.invoke.return_value = [mock_doc]
        mock_get_retriever.return_value = mock_retriever
        
        # Execute
        result = get_support_info(
            "¿Quién es el gerente?",
            filters=["Directorio PM"]
        )
        
        # Assert
        assert "Coordinador(a) responsable" in result
        assert "Juan Pérez" in result
        assert "juan@ct.com" in result
        assert "juan.perez" in result
        assert "1234" in result
    
    @patch("ct.tools.support.get_faiss_retriever")
    def test_empty_results_returns_message(self, mock_get_retriever):
        """Test message when no results found."""
        from ct.tools.support import get_support_info
        
        # Setup
        mock_retriever = MagicMock()
        mock_retriever.invoke.return_value = []
        mock_get_retriever.return_value = mock_retriever
        
        # Execute
        result = get_support_info("consulta", filters=["Compra en línea"])
        
        # Assert
        assert "No se encontró información relevante" in result
    
    @patch("ct.tools.support.get_faiss_retriever")
    def test_filter_error_handling(self, mock_get_retriever):
        """Test error handling when filter fails."""
        from ct.tools.support import get_support_info
        
        # Setup - first filter fails, second succeeds
        def side_effect(collection_filter):
            if collection_filter == "ESD":
                raise Exception("FAISS error")
            mock_retriever = MagicMock()
            mock_doc = MagicMock()
            mock_doc.page_content = "Info válida"
            mock_retriever.invoke.return_value = [mock_doc]
            return mock_retriever
        
        mock_get_retriever.side_effect = side_effect
        
        # Execute - should continue with other filters
        result = get_support_info(
            "consulta",
            filters=["ESD", "Compra en línea"]
        )
        
        # Assert - should have results from working filter
        assert "Compra en línea" in result
    
    @patch("ct.tools.support.get_faiss_retriever")
    def test_all_filters_fail(self, mock_get_retriever):
        """Test when all filters fail."""
        from ct.tools.support import get_support_info
        
        # Setup - all filters fail
        mock_get_retriever.side_effect = Exception("FAISS error")
        
        # Execute
        result = get_support_info(
            "consulta",
            filters=["ESD", "Compra en línea"]
        )
        
        # Assert
        assert "No se encontró información relevante" in result
    
    @patch("ct.tools.support.get_faiss_retriever")
    def test_context_separation_between_filters(self, mock_get_retriever):
        """Test that context from different filters is properly separated."""
        from ct.tools.support import get_support_info
        
        # Setup
        mock_retriever1 = MagicMock()
        mock_doc1 = MagicMock()
        mock_doc1.page_content = "Contenido 1"
        mock_retriever1.invoke.return_value = [mock_doc1]
        
        mock_retriever2 = MagicMock()
        mock_doc2 = MagicMock()
        mock_doc2.page_content = "Contenido 2"
        mock_retriever2.invoke.return_value = [mock_doc2]
        
        mock_get_retriever.side_effect = [mock_retriever1, mock_retriever2]
        
        # Execute
        result = get_support_info(
            "consulta",
            filters=["Compra en línea", "ESD"]
        )
        
        # Assert - should have separators
        assert "--- Información sobre: Compra en línea ---" in result
        assert "--- Información sobre: ESD ---" in result
    
    def test_support_input_model(self):
        """Test that SupportInput model accepts valid filters."""
        from ct.tools.support import SupportInput
        
        # Valid filters
        valid_filters = [
            "Compra en línea",
            "ESD",
            "Terminos, condiciones y políticas",
            "Procedimientos Garantía",
            "PartnerCT",
            "Directorio PM",
            "CT Connect",
            "CT Arrendamiento",
            "CT Cloud",
            "Docusmart",
        ]
        
        for filter_value in valid_filters:
            # Should not raise
            input_data = SupportInput(query="test", filters=[filter_value])
            assert input_data.query == "test"
            assert filter_value in input_data.filters


@pytest.mark.unit
class TestSupportFilters:
    """Tests for supported filter types."""
    
    def test_all_filter_types_defined(self):
        """Test that all expected filter types are defined."""
        from ct.tools.support import SupportFilter
        
        # Get the allowed values from the Literal type
        # SupportFilter is a type alias, we check what values it accepts
        expected_filters = [
            "Compra en línea",
            "ESD",
            "Terminos, condiciones y políticas",
            "Procedimientos Garantía",
            "PartnerCT",
            "Directorio PM",
            "CT Connect",
            "CT Arrendamiento",
            "CT Cloud",
            "Docusmart",
        ]
        
        # Verify SupportInput accepts these values
        from ct.tools.support import SupportInput
        
        for filter_val in expected_filters:
            try:
                SupportInput(query="test", filters=[filter_val])
            except Exception:
                pytest.fail(f"Filter '{filter_val}' should be valid")
