"""Test configuration for Scribe."""
import pytest
from unittest.mock import MagicMock

@pytest.fixture
def mock_setup_entry():
    """Mock setup entry."""
    with pytest.mock.patch("custom_components.scribe.async_setup_entry", return_value=True) as mock_setup:
        yield mock_setup
