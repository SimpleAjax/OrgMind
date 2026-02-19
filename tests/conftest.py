"""
Pytest configuration and shared fixtures.
"""

import os
import sys
import pytest

sys.path.append(os.path.join(os.getcwd(), "src"))


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment() -> None:
    """Set up test environment variables."""
    os.environ.setdefault("APP_ENV", "test")
    os.environ.setdefault("DEBUG", "true")
    os.environ.setdefault("DUCKDB_PATH", "data/test.duckdb")
    os.environ.setdefault("JWT_SECRET", "test-secret-key")


@pytest.fixture
def test_data_dir(tmp_path) -> str:
    """Create a temporary data directory for tests."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return str(data_dir)
