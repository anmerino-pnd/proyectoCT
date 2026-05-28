"""
Tests for settings configuration module.

These tests verify that the configuration module correctly:
- Resolves project paths
- Creates necessary directories
- Handles edge cases
"""

from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.mark.unit
class TestConfigPaths:
    """Tests for configuration path resolution."""
    
    def test_find_project_root_finds_pyproject_toml(self, project_root: Path):
        """Test that project root is correctly identified by pyproject.toml."""
        from ct.settings.config import find_project_root
        
        # Test with current file location
        result = find_project_root(Path(__file__))
        
        # Should find the project root containing pyproject.toml
        assert result.exists()
        assert (result / "pyproject.toml").exists()
        assert result == project_root
    
    def test_find_project_root_with_custom_marker(self, tmp_path: Path):
        """Test finding project root with custom marker file."""
        from ct.settings.config import find_project_root
        
        # Create a temporary structure
        marker_file = "custom_marker.txt"
        (tmp_path / marker_file).touch()
        nested_dir = tmp_path / "a" / "b" / "c"
        nested_dir.mkdir(parents=True)
        
        # Should find root with custom marker
        result = find_project_root(nested_dir, marker_file=marker_file)
        assert result == tmp_path
    
    def test_find_project_root_stops_at_root(self, tmp_path: Path):
        """Test that search stops at filesystem root if marker not found."""
        from ct.settings.config import find_project_root
        
        # Start from a temp directory without marker
        result = find_project_root(tmp_path, marker_file="nonexistent.marker")
        
        # Should return the start path when marker not found
        # (as the loop stops when current == current.parent)
        assert result == Path(tmp_path.anchor)


@pytest.mark.unit
class TestBaseDir:
    """Tests for BASE_DIR configuration."""
    
    def test_base_dir_exists(self):
        """Test that BASE_DIR is defined and exists."""
        from ct.settings.config import BASE_DIR
        
        assert BASE_DIR is not None
        assert BASE_DIR.exists()
        assert BASE_DIR.is_dir()
    
    def test_base_dir_contains_pyproject(self):
        """Test that BASE_DIR contains pyproject.toml."""
        from ct.settings.config import BASE_DIR
        
        assert (BASE_DIR / "pyproject.toml").exists()


@pytest.mark.unit
class TestDataPaths:
    """Tests for data directory paths."""
    
    def test_data_dir_is_path(self):
        """Test that DATA_DIR is a Path object."""
        from ct.settings.config import DATA_DIR
        
        assert isinstance(DATA_DIR, Path)
    
    def test_data_dir_relative_to_base(self):
        """Test that DATA_DIR is relative to BASE_DIR."""
        from ct.settings.config import BASE_DIR, DATA_DIR
        
        expected = BASE_DIR / "datos"
        assert DATA_DIR == expected
    
    def test_vectors_dir_defined(self):
        """Test that vectors directory is defined."""
        from ct.settings.config import VECTORS_DIR
        
        assert VECTORS_DIR is not None
        assert "vectorstores" in str(VECTORS_DIR)
    
    def test_product_vector_path_defined(self):
        """Test that product vector store path is defined."""
        from ct.settings.config import PRODUCTS_VECTOR_PATH
        
        assert PRODUCTS_VECTOR_PATH is not None
        assert "products" in str(PRODUCTS_VECTOR_PATH).lower()
    
    def test_sales_vector_path_defined(self):
        """Test that sales vector store path is defined."""
        from ct.settings.config import SALES_VECTOR_PATH
        
        assert SALES_VECTOR_PATH is not None
        assert "sales" in str(SALES_VECTOR_PATH).lower()


@pytest.mark.unit
class TestKnowledgeBasePaths:
    """Tests for knowledge base paths."""
    
    def test_base_knowledge_defined(self):
        """Test that base knowledge path is defined."""
        from ct.settings.config import BASE_KNOWLEDGE
        
        assert BASE_KNOWLEDGE is not None
        assert "base_de_conocimientos" in str(BASE_KNOWLEDGE)
    
    def test_partner_ct_path_defined(self):
        """Test that Partner CT path is defined."""
        from ct.settings.config import PARTNER_CT
        
        assert PARTNER_CT is not None
        assert "partnerCT" in str(PARTNER_CT)
    
    def test_ct_connect_path_defined(self):
        """Test that CT Connect path is defined."""
        from ct.settings.config import CT_CONNECT
        
        assert CT_CONNECT is not None
        assert "CTConnect" in str(CT_CONNECT)
    
    def test_ct_cloud_path_defined(self):
        """Test that CT Cloud path is defined."""
        from ct.settings.config import CT_CLOUD
        
        assert CT_CLOUD is not None
        assert "CTCloud" in str(CT_CLOUD)


@pytest.mark.unit
class TestDirectoryCreation:
    """Tests for automatic directory creation."""
    
    @patch("ct.settings.config.Path.mkdir")
    def test_directories_created_with_mkdir(self, mock_mkdir):
        """Test that directories are created using mkdir."""
        # Re-import to trigger the mkdir calls
        import importlib
        import ct.settings.config as config_module
        
        importlib.reload(config_module)
        
        # Verify mkdir was called for each directory
        assert mock_mkdir.called
        # Should be called with parents=True, exist_ok=True
        for call in mock_mkdir.call_args_list:
            args, kwargs = call
            assert kwargs.get("parents") is True
            assert kwargs.get("exist_ok") is True


@pytest.mark.unit
class TestPathConsistency:
    """Tests for path consistency across the configuration."""
    
    def test_all_paths_under_base_dir(self):
        """Test that all defined paths are under BASE_DIR."""
        from ct.settings.config import (
            BASE_DIR,
            DATA_DIR,
            VECTORS_DIR,
            PRODUCTS_VECTOR_PATH,
            SALES_VECTOR_PATH,
            BASE_KNOWLEDGE,
            PARTNER_CT,
            CT_CONNECT,
            CT_CLOUD,
        )
        
        paths_to_check = [
            DATA_DIR,
            VECTORS_DIR,
            PRODUCTS_VECTOR_PATH,
            SALES_VECTOR_PATH,
            BASE_KNOWLEDGE,
            PARTNER_CT,
            CT_CONNECT,
            CT_CLOUD,
        ]
        
        for path in paths_to_check:
            # Path should be under BASE_DIR
            assert str(path).startswith(str(BASE_DIR)), f"{path} is not under BASE_DIR"
