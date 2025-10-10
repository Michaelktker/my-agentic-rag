"""
Unit Tests for My Agentic RAG Application

This module contains unit tests for core application components.
Tests are organized by functionality and use pytest framework.

Run tests with:
    pytest tests/unit/test_core.py -v
"""

import pytest
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'app'))


class TestApplicationHealth:
    """Test basic application health and configuration."""
    
    def test_python_version(self):
        """Test that we're running a supported Python version."""
        assert sys.version_info >= (3, 9), "Python 3.9+ is required"
    
    def test_import_main_modules(self):
        """Test that main application modules can be imported."""
        try:
            import app.agent as agent_module
            import app.server as server_module
            assert agent_module is not None
            assert server_module is not None
        except ImportError as e:
            pytest.fail(f"Failed to import main modules: {e}")
    
    def test_environment_setup(self):
        """Test basic environment setup."""
        # This is a placeholder test - add actual environment checks as needed
        assert True, "Environment setup test passed"


class TestUtilities:
    """Test utility functions and helpers."""
    
    def test_basic_functionality(self):
        """Test basic functionality is working."""
        # Placeholder test - replace with actual utility tests
        assert 1 + 1 == 2, "Basic math should work"
    
    def test_string_operations(self):
        """Test string operations used in the application."""
        test_string = "Hello, World!"
        assert len(test_string) > 0
        assert test_string.lower() == "hello, world!"


@pytest.fixture
def sample_data():
    """Provide sample data for testing."""
    return {
        "user_id": "test_user_123",
        "session_id": "test_session_456",
        "message": "Hello, test!"
    }


class TestDataHandling:
    """Test data handling and processing functions."""
    
    def test_sample_data_structure(self, sample_data):
        """Test that sample data has expected structure."""
        assert "user_id" in sample_data
        assert "session_id" in sample_data
        assert "message" in sample_data
        assert isinstance(sample_data["user_id"], str)
        assert isinstance(sample_data["session_id"], str)
        assert isinstance(sample_data["message"], str)


if __name__ == "__main__":
    # Run tests when script is executed directly
    pytest.main([__file__, "-v"])