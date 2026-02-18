from typing import List, Dict, Any, Optional, Protocol
import json
import logging
from openai import OpenAI
from orgmind.platform.config import settings
from orgmind.agents.schemas import MessageCreate
from orgmind.storage.models import AgentModel, MessageModel
from orgmind.agents.tools import tool_registry

logger = logging.getLogger(__name__)

class LLMProvider(Protocol):
    def chat_completion(self, 
                        messages: List[Dict[str, Any]], 
                        model: str,
                        tools: Optional[List[Dict[str, Any]]] = None,
                        **kwargs) -> Any:
        ...

class OpenAIProvider:
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def chat_completion(self, 
                        messages: List[Dict[str, Any]], 
                        model: str, 
                        tools: Optional[List[Dict[str, Any]]] = None,
                        **kwargs) -> Any:
        completion_args = {
            "model": model,
            "messages": messages,
            **kwargs
        }
        if tools:
            completion_args["tools"] = tools
            
        return self.client.chat.completions.create(**completion_args)

from orgmind.agents.memory import MemoryStore
from orgmind.agents.context import ContextBuilder
from orgmind.agents.schemas import MemoryCreate, MemoryFilter

class AgentBrain:
    def __init__(self, service):
        self.service = service
        self.provider = OpenAIProvider()
        self.memory_store = MemoryStore()
        self.context_builder = ContextBuilder()

    async def process(self, agent: AgentModel, conversation_id: str) -> MessageModel:
        """
        Main loop for processing a conversation state:
        1. Load history
        2. Prepare context (system prompt + history + memory + graph)
        3. Call LLM
        4. If tool call -> Execute -> Add result -> GOTO 3
        5. If content -> Save -> Return
        """
        
        # Initialize components (idempotent/fast checks)
        await self.memory_store.initialize()

        # Get Conversation Details (for user_id)
        conversation = self.service.get_conversation(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")
        user_id = conversation.user_id

        # Get User Roles for Access Control
        user_roles = self.service.get_user_roles(user_id)

        # Get recent history
        history = self.service.get_conversation_history(conversation_id)
        
        # Extract User Query from last message if it's user
        user_query = ""
        if history and history[-1].role == "user":
            user_query = history[-1].content
            
            # Async Save User Message to Memory
            # We fire and forget ideally, but here we await for simplicity/consistency
            try:
                await self.memory_store.add_memory(MemoryCreate(
                    content=user_query,
                    role="user",
                    agent_id=agent.id,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    type="raw"
                ))
            except Exception as e:
                logger.error("failed_to_save_user_memory", error=str(e))

        # Retrieve Context (RAG)
        rag_context = ""
        if user_query:
            # 1. Long-term Memory (Inheritance)
            hierarchy_memories = []
            
            # Traverse hierarchy
            curr_agent = agent
            depth = 0
            visited = set()
            
            while curr_agent and depth < 3:
                if curr_agent.id in visited:
                    break
                visited.add(curr_agent.id)
                
                # Search memory for this agent
                memories = await self.memory_store.search_memory(
                    query=user_query,
                    filter_params=MemoryFilter(
                        agent_id=curr_agent.id,
                        user_id=user_id,
                        roles=user_roles
                    ),
                    limit=5
                )
                hierarchy_memories.extend(memories)
                
                # Move to parent
                if curr_agent.parent_agent_id:
                   # Fetch parent
                   curr_agent = self.service.get_agent(curr_agent.parent_agent_id)
                else:
                   curr_agent = None
                
                depth += 1
            
            # Deduplicate by ID
            seen_ids = set()
            unique_memories = []
            for m in hierarchy_memories:
                if m.id not in seen_ids:
                    unique_memories.append(m)
                    seen_ids.add(m.id)
            
            # Re-sort based on score
            unique_memories.sort(key=lambda x: x.score or 0, reverse=True)
            
            if unique_memories:
                rag_context += "\n[Relevant Past Memories (User & Parent Agents)]:\n" + "\n".join([f"- {m.content}" for m in unique_memories[:5]])

            # 2. Graph Context
            graph_context = await self.context_builder.get_context(user_query)
            if graph_context:
                rag_context += "\n\n[Organizational Context]:\n" + graph_context

        # Max turns to prevent infinite loops
        max_turns = 10 
        turn_count = 0

        while turn_count < max_turns:
            messages = self._prepare_messages(agent, conversation_id, rag_context)
            tools = tool_registry.get_definitions()
            
            # Call LLM
            response = self.provider.chat_completion(
                messages=messages,
                model=agent.llm_config.get("model", settings.OPENAI_MODEL),
                tools=tools if tools else None,
                temperature=agent.llm_config.get("temperature", 0.7)
            )
            
            message_choice = response.choices[0].message
            
            # Handle Tool Calls
            if message_choice.tool_calls:
                # 1. Save assistant message with tool calls
                tool_calls_data = []
                for tc in message_choice.tool_calls:
                    tool_calls_data.append({
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    })
                
                assistant_msg_data = MessageCreate(
                    role="assistant",
                    content=message_choice.content or "", # Content might be null if just tool call
                    tool_calls=tool_calls_data
                )
                self.service.add_message(conversation_id, assistant_msg_data)
                
                # 2. Execute tools and add tool outputs
                for tc in message_choice.tool_calls:
                    await self._execute_tool_and_save(conversation_id, tc)
                
                # Loop continues to get next response from LLM
                turn_count += 1
                continue
            
            # Handle Final Response
            else:
                final_content = message_choice.content
                final_msg_data = MessageCreate(
                    role="assistant",
                    content=final_content
                )
                saved_msg = self.service.add_message(conversation_id, final_msg_data)
                
                # Async Save Assistant Response to Memory
                if final_content:
                    try:
                        await self.memory_store.add_memory(MemoryCreate(
                            content=final_content,
                            role="assistant",
                            agent_id=agent.id,
                            user_id=user_id,
                            conversation_id=conversation_id,
                            type="raw"
                        ))
                    except Exception as e:
                        logger.error("failed_to_save_assistant_memory", error=str(e))
                
                return saved_msg
        
        # Fallback if loop limit reached
        return self.service.add_message(conversation_id, MessageCreate(
            role="assistant", 
            content="I apologize, but I reached the maximum number of processing steps. Please try again or simplify your request."
        ))

    def _prepare_messages(self, agent: AgentModel, conversation_id: str, rag_context: str = "") -> List[Dict[str, Any]]:
        history = self.service.get_conversation_history(conversation_id)
        
        system_content = agent.system_prompt
        if rag_context:
            system_content += f"\n\n=== CONTEXT ===\n{rag_context}\n==============="

        mapped_messages = [{"role": "system", "content": system_content}]
        for msg in history:
            if msg.role == "tool":
                # Extract tool_call_id from the JSON stash
                tool_call_id = msg.tool_calls[0].get("tool_call_id") if msg.tool_calls else None
                mapped_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": msg.content
                })
            elif msg.role == "assistant" and msg.tool_calls:
                mapped_messages.append({
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": msg.tool_calls
                })
            else:
                mapped_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
                
        return mapped_messages

    async def _execute_tool_and_save(self, conversation_id: str, tool_call: Any):
        func_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)
        tool_call_id = tool_call.id
        
        tool = tool_registry.get_tool(func_name)
        if not tool:
            result = f"Error: Tool {func_name} not found."
        else:
            try:
                # Inject dependencies if needed (e.g. session)
                # We simply pass kwargs, and let tool pick what it needs alongside arguments
                # Since we don't know what tool needs, we can pass `session` if we have it.
                # But Tool.run signature will capture it in **kwargs if not defined.
                # However, async run might need await.
                result = await tool.run(session=self.service.session, **arguments)
            except Exception as e:
                logger.error(f"Tool execution failed: {e}")
                result = f"Error executing tool: {str(e)}"
        
        # Save Tool Output
        msg_data = MessageCreate(
            role="tool",
            content=str(result),
            tool_calls=[{"tool_call_id": tool_call_id}]
        )
        self.service.add_message(conversation_id, msg_data)

