from typing import List, Dict, Any, Optional
import re
import structlog
from orgmind.graph.neo4j_adapter import Neo4jAdapter

logger = structlog.get_logger()

class ContextBuilder:
    def __init__(self, neo4j_adapter: Optional[Neo4jAdapter] = None):
        self.neo4j = neo4j_adapter or Neo4jAdapter()

    async def get_context(self, query: str, limit: int = 5) -> str:
        """
        Retrieve relevant context from the graph based on entities in the query.
        Returns a formatted string suitable for LLM context window.
        """
        entities = self._extract_entities(query)
        if not entities:
            return ""

        # Query graph for these entities
        params = {"names": entities, "limit": limit}
        cypher = """
        MATCH (n:Object) 
        WHERE n.name IN $names
        CALL {
            WITH n
            MATCH (n)-[r]-(m:Object)
            RETURN n.name as source, type(r) as relationship, m.name as target
            LIMIT $limit
        }
        RETURN source, relationship, target
        """
        
        try:
            # We assume Neo4j adapter handles async internally via run_in_executor or driver async methods?
            # Looking at adapter code, execute_read uses synchronous session.run.
            # So we might block here. Ideally adapter should be async.
            # For now, we call it directly (blocking).
            if not self.neo4j._driver:
                self.neo4j.connect()
                
            records = self.neo4j.execute_read(cypher, params)
            
            if not records:
                return ""
            
            # Format context
            context_lines = []
            for r in records:
                line = f"- {r['source']} {r['relationship']} {r['target']}"
                context_lines.append(line)
            
            return "Graph Context:\n" + "\n".join(context_lines)
            
        except Exception as e:
            logger.error("graph_context_retrieval_failed", error=str(e))
            return ""

    def _extract_entities(self, text: str) -> List[str]:
        """
        Naive entity extraction: find consecutive capitalized words.
        TODO: Replace with actual NER or LLM call.
        """
        # Exclude common stop words if needed, but regex handles basic capitalization
        # Pattern: Word starting with Upper, followed by lower/digits, optionally followed by space + same
        pattern = r'\b[A-Z][a-zA-Z0-9]*(?:\s+[A-Z][a-zA-Z0-9]*)*\b'
        matches = re.findall(pattern, text)
        
        # Filter out single words that might be start of sentence if query is simple?
        # For now, just return unique matches
        return list(set(matches))
