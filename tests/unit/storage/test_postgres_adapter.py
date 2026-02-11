import pytest
from unittest.mock import patch, MagicMock
from orgmind.storage.postgres_adapter import PostgresAdapter, PostgresConfig

@pytest.fixture
def mock_engine():
    with patch("orgmind.storage.postgres_adapter.create_engine") as mock:
        yield mock

def test_config_credentials():
    """Verify config loads correctly (mocking env vars)."""
    with patch.dict("os.environ", {
        "POSTGRES_USER": "testuser",
        "POSTGRES_PASSWORD": "testpassword",
        "POSTGRES_DB": "testdb"
    }):
        # Pydantic Settings reads from env
        config = PostgresConfig()
        assert config.POSTGRES_USER == "testuser"
        assert config.POSTGRES_PASSWORD.get_secret_value() == "testpassword"
        assert config.POSTGRES_DB == "testdb"
        assert "postgresql://testuser:testpassword@localhost:5432/testdb" == config.connection_string

def test_adapter_connect(mock_engine):
    """Verify adapter creates engine with correct URL."""
    config = PostgresConfig(POSTGRES_USER="user", POSTGRES_PASSWORD="pw", POSTGRES_DB="db")
    adapter = PostgresAdapter(config)
    adapter.connect()
    
    mock_engine.assert_called_once()
    args, kwargs = mock_engine.call_args
    assert "postgresql://user:pw@localhost:5432/db" == args[0]
    assert kwargs["pool_size"] == config.POSTGRES_POOL_SIZE

def test_adapter_session_context(mock_engine):
    """Verify session context manager commits on success."""
    config = PostgresConfig()
    adapter = PostgresAdapter(config)
    adapter.connect()
    
    # Mock session factory
    mock_session = MagicMock()
    adapter._session_factory = MagicMock(return_value=mock_session)
    
    with adapter.get_session() as session:
        session.add(MagicMock())
    
    mock_session.commit.assert_called_once()
    mock_session.close.assert_called_once()

def test_adapter_session_rollback(mock_engine):
    """Verify session rolls back on error."""
    config = PostgresConfig()
    adapter = PostgresAdapter(config)
    adapter.connect()
    
    mock_session = MagicMock()
    adapter._session_factory = MagicMock(return_value=mock_session)
    
    with pytest.raises(ValueError):
        with adapter.get_session() as session:
            raise ValueError("Boom")
            
    mock_session.rollback.assert_called_once()
    mock_session.close.assert_called_once()
