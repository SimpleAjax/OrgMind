"""
Neo4j Adapter - Graph database adapter for the Ontology Engine.

This adapter provides a clean interface for interacting with Neo4j
for storing and querying the organizational context graph.
"""

from typing import Dict, List, Optional, Any
from contextlib import contextmanager
import logging

from neo4j import GraphDatabase, Driver, Session
from neo4j.exceptions import Neo4jError


logger = logging.getLogger(__name__)


class Neo4jAdapter:
    """
    Adapter for Neo4j graph database operations.
    
    This adapter handles:
    - Connection management
    - Cypher query execution
    - Transaction management
    - Error handling
    """
    
    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        username: str = "neo4j",
        password: str = "orgmind_dev",
    ):
        """
        Initialize Neo4j connection.
        
        Args:
            uri: Neo4j connection URI
            username: Database username
            password: Database password
        """
        self.uri = uri
        self.username = username
        self.password = password
        self._driver: Optional[Driver] = None
        
    def connect(self) -> None:
        """Establish connection to Neo4j database."""
        try:
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password),
            )
            # Verify connectivity
            self._driver.verify_connectivity()
            logger.info(f"Connected to Neo4j at {self.uri}")
        except Neo4jError as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise
    
    def disconnect(self) -> None:
        """Close connection to Neo4j database."""
        if self._driver:
            self._driver.close()
            self._driver = None
            logger.info("Disconnected from Neo4j")
    
    @contextmanager
    def session(self, database: str = "neo4j"):
        """
        Context manager for Neo4j sessions.
        
        Args:
            database: Database name (default: "neo4j")
            
        Yields:
            Neo4j Session object
        """
        if not self._driver:
            raise RuntimeError("Not connected to Neo4j. Call connect() first.")
        
        session = self._driver.session(database=database)
        try:
            yield session
        finally:
            session.close()
    
    def execute_write(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute a write query (CREATE, MERGE, SET, DELETE).
        
        Args:
            query: Cypher query to execute
            parameters: Query parameters
            
        Returns:
            List of records as dictionaries
        """
        with self.session() as session:
            try:
                result = session.run(query, parameters or {})
                return [dict(record) for record in result]
            except Neo4jError as e:
                logger.error(f"Write query failed: {e}\nQuery: {query}\nParams: {parameters}")
                raise
    
    def execute_read(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute a read query (MATCH, RETURN).
        
        Args:
            query: Cypher query to execute
            parameters: Query parameters
            
        Returns:
            List of records as dictionaries
        """
        with self.session() as session:
            try:
                result = session.run(query, parameters or {})
                return [dict(record) for record in result]
            except Neo4jError as e:
                logger.error(f"Read query failed: {e}\nQuery: {query}\nParams: {parameters}")
                raise
    
    def create_indexes(self) -> None:
        """Create indexes for optimal query performance."""
        indexes = [
            # Object node indexes
            "CREATE INDEX object_id IF NOT EXISTS FOR (o:Object) ON (o.id)",
            "CREATE INDEX object_type IF NOT EXISTS FOR (o:Object) ON (o.type_id)",
            "CREATE INDEX object_tenant IF NOT EXISTS FOR (o:Object) ON (o.tenant_id)",
            
            # Composite index for tenant-scoped queries
            "CREATE INDEX object_tenant_type IF NOT EXISTS FOR (o:Object) ON (o.tenant_id, o.type_id)",
        ]
        
        for index_query in indexes:
            try:
                self.execute_write(index_query)
                logger.info(f"Created index: {index_query}")
            except Neo4jError as e:
                # Ignore errors if index already exists
                logger.debug(f"Index creation skipped: {e}")
    
    def health_check(self) -> bool:
        """
        Check if Neo4j is healthy and accessible.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            if not self._driver:
                return False
            
            with self.session() as session:
                result = session.run("RETURN 1 AS health")
                record = result.single()
                return record and record["health"] == 1
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def clear_database(self) -> None:
        """
        Clear all nodes and relationships from the database.
        
        WARNING: This is destructive and should only be used in tests!
        """
        logger.warning("Clearing Neo4j database - this will delete ALL data!")
        self.execute_write("MATCH (n) DETACH DELETE n")
        logger.info("Neo4j database cleared")
    
    def get_node_count(self) -> int:
        """Get total count of nodes in the database."""
        result = self.execute_read("MATCH (n) RETURN count(n) AS count")
        return result[0]["count"] if result else 0
    
    def get_relationship_count(self) -> int:
        """Get total count of relationships in the database."""
        result = self.execute_read("MATCH ()-[r]->() RETURN count(r) AS count")
        return result[0]["count"] if result else 0
