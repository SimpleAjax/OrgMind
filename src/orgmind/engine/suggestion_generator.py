import logging
import json
from typing import List, Dict, Any, Optional

# Using OpenAIProvider directly as it is the current implementation
from orgmind.agents.llm import OpenAIProvider, MessageCreate 
from orgmind.storage.models_traces import DecisionTraceModel, ContextSnapshotModel, ContextSuggestionModel

logger = logging.getLogger(__name__)

class SuggestionGenerator:
    """
    Uses an LLM to generate context suggestions for a decision trace.
    """
    
    def __init__(self, llm_service: OpenAIProvider):
        self.llm = llm_service
        
    async def generate_suggestion(self, trace: DecisionTraceModel, snapshot: ContextSnapshotModel) -> Optional[str]:
        """
        Analyze the trace and snapshot to suggest a reason for the action.
        """
        try:
            prompt = self._construct_prompt(trace, snapshot)
            messages = [
                {"role": "system", "content": "You are an expert system analyst. Your goal is to explain WHY a specific action was taken based on the available data context."},
                {"role": "user", "content": prompt}
            ]
            
            # OpenAIProvider.chat_completion returns an object like OpenAI response
            response = self.llm.chat_completion(messages=messages, model="gpt-4o") # default model
            suggestion = response.choices[0].message.content.strip()
            
            # Basic cleanup if the LLM is too chatty
            if "Reason:" in suggestion:
                suggestion = suggestion.split("Reason:")[-1].strip()
                
            return suggestion
            
        except Exception as e:
            logger.error(f"Failed to generate suggestion for trace {trace.id}: {e}")
            return None

    def _construct_prompt(self, trace: DecisionTraceModel, snapshot: ContextSnapshotModel) -> str:
        # Format Trace
        trace_info = f"""
        Action: {trace.action_type}
        Input: {json.dumps(trace.input_payload, indent=2)}
        Status: {trace.status}
        Timestamp: {trace.timestamp}
        """
        
        # Format Snapshot
        snapshot_info = "No context snapshot available."
        if snapshot:
            entities = snapshot.entity_states
            graph = snapshot.graph_neighborhood
            snapshot_info = f"""
            Entities involved: {json.dumps(entities, indent=2)}
            Graph Context: {json.dumps(graph, indent=2)}
            """
            
        return f"""
        Analyze the following system action and its context to infer the likely business or technical reason it occurred.
        
        TRACE DATA:
        {trace_info}
        
        CONTEXT DATA:
        {snapshot_info}
        
        Provide a single, concise sentence explaining the likely reason (e.g., "The task priority was escalated due to an approaching deadline linked to project X").
        """
