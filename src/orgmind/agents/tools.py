from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable, Type
from pydantic import BaseModel, Field

class Tool(ABC):
    """Abstract base class for all agent tools."""
    
    name: str
    description: str
    parameters: Type[BaseModel]

    @abstractmethod
    async def run(self, **kwargs: Any) -> Any:
        pass

    @property
    def definition(self) -> Dict[str, Any]:
        """Returns the OpenAI function definition."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters.model_json_schema(),
            }
        }

class ToolRegistry:
    """Registry for managing available tools."""
    
    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool):
        if tool.name in self._tools:
            raise ValueError(f"Tool with name '{tool.name}' already registered")
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list_tools(self) -> List[Tool]:
        return list(self._tools.values())
    
    def get_definitions(self) -> List[Dict[str, Any]]:
        return [tool.definition for tool in self._tools.values()]

# Singleton registry
tool_registry = ToolRegistry()
