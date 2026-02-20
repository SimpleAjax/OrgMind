"""
Base Scheduler class for Project Management schedulers.

Provides common functionality for database access, logging, and error handling.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from contextlib import contextmanager

from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_, func

# Import OrgMind storage components
try:
    from orgmind.storage.postgres_adapter import PostgresAdapter
    from orgmind.storage.models import ObjectModel, LinkModel
    from orgmind.graph.neo4j_adapter import Neo4jAdapter
    ORGMIND_AVAILABLE = True
except ImportError:
    ORGMIND_AVAILABLE = False
    # Fallback for standalone testing
    PostgresAdapter = Any
    Neo4jAdapter = Any


logger = logging.getLogger(__name__)


class SchedulerBase(ABC):
    """
    Base class for all PM schedulers.
    
    Provides:
    - Database access (PostgreSQL for relational data)
    - Graph database access (Neo4j for dependency analysis)
    - Common utility methods
    - Error handling and logging
    """
    
    def __init__(
        self,
        db_adapter: Optional[PostgresAdapter] = None,
        neo4j_adapter: Optional[Neo4jAdapter] = None,
    ):
        """
        Initialize the scheduler.
        
        Args:
            db_adapter: PostgreSQL adapter for relational queries
            neo4j_adapter: Neo4j adapter for graph queries
        """
        self.db = db_adapter
        self.neo4j = neo4j_adapter
        self.logger = logging.getLogger(self.__class__.__name__)
        
    @contextmanager
    def get_session(self) -> Session:
        """Get a database session context."""
        if self.db is None:
            raise RuntimeError("Database adapter not configured")
        with self.db.get_session() as session:
            yield session
            
    def get_objects_by_type(
        self, 
        session: Session, 
        type_id: str, 
        status: Optional[str] = None,
        limit: int = 1000
    ) -> List[ObjectModel]:
        """
        Get objects by type with optional status filter.
        
        Args:
            session: Database session
            type_id: Object type ID (e.g., 'ot_project')
            status: Optional status filter
            limit: Maximum number of results
            
        Returns:
            List of ObjectModel instances
        """
        stmt = select(ObjectModel).where(
            and_(
                ObjectModel.type_id == type_id,
                ObjectModel.status != 'deleted'
            )
        ).limit(limit)
        
        if status:
            stmt = stmt.where(ObjectModel.status == status)
            
        return list(session.scalars(stmt).all())
    
    def get_object_by_id(self, session: Session, object_id: str) -> Optional[ObjectModel]:
        """Get a single object by ID."""
        return session.get(ObjectModel, object_id)
    
    def update_object_data(
        self, 
        session: Session, 
        object_id: str, 
        data_updates: Dict[str, Any]
    ) -> Optional[ObjectModel]:
        """
        Update object data (merges with existing data).
        
        Args:
            session: Database session
            object_id: Object ID to update
            data_updates: Dictionary of data fields to update
            
        Returns:
            Updated ObjectModel or None if not found
        """
        obj = self.get_object_by_id(session, object_id)
        if not obj:
            return None
            
        # Merge data
        new_data = obj.data.copy()
        new_data.update(data_updates)
        obj.data = new_data
        obj.version += 1
        
        return obj
    
    def get_linked_objects(
        self,
        session: Session,
        source_id: str,
        link_type_id: Optional[str] = None,
        target_type_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get objects linked to a source object.
        
        Args:
            session: Database session
            source_id: Source object ID
            link_type_id: Optional link type filter
            target_type_id: Optional target object type filter
            
        Returns:
            List of dictionaries with 'object' and 'link_data' keys
        """
        stmt = select(LinkModel, ObjectModel).join(
            ObjectModel, LinkModel.target_id == ObjectModel.id
        ).where(
            and_(
                LinkModel.source_id == source_id,
                ObjectModel.status != 'deleted'
            )
        )
        
        if link_type_id:
            stmt = stmt.where(LinkModel.type_id == link_type_id)
        if target_type_id:
            stmt = stmt.where(ObjectModel.type_id == target_type_id)
            
        results = session.execute(stmt).all()
        
        return [
            {
                'object': obj,
                'link_data': link.data if link.data else {}
            }
            for link, obj in results
        ]
    
    def execute_neo4j_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a Neo4j Cypher query.
        
        Args:
            query: Cypher query string
            parameters: Query parameters
            
        Returns:
            Query results as list of dictionaries
        """
        if not self.neo4j:
            raise RuntimeError("Neo4j adapter not configured")
            
        return self.neo4j.execute_read(query, parameters or {})
    
    def now(self) -> datetime:
        """Get current UTC datetime."""
        return datetime.utcnow()
    
    def days_until(self, target_date: datetime) -> int:
        """Calculate days until a target date."""
        if not target_date:
            return 999  # Far future if no date
        delta = target_date - self.now()
        return max(0, delta.days)
    
    def normalize_score(
        self, 
        value: float, 
        min_val: float, 
        max_val: float, 
        invert: bool = False
    ) -> float:
        """
        Normalize a value to 0-100 scale.
        
        Args:
            value: The value to normalize
            min_val: Minimum expected value
            max_val: Maximum expected value
            invert: If True, higher input values produce lower scores
            
        Returns:
            Normalized score 0-100
        """
        if max_val == min_val:
            return 50.0
            
        normalized = (value - min_val) / (max_val - min_val)
        normalized = max(0.0, min(1.0, normalized))
        
        if invert:
            normalized = 1.0 - normalized
            
        return normalized * 100.0
    
    @abstractmethod
    async def run(self, *args, **kwargs) -> Any:
        """
        Main entry point for the scheduler.
        
        Must be implemented by subclasses.
        """
        pass
