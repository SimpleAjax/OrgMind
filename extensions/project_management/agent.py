"""
PM Assistant Agent

A specialized AI agent for project managers with PM-specific system prompt and tools.

Usage:
    # Create the agent
    from extensions.project_management.agent import create_pm_assistant_agent
    agent = create_pm_assistant_agent(session, owner_id="user_123")
    
    # Or get existing
    agent = get_pm_assistant_agent(session)
"""

from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from orgmind.storage.models import AgentModel
from orgmind.agents.schemas import AgentCreate
from orgmind.agents.service import AgentService

from .agent_tools import TOOL_DEFINITIONS


# PM Assistant System Prompt
PM_ASSISTANT_SYSTEM_PROMPT = """You are an AI Project Management Assistant for OrgMind, an intelligent project management platform.

YOUR ROLE:
You help project managers make better decisions by providing data-driven insights, running what-if scenarios, and automating routine tasks. You have access to the organization's project data, resource allocations, and scheduling information.

YOUR CAPABILITIES:
1. Project Portfolio Management
   - Answer questions about project status, health, and risks
   - Identify at-risk projects and tasks
   - Generate portfolio reports and summaries

2. Resource Management
   - Check resource utilization and availability
   - Identify overallocation and conflicts
   - Suggest optimal task assignments based on skills
   - Recommend workload rebalancing

3. Sprint Planning
   - Generate AI-powered sprint recommendations
   - Analyze sprint health and progress
   - Suggest task prioritization

4. Impact Analysis
   - Simulate the impact of scope changes
   - Analyze the effect of team member leave
   - Compare different planning scenarios

5. Proactive Alerts (Nudges)
   - Create and manage nudges for risks and opportunities
   - Help resolve conflicts and issues

6. Reporting
   - Generate portfolio, utilization, and skills gap reports
   - Provide insights on team productivity

HOW TO INTERACT:
- Be concise but thorough in your responses
- Always provide actionable recommendations
- When making changes, explain the impact
- Use data to support your recommendations
- Ask clarifying questions when needed

TOOL USAGE:
You have access to specialized tools for project management:
- Query tools to fetch project and task data
- Analysis tools to run simulations and impact analysis
- Action tools to create nudges and reassign tasks

Always use the most specific tool for the job. If a user asks about a specific project, use query_projects or get_project_health rather than listing all projects.

RESPONSE FORMAT:
1. Direct answer to the question
2. Supporting data or context
3. Recommended actions (if applicable)
4. Offer to run simulations or provide more details

PERMISSIONS AND SAFETY:
- You can read all project data the user has access to
- You can create nudges and reassign tasks on behalf of the user
- You cannot delete projects or tasks
- You will ask for confirmation before making significant changes
- You respect data privacy and only access information relevant to the query

When the user asks about "my" projects or tasks, use their user ID to filter appropriately.
"""


# Agent configuration
PM_ASSISTANT_CONFIG = {
    "name": "PM Assistant",
    "description": "AI assistant for project managers. Helps with portfolio management, resource allocation, sprint planning, and impact analysis.",
    "system_prompt": PM_ASSISTANT_SYSTEM_PROMPT,
    "scope": "USER",  # Personal agent per user
    "llm_config": {
        "model": "gpt-4o",
        "temperature": 0.3,  # Lower temperature for more consistent, factual responses
        "max_tokens": 2000
    }
}


def create_pm_assistant_agent(
    session: Session,
    owner_id: str,
    custom_tools: Optional[List[str]] = None
) -> AgentModel:
    """
    Create a new PM Assistant agent for a user.
    
    Args:
        session: Database session
        owner_id: User ID who owns this agent
        custom_tools: Optional list of tool names to enable (defaults to all)
        
    Returns:
        Created AgentModel
    """
    service = AgentService(session)
    
    # Check if user already has a PM assistant
    existing = get_pm_assistant_agent(session, owner_id)
    if existing:
        raise ValueError(f"User {owner_id} already has a PM Assistant agent")
    
    # Create agent
    agent_data = AgentCreate(
        name=PM_ASSISTANT_CONFIG["name"],
        description=PM_ASSISTANT_CONFIG["description"],
        system_prompt=PM_ASSISTANT_CONFIG["system_prompt"],
        scope=PM_ASSISTANT_CONFIG["scope"],
        llm_config=PM_ASSISTANT_CONFIG["llm_config"],
        parent_agent_id=None
    )
    
    agent = service.create_agent(agent_data, owner_id)
    
    # Store tool configuration in agent metadata (if supported)
    # This is a placeholder - actual tool registration depends on OrgMind's implementation
    enabled_tools = custom_tools or [t["function"]["name"] for t in TOOL_DEFINITIONS]
    
    # Update agent with tool metadata
    if hasattr(agent, 'data') or hasattr(agent, 'metadata'):
        tool_config = {
            'enabled_tools': enabled_tools,
            'tool_definitions': TOOL_DEFINITIONS,
            'agent_type': 'pm_assistant'
        }
        # Store in agent's data field if available
        if hasattr(agent, 'data'):
            agent.data = tool_config
            session.commit()
    
    return agent


def get_pm_assistant_agent(
    session: Session,
    owner_id: Optional[str] = None
) -> Optional[AgentModel]:
    """
    Get the PM Assistant agent for a user.
    
    Args:
        session: Database session
        owner_id: User ID (optional, if None returns first PM assistant found)
        
    Returns:
        AgentModel or None if not found
    """
    service = AgentService(session)
    
    if owner_id:
        agents = service.list_agents(owner_id=owner_id)
    else:
        agents = service.list_agents()
    
    # Find PM Assistant
    for agent in agents:
        # Check by name or metadata
        if agent.name == PM_ASSISTANT_CONFIG["name"]:
            return agent
        
        # Check by metadata if stored
        agent_data = getattr(agent, 'data', None) or getattr(agent, 'metadata', None)
        if agent_data and isinstance(agent_data, dict):
            if agent_data.get('agent_type') == 'pm_assistant':
                return agent
    
    return None


def ensure_pm_assistant_exists(
    session: Session,
    owner_id: str
) -> AgentModel:
    """
    Ensure a PM Assistant exists for the user, creating if necessary.
    
    Args:
        session: Database session
        owner_id: User ID
        
    Returns:
        AgentModel (existing or newly created)
    """
    agent = get_pm_assistant_agent(session, owner_id)
    if agent:
        return agent
    
    return create_pm_assistant_agent(session, owner_id)


def get_pm_assistant_tools() -> List[Dict[str, Any]]:
    """
    Get the tool definitions for the PM Assistant.
    
    Returns:
        List of tool definitions in OpenAI function format
    """
    return TOOL_DEFINITIONS


def register_pm_assistant_with_orgmind(
    session: Session,
    owner_id: str
) -> Dict[str, Any]:
    """
    Register the PM Assistant with OrgMind's agent system.
    
    This creates the agent and makes it available in the system.
    
    Args:
        session: Database session
        owner_id: User ID
        
    Returns:
        Registration result
    """
    try:
        agent = ensure_pm_assistant_exists(session, owner_id)
        
        return {
            'success': True,
            'agent_id': agent.id,
            'agent_name': agent.name,
            'owner_id': owner_id,
            'tools_enabled': len(TOOL_DEFINITIONS),
            'message': 'PM Assistant registered successfully'
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'message': 'Failed to register PM Assistant'
        }


# Agent capabilities documentation for users
PM_ASSISTANT_CAPABILITIES = """
## PM Assistant Capabilities

### 1. Portfolio Management
- "Show me my portfolio overview"
- "Which projects are at risk?"
- "What's the health status of Project X?"
- "Generate a portfolio report"

### 2. Resource Management
- "Who's available next week?"
- "Is anyone overallocated?"
- "Find the best person for Task Y"
- "Show me resource conflicts"
- "What's the utilization of Team Member Z?"

### 3. Sprint Planning
- "Recommend tasks for Sprint 5"
- "How healthy is our current sprint?"
- "Can we add more to this sprint?"

### 4. Impact Analysis
- "What if Sarah takes next week off?"
- "How would adding 3 new tasks affect Project X?"
- "Compare these two planning scenarios"

### 5. Task Management
- "Reassign Task 123 to John"
- "Create a nudge about the deadline risk"
- "Show me task dependencies"

### 6. Reporting
- "Generate a utilization report for March"
- "What are our skill gaps?"
- "Show me the portfolio summary"

The assistant will use the appropriate tools to fetch data and provide actionable insights.
"""
