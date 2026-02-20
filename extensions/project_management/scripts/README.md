# OrgMind PM Configuration Deployment

This directory contains scripts for deploying and managing the Project Management configuration on OrgMind.

## Prerequisites

1. **OrgMind Platform Running**
   ```bash
   make up  # Start all services
   ```

2. **Database Connection**
   - PostgreSQL must be accessible
   - Environment variables or `.env` file configured

3. **Python Dependencies**
   ```bash
   pip install pyyaml
   ```

## Quick Start

### Option 1: Full Deployment (Recommended for first time)

```bash
# From project root
cd extensions/project_management

# Load all configurations
python scripts/load_config.py --verify

# Expected output:
# ✅ Configuration loaded successfully!
# ✅ All verification tests passed!
```

### Option 2: Reset and Reload (DESTRUCTIVE)

Use this if you need to start fresh (deletes existing PM data):

```bash
python scripts/load_config.py --reset --verify
```

⚠️ **WARNING**: `--reset` will archive existing object types and delete link types.

### Option 3: Load Without Verification

```bash
python scripts/load_config.py
```

## What Gets Loaded

### 1. Object Types (15 entities)
Creates database tables for:
- Customers, Projects, Sprints, Tasks
- People, Skills, Assignments
- Leave tracking, Productivity profiles
- AI Nudges and Actions

### 2. Link Types (28 relationships)
Creates relationship definitions:
- Customer → Project
- Project → Task → Person
- Task dependencies (blocks)
- Skill requirements
- Sprint memberships

### 3. Triggers (25 rules)
Exports trigger definitions for:
- Event-driven reactions (task updates, leave approval)
- Scheduled jobs (priority calc, nudge generation)

**Note**: Triggers must be loaded separately via OrgMind's Trigger API after the export.

## Verification

The `--verify` flag runs these tests:

1. **Object Types Exist** - All 15 types created
2. **Link Types Exist** - All 28 relationships defined
3. **CRUD Operations** - Create, read, update, delete work
4. **Relationships** - Links between objects work

Run tests manually:
```bash
pytest extensions/project_management/tests/test_config_deployment.py -v
```

## Manual Steps After Deployment

### 1. Load Triggers via API

```bash
# Triggers are exported to:
cat extensions/project_management/config/triggers_export.json

# Load via OrgMind API
curl -X POST http://localhost:8000/api/v1/rules \
  -H "Content-Type: application/json" \
  -d @extensions/project_management/config/triggers_export.json
```

### 2. Verify API Endpoints

Test that APIs are auto-generated:

```bash
# List object types
curl http://localhost:8000/api/v1/types/objects

# List projects (empty at first)
curl http://localhost:8000/api/v1/objects?type_id=ot_project

# Create a test project
curl -X POST http://localhost:8000/api/v1/objects \
  -H "Content-Type: application/json" \
  -d '{
    "type_id": "ot_project",
    "data": {
      "name": "Test Project",
      "status": "planning",
      "planned_start": "2026-03-01T00:00:00Z",
      "planned_end": "2026-06-01T00:00:00Z"
    }
  }'
```

### 3. Check Neo4j Graph

Open Neo4j Browser at http://localhost:7474:

```cypher
// View schema
CALL db.schema.visualization()

// Count nodes
MATCH (n) RETURN labels(n), count(n)

// Test relationship
MATCH (c:ot_customer)-[:lt_customer_has_project]->(p:ot_project)
RETURN c.name, p.name LIMIT 10
```

## Troubleshooting

### Issue: "Connection refused" to PostgreSQL

**Solution**: Ensure services are running:
```bash
docker ps  # Check containers
make logs  # View logs
```

### Issue: Object types not found

**Solution**: Check database directly:
```bash
docker exec -it orgmind-postgres psql -U orgmind -d orgmind -c "SELECT id, name FROM object_types WHERE id LIKE 'ot_%';"
```

### Issue: Import errors

**Solution**: Ensure you're in the correct directory:
```bash
# Must run from extensions/project_management or project root
python extensions/project_management/scripts/load_config.py
```

### Issue: YAML parsing errors

**Solution**: Validate YAML syntax:
```bash
pip install yamllint
yamllint extensions/project_management/config/
```

## File Structure

```
extensions/project_management/
├── config/
│   ├── object_types.yaml       # Entity definitions (15 types)
│   ├── link_types.yaml         # Relationship definitions (28 types)
│   ├── triggers.yaml           # Automation rules (25 triggers)
│   └── triggers_export.json    # Auto-generated trigger export
├── scripts/
│   ├── load_config.py          # Main deployment script
│   └── README.md               # This file
└── tests/
    └── test_config_deployment.py  # Verification tests
```

## Next Steps After Deployment

1. **Create sample data** (optional)
   ```bash
   python extensions/project_management/scripts/load_sample_data.py
   ```

2. **Start implementing schedulers**
   - Priority Calculator
   - Impact Analyzer
   - Nudge Generator
   - Skill Matcher

3. **Build frontend dashboard**
   - Portfolio view
   - Resource allocation
   - Sprint planning

## Configuration Updates

To update configuration after initial deployment:

1. Edit YAML files in `config/`
2. Run loader without reset (updates existing):
   ```bash
   python scripts/load_config.py --verify
   ```
3. For breaking changes, use reset (⚠️ destructive):
   ```bash
   python scripts/load_config.py --reset --verify
   ```

## Support

- OrgMind Documentation: `private/context/orgmind-components/`
- PM Design Docs: `docs/PRD_AI_Project_Management.md`
- Issues: Check logs with `make logs`
