# OrgMind AI Project Management Extension

AI-powered Project Management system built on the OrgMind platform.

## Features

- **Intelligent Resource Allocation**: Skill-based matching with proficiency levels
- **Predictive Analytics**: AI-powered delay risk prediction
- **Impact Analysis**: Real-time calculation of scope/leave changes
- **Proactive Nudges**: AI agent alerts for risks and opportunities
- **Sprint Planning**: AI-assisted task selection and capacity planning
- **What-If Scenarios**: Simulate changes before committing

## Architecture

This extension uses OrgMind's platform capabilities:

- **Ontology Engine**: Dynamic schema for PM entities
- **Trigger Engine**: Event-driven automation
- **Graph Database**: Neo4j for dependency analysis
- **Agent System**: LLM-powered insights and recommendations

## Quick Start

### 1. Deploy Configuration

```bash
cd extensions/project_management

# Deploy to OrgMind
python scripts/load_config.py --verify

# Or use the shell script
chmod +x scripts/deploy.sh
./deploy.sh --verify
```

### 2. Verify Deployment

```bash
# Run tests
pytest tests/ -v

# Check APIs
curl http://localhost:8000/api/v1/types/objects
```

### 3. Load Sample Data (Optional)

```bash
python scripts/load_sample_data.py
```

## Directory Structure

```
extensions/project_management/
├── config/                 # Configuration files (✅ Phase 1 Complete)
│   ├── object_types.yaml   # 15 entity definitions
│   ├── link_types.yaml     # 28 relationship types
│   └── triggers.yaml       # 25 automation rules
├── scripts/                # Deployment scripts (✅ Phase 1 Complete)
│   ├── load_config.py
│   ├── deploy.sh
│   └── README.md
├── tests/                  # Test suite
│   ├── test_config_deployment.py
│   ├── test_schedulers.py  # Phase 2 & 3 scheduler tests
│   └── test_agent_tools.py # Agent tools tests
├── schedulers/             # Core schedulers (✅ Phase 2 & 3 Complete)
│   ├── __init__.py
│   ├── base.py             # Base scheduler with common utilities
│   ├── priority_calculator.py    # Project priority scoring
│   ├── impact_analyzer.py        # Change impact analysis
│   ├── nudge_generator.py        # AI nudge generation
│   ├── skill_matcher.py          # Skill-based matching
│   ├── sprint_planner.py         # AI sprint planning
│   ├── velocity_calculator.py    # Productivity tracking
│   └── conflict_detector.py      # Conflict detection
├── agent_tools/            # AI agent tools (✅ Phase 3 Complete)
│   ├── __init__.py
│   ├── query_tools.py            # Query tools (projects, tasks, health, utilization)
│   ├── analysis_tools.py         # Analysis tools (impact, simulation, recommendations)
│   └── action_tools.py           # Action tools (nudges, reassignments)
├── api/                    # REST API endpoints (✅ Phase 4 Complete)
│   ├── __init__.py
│   ├── router.py           # Main API router
│   ├── dashboard.py        # Dashboard endpoints
│   ├── projects.py         # Project endpoints
│   ├── tasks.py            # Task endpoints
│   ├── resources.py        # Resource endpoints
│   ├── sprints.py          # Sprint endpoints
│   ├── simulation.py       # Simulation endpoints
│   ├── reports.py          # Report endpoints
│   ├── nudges.py           # Nudge endpoints
│   └── README.md
├── agent.py                # PM Assistant Agent (✅ Phase 4)
├── frontend/               # Dashboard frontend (✅ Phase 4)
│   ├── index.html
│   ├── css/styles.css
│   ├── js/api.js
│   ├── js/components.js
│   ├── js/dashboard.js
│   ├── Dockerfile
│   └── README.md
└── README.md
```

## Implementation Status

| Phase | Status | Components |
|-------|--------|------------|
| Phase 1 | ✅ Complete | Object Types, Link Types, Triggers |
| Phase 2 | ✅ Complete | Priority Calculator, Impact Analyzer, Nudge Generator, Skill Matcher |
| Phase 3 | ✅ Complete | Sprint Planner, Velocity Calculator, Conflict Detector, Agent Tools |
| Phase 4 | ✅ Complete | API Endpoints, PM Agent, Frontend |
| Phase 5 | 🔲 Not Started | Testing & Documentation |
| Phase 6 | 🔲 Not Started | Deployment |

## Configuration

### Object Types (15 entities)

Core entities for project management:
- **Customers**: Client organizations with tiers
- **Projects**: Work containers with priority/risk scores
- **Sprints**: Iteration planning
- **Tasks**: Work items with AI predictions
- **People**: Team members with skills
- **Skills**: Capability catalog with proficiency
- **Assignments**: Task-person allocations
- **Nudges**: AI-generated notifications

See `config/object_types.yaml` for full schema.

### Link Types (28 relationships)

Relationships connecting entities:
- Customer → Project
- Project → Task → Person
- Task blocks Task (dependencies)
- Person has Skill (proficiency)
- Sprint contains Task

See `config/link_types.yaml` for full definitions.

### Triggers (25 rules)

Event-driven and scheduled automation:

**Event Triggers**:
- Task status change → Update dependencies
- Leave approved → Impact analysis
- Project scope change → Recalculate priorities

**Scheduled Triggers**:
- Priority recalculation (hourly)
- Nudge generation (every 15 min)
- Conflict detection (every 30 min)
- Velocity updates (every 2 hours)

See `config/triggers.yaml` for full rules.

## Development

### Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ -v

# Lint YAML
yamllint config/
```

### Adding New Features

1. **Update schema**: Edit `config/object_types.yaml` or `link_types.yaml`
2. **Redeploy**: `python scripts/load_config.py --verify`
3. **Implement logic**: Add code to `schedulers/` or `agent_tools/`
4. **Add tests**: Create tests in `tests/`

### Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_config_deployment.py -v

# Run with coverage
pytest tests/ --cov=extensions/project_management --cov-report=html
```

## API Endpoints

After deployment, the following endpoints are available:

### Object APIs (Auto-generated)

```
GET    /api/v1/objects                    # List all objects
GET    /api/v1/objects?type_id=ot_project # Filter by type
POST   /api/v1/objects                    # Create object
GET    /api/v1/objects/{id}               # Get object
PATCH  /api/v1/objects/{id}               # Update object
DELETE /api/v1/objects/{id}               # Delete object
```

### Type APIs (Auto-generated)

```
GET /api/v1/types/objects              # List object types
GET /api/v1/types/objects/ot_project   # Get project schema
GET /api/v1/types/links                # List link types
```

### PM-Specific APIs (Phase 4)

```
GET  /pm/dashboard/portfolio           # Portfolio overview
GET  /pm/projects/{id}/health          # Project health
POST /pm/projects/{id}/impact          # Impact analysis
GET  /pm/sprints/{id}/recommendations  # AI recommendations
GET  /pm/resources/allocations         # Resource view
POST /pm/simulate/leave                # What-if scenarios
```

## Documentation

- **PRD**: `docs/PRD_AI_Project_Management.md`
- **Ontology Design**: `docs/ONTOLOGY_DESIGN.md`
- **Logic Design**: `docs/LOGIC_SCHEDULER_DESIGN.md`
- **OrgMind Analysis**: `docs/ORGMIND_ANALYSIS.md`
- **Tasks**: `docs/TASKS.md`

## Contributing

1. Create feature branch
2. Make changes
3. Add tests
4. Run verification: `python scripts/load_config.py --verify`
5. Submit pull request

## License

Proprietary - Part of OrgMind Platform

## Support

For issues or questions:
- Check `scripts/README.md` for troubleshooting
- Review OrgMind docs: `private/context/orgmind-components/`
- Check logs: `make logs` from project root
