from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List, Dict, Any
from sqlalchemy.orm import Session

T = TypeVar("T")

class BaseRepository(Generic[T], ABC):
    """Abstract base repository defining CRUD contracts using SQLAlchemy Session."""

    def __init__(self, session_factory=None):
        # Optional factory, but methods below expect a valid Session object
        self.session_factory = session_factory

    @abstractmethod
    def create(self, session: Session, entity: Any) -> T:
        pass

    @abstractmethod
    def get(self, session: Session, id: str) -> Optional[T]:
        pass

    @abstractmethod
    def update(self, session: Session, id: str, updates: Dict[str, Any]) -> Optional[T]:
        pass

    @abstractmethod
    def delete(self, session: Session, id: str) -> bool:
        pass
        
    @abstractmethod
    def list(self, session: Session, limit: int = 100, offset: int = 0) -> List[T]:
        pass
