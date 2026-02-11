from abc import ABC, abstractmethod
from typing import Generator
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
import logging

class StorageAdapter(ABC):
    """Abstract base class for storage adapters."""

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to the storage backend."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the connection."""
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Check if the backend is reachable."""
        pass
        
    @abstractmethod
    def get_session(self) -> Generator[Session, None, None]:
        """Provide a contextual session."""
        pass
