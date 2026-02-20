"""
AI Agent Tools for Project Management

Specialized tools that AI agents can use to interact with project management data.

Query Tools:
- query_projects: Search projects
- query_tasks: Search tasks
- get_project_health: Get project health metrics
- get_person_utilization: Get resource utilization

Analysis Tools:
- analyze_impact: What-if analysis
- simulate_scope_change: Try changes without committing
- get_sprint_recommendations: AI sprint planning
- find_skill_matches: Match people to tasks

Action Tools:
- create_nudge: Create manual nudge
- reassign_task: Reallocate task
"""

from .query_tools import (
    query_projects,
    query_tasks,
    get_project_health,
    get_person_utilization
)
from .analysis_tools import (
    analyze_impact,
    simulate_scope_change,
    get_sprint_recommendations,
    find_skill_matches
)
from .action_tools import (
    create_nudge,
    reassign_task
)

# Tool definitions for OpenAI function format
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "query_projects",
            "description": "Search and filter projects by various criteria",
            "parameters": {
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "object",
                        "description": "Filter criteria (status, customer_id, priority_min, etc.)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 20
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_tasks",
            "description": "Search and filter tasks by various criteria",
            "parameters": {
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "object",
                        "description": "Filter criteria (status, assignee_id, priority, due_before, etc.)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 20
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_project_health",
            "description": "Get health metrics and status for a specific project",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "string",
                        "description": "ID of the project to analyze"
                    }
                },
                "required": ["project_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_person_utilization",
            "description": "Get resource utilization for a person",
            "parameters": {
                "type": "object",
                "properties": {
                    "person_id": {
                        "type": "string",
                        "description": "ID of the person"
                    },
                    "date_range": {
                        "type": "object",
                        "description": "Date range {'start': 'YYYY-MM-DD', 'end': 'YYYY-MM-DD'}"
                    }
                },
                "required": ["person_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_impact",
            "description": "Analyze the impact of a hypothetical scenario (leave, scope change, etc.)",
            "parameters": {
                "type": "object",
                "properties": {
                    "scenario_type": {
                        "type": "string",
                        "enum": ["leave", "scope_change", "resource_change"],
                        "description": "Type of scenario to analyze"
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Scenario-specific parameters"
                    }
                },
                "required": ["scenario_type", "parameters"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "simulate_scope_change",
            "description": "Simulate adding or removing tasks from a project",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "string",
                        "description": "Project to simulate changes on"
                    },
                    "added_tasks": {
                        "type": "array",
                        "description": "Tasks to add",
                        "items": {"type": "object"}
                    },
                    "removed_task_ids": {
                        "type": "array",
                        "description": "IDs of tasks to remove",
                        "items": {"type": "string"}
                    }
                },
                "required": ["project_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_sprint_recommendations",
            "description": "Get AI recommendations for sprint planning",
            "parameters": {
                "type": "object",
                "properties": {
                    "sprint_id": {
                        "type": "string",
                        "description": "Sprint to get recommendations for"
                    }
                },
                "required": ["sprint_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_skill_matches",
            "description": "Find the best people for a task based on skills",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task to find matches for"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of matches",
                        "default": 5
                    }
                },
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_nudge",
            "description": "Create a manual nudge/notification for users",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["risk", "opportunity", "conflict", "suggestion"],
                        "description": "Type of nudge"
                    },
                    "title": {
                        "type": "string",
                        "description": "Short title for the nudge"
                    },
                    "description": {
                        "type": "string",
                        "description": "Detailed description"
                    },
                    "recipient_ids": {
                        "type": "array",
                        "description": "IDs of people to notify",
                        "items": {"type": "string"}
                    },
                    "related_project_id": {
                        "type": "string",
                        "description": "Optional related project"
                    },
                    "related_task_id": {
                        "type": "string",
                        "description": "Optional related task"
                    }
                },
                "required": ["type", "title", "description", "recipient_ids"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "reassign_task",
            "description": "Reassign a task from one person to another",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task to reassign"
                    },
                    "from_person_id": {
                        "type": "string",
                        "description": "Current assignee (if any)"
                    },
                    "to_person_id": {
                        "type": "string",
                        "description": "New assignee"
                    }
                },
                "required": ["task_id", "to_person_id"]
            }
        }
    }
]

__all__ = [
    # Query tools
    'query_projects',
    'query_tasks',
    'get_project_health',
    'get_person_utilization',
    # Analysis tools
    'analyze_impact',
    'simulate_scope_change',
    'get_sprint_recommendations',
    'find_skill_matches',
    # Action tools
    'create_nudge',
    'reassign_task',
    # Tool definitions
    'TOOL_DEFINITIONS'
]
