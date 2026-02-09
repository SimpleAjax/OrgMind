# OrgMind

> Context Graph Platform for Organizational Intelligence

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- [uv](https://docs.astral.sh/uv/) (Python package manager)

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/your-org/orgmind.git
cd orgmind

# 2. Copy environment variables
cp .env.example .env

# 3. Start Docker services
make up

# 4. Install Python dependencies
make dev

# 5. Run database migrations
make migrate

# 6. Start the API server
make run
```

### Verify Setup

```bash
# Check API health
curl http://localhost:8000/health/ready

# Open API docs
open http://localhost:8000/docs
```

### Available Services

| Service | URL | Purpose |
|---------|-----|---------|
| API | http://localhost:8000 | Main REST API |
| API Docs | http://localhost:8000/docs | Swagger UI |
| Neo4j Browser | http://localhost:7474 | Graph database UI |
| MinIO Console | http://localhost:9001 | Object storage UI |
| Temporal UI | http://localhost:8080 | Workflow monitoring |
| Meilisearch | http://localhost:7700 | Search dashboard |

## Development Commands

```bash
# Run tests
make test

# Lint and format code
make format
make lint

# Run all checks
make check

# View Docker logs
make logs

# Stop all services
make down

# Clean everything (including volumes)
make clean
```

## Project Structure

```
orgmind/
├── src/orgmind/
│   ├── api/          # FastAPI REST endpoints
│   ├── engine/       # Ontology Engine (schema, objects, links)
│   ├── storage/      # Database adapters
│   ├── events/       # Event Bus (Redis pub/sub)
│   ├── triggers/     # Trigger Engine (rules, reactions)
│   ├── workflows/    # Workflow Engine (Temporal)
│   ├── agents/       # Agent System (LLM, tools, memory)
│   └── platform/     # Cross-cutting concerns
├── tests/
│   ├── unit/         # Unit tests
│   └── integration/  # Integration tests
├── docker/           # Dockerfiles
├── private/context/  # Documentation & planning
└── .github/workflows/  # CI/CD pipelines
```

## Documentation

- [Execution Plan](private/context/execution-plan.md)
- [Component TRDs](private/context/orgmind-components/)

## License

Proprietary - All rights reserved
