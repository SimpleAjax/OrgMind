# Project Management API

This module provides PM-specific REST API endpoints for OrgMind.

## Integration

To integrate with OrgMind's main API, add the following to `src/orgmind/api/main.py`:

```python
# Import the PM router
from extensions.project_management.api import router as pm_router

# Include the router
app.include_router(pm_router, prefix="/pm", tags=["Project Management"])
```

## Endpoints

### Dashboard
- `GET /pm/dashboard/portfolio` - Portfolio overview
- `GET /pm/dashboard/risks` - At-risk items
- `GET /pm/dashboard/utilization` - Resource heatmap

### Projects
- `GET /pm/projects/{id}/health` - Project health
- `POST /pm/projects/{id}/impact` - Scope change impact
- `GET /pm/projects/{id}/timeline` - Project timeline

### Tasks
- `GET /pm/tasks/{id}/matches` - Best people for task
- `GET /pm/tasks/{id}/dependencies` - Dependency graph
- `POST /pm/tasks/{id}/reassign` - Reassign task

### Resources
- `GET /pm/resources/allocations` - All allocations
- `GET /pm/resources/{id}/utilization` - Single person view
- `GET /pm/resources/conflicts` - Current conflicts

### Sprints
- `GET /pm/sprints/{id}/recommendations` - AI recommendations
- `POST /pm/sprints/{id}/plan` - Commit sprint plan
- `GET /pm/sprints/{id}/health` - Sprint health check

### Simulation
- `POST /pm/simulate/leave` - Simulate person on leave
- `POST /pm/simulate/scope` - Simulate scope change
- `POST /pm/simulate/compare` - Compare scenarios

### Reports
- `GET /pm/reports/portfolio` - Portfolio report
- `GET /pm/reports/utilization` - Utilization report
- `GET /pm/reports/skills` - Skills gap report

### Nudges
- `GET /pm/nudges` - List nudges
- `POST /pm/nudges/{id}/acknowledge` - Acknowledge
- `POST /pm/nudges/{id}/dismiss` - Dismiss
- `POST /pm/nudges/{id}/act` - Execute suggested action

## Authentication

All endpoints require authentication via the standard OrgMind auth system.

## Permissions

Required permissions:
- `project.read` - Read project data
- `project.write` - Modify projects
- `task.read` - Read task data
- `task.write` - Modify tasks
- `resource.read` - Read resource data
- `sprint.read` / `sprint.write` - Sprint operations
- `nudge.read` / `nudge.write` - Nudge operations
- `report.read` - Generate reports
