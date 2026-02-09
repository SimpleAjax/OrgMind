"""
OrgMind - Context Graph Platform for Organizational Intelligence

This package contains the core OrgMind backend services:
- api: FastAPI REST endpoints
- engine: Ontology Engine (schema, objects, links, actions)
- storage: Database adapters (DuckDB, Neo4j, Qdrant, Meilisearch, MinIO)
- events: Event Bus (Redis pub/sub)
- triggers: Trigger Engine (rules, conditions, reactions)
- workflows: Workflow Engine (Temporal integration)
- agents: Agent System (LLM, tools, memory)
- platform: Cross-cutting concerns (logging, metrics, notifications)
"""

__version__ = "0.1.0"
