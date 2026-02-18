from typing import Generator
from sqlalchemy.orm import Session
from orgmind.storage.postgres_adapter import PostgresAdapter, PostgresConfig

# Singletons
_postgres_adapter: PostgresAdapter | None = None

def get_postgres_adapter() -> PostgresAdapter:
    global _postgres_adapter
    if not _postgres_adapter:
        config = PostgresConfig()
        _postgres_adapter = PostgresAdapter(config)
    return _postgres_adapter

def get_db() -> Generator[Session, None, None]:
    adapter = get_postgres_adapter()
    with adapter.get_session() as session:
        yield session

def close_postgres_adapter():
    global _postgres_adapter
    if _postgres_adapter:
        _postgres_adapter.close()
        _postgres_adapter = None
