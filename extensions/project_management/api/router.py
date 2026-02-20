"""
Main router for Project Management API.

Combines all PM-specific endpoints under /pm/ prefix.
"""

from fastapi import APIRouter

from . import dashboard, projects, tasks, resources, sprints, simulation, reports, nudges

router = APIRouter(prefix="/pm", tags=["Project Management"])

# Include all sub-routers
router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
router.include_router(projects.router, prefix="/projects", tags=["Projects"])
router.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])
router.include_router(resources.router, prefix="/resources", tags=["Resources"])
router.include_router(sprints.router, prefix="/sprints", tags=["Sprints"])
router.include_router(simulation.router, prefix="/simulate", tags=["Simulation"])
router.include_router(reports.router, prefix="/reports", tags=["Reports"])
router.include_router(nudges.router, prefix="/nudges", tags=["Nudges"])
