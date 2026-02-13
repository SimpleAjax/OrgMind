from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session, scoped_session
from typing import Generator
from contextlib import contextmanager
import logging

from pydantic import SecretStr
from pydantic_settings import BaseSettings
from .base import StorageAdapter

logger = logging.getLogger(__name__)

class PostgresConfig(BaseSettings):
    """Configuration for Postgres Storage."""
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: SecretStr = "postgres"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "orgmind"
    POSTGRES_POOL_SIZE: int = 5
    POSTGRES_MAX_OVERFLOW: int = 10
    
    model_config = {"env_file": ".env", "extra": "ignore"}
    
    @property
    def connection_string(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD.get_secret_value()}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

class PostgresAdapter(StorageAdapter):
    """
    SQLAlchemy-based Postgres adapter.
    """
    
    def __init__(self, config: PostgresConfig):
        self.config = config
        self._engine = None
        self._session_factory = None
        
    def connect(self) -> None:
        if self._engine:
            return

        try:
            logger.info(f"Connecting to Postgres at {self.config.POSTGRES_HOST}:{self.config.POSTGRES_PORT}")
            
            self._engine = create_engine(
                self.config.connection_string,
                pool_size=self.config.POSTGRES_POOL_SIZE,
                max_overflow=self.config.POSTGRES_MAX_OVERFLOW,
                pool_pre_ping=True
            )
            
            self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False)
            logger.info("Postgres connection pool established.")
            
        except Exception as e:
            logger.error(f"Failed to connect to Postgres: {e}")
            raise

    def close(self) -> None:
        if self._engine:
            self._engine.dispose()
            self._engine = None
            logger.info("Postgres connection pool closed.")

    def health_check(self) -> bool:
        if not self._engine:
            return False
        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.exception("postgres unhealthy")
            return False

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Provide a transactional scope around a series of operations.
        """
        if not self._session_factory:
            raise ConnectionError("Postgres is not connected. Call connect() first.")
            
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def create_database_if_not_exists(self):
        """Helper for local dev setup."""
        temp_engine = create_engine(
            self.config.connection_string.rsplit('/', 1)[0] + '/postgres'
        )
        with temp_engine.connect() as conn:
            conn.execution_options(isolation_level="AUTOCOMMIT")
            result = conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname='{self.config.POSTGRES_DB}'"))
            if not result.fetchone():
                conn.execute(text(f"CREATE DATABASE {self.config.POSTGRES_DB}"))
                logger.info(f"Database {self.config.POSTGRES_DB} created.")
        temp_engine.dispose()
