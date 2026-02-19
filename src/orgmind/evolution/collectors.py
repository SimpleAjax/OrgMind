from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import datetime

class MetricCollector(ABC):
    """
    Base class for collecting metrics related to an outcome.
    """
    @abstractmethod
    async def collect(self, definition_params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Collect metrics based on the definition parameters and context.
        
        Args:
            definition_params: Configuration from OutcomeDefinition (e.g. timeout, target_status)
            context: Context from the decision trace (e.g. task_id, email_thread_id)
            
        Returns:
            Dict containing collected metrics (e.g. {"status": "done", "completed_at": "..."})
        """
        pass

class MockCollector(MetricCollector):
    """
    Collector for testing purposes that returns pre-configured metrics.
    """
    async def collect(self, definition_params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        return definition_params.get("mock_response", {"success": True})

class TaskCompletionCollector(MetricCollector):
    """
    Checks if a task (e.g. in Jira/Linear) is completed.
    params: { "provider": "jira", "completed_statuses": ["Done", "Closed"] }
    context: { "task_id": "PROJ-123" }
    """
    async def collect(self, definition_params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        # TODO: Integrate with actual project management tool client
        # For now, simulate based on context
        task_id = context.get("task_id")
        if not task_id:
            return {"error": "No task_id in context"}
            
        # Simulation: assume task is done if ID starts with 'DONE' (for testing)
        is_done = task_id.startswith("DONE")
        return {
            "task_id": task_id,
            "status": "Done" if is_done else "In Progress",
            "is_completed": is_done,
            "checked_at": datetime.datetime.now().isoformat()
        }

class EmailReplyCollector(MetricCollector):
    """
    Checks if an email received a reply.
    params: { "timeout_hours": 24 }
    context: { "message_id": "...", "thread_id": "..." }
    """
    async def collect(self, definition_params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        # TODO: Integrate with EmailService
        thread_id = context.get("thread_id")
        if not thread_id:
            return {"error": "No thread_id in context"}
            
        # Simulation
        return {
            "thread_id": thread_id,
            "reply_count": 1, # Mock
            "last_reply_at": datetime.datetime.now().isoformat()
        }
