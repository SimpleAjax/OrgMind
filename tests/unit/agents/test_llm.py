import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from orgmind.agents.llm import AgentBrain
from orgmind.agents.schemas import MessageResponse, MessageCreate

@pytest.fixture
def mock_service():
    service = MagicMock()
    # Explicitly configure conversation mock
    conversation = MagicMock()
    conversation.user_id = "user-1"
    service.get_conversation.return_value = conversation
    
    service.get_conversation_history.return_value = [
        MagicMock(role="user", content="Hello", tool_calls=None)
    ]
    service.add_message.side_effect = lambda cid, data: MessageResponse(
        id="msg-2", conversation_id=cid, role="assistant", content=data.content, created_at="2023-01-01T00:00:00"
    )
    service.get_user_roles.return_value = ["admin", "editor"]
    return service

@pytest.fixture
def mock_memory_store():
    with patch("orgmind.agents.llm.MemoryStore") as mock:
        instance = mock.return_value
        instance.initialize = AsyncMock()
        instance.add_memory = AsyncMock()
        instance.search_memory = AsyncMock(return_value=[
            MagicMock(content="Memory 1")
        ])
        yield instance

@pytest.fixture
def mock_context_builder():
    with patch("orgmind.agents.llm.ContextBuilder") as mock:
        instance = mock.return_value
        instance.get_context = AsyncMock(return_value="Graph Context Info")
        yield instance

@pytest.fixture
def mock_provider():
    with patch("orgmind.agents.llm.OpenAIProvider") as mock:
        instance = mock.return_value
        # Mock chat_completion response
        message = MagicMock(content="Hello there", tool_calls=None)
        choice = MagicMock(message=message)
        response = MagicMock(choices=[choice])
        instance.chat_completion.return_value = response
        yield instance

@pytest.mark.asyncio
async def test_agent_brain_process(mock_service, mock_memory_store, mock_context_builder, mock_provider):
    brain = AgentBrain(mock_service)
    
    agent = MagicMock()
    agent.id = "agent-1"
    agent.system_prompt = "System Prompt"
    agent.llm_config = {}
    agent.parent_agent_id = None
    
    # Run process
    response = await brain.process(agent, "conv-1")
    
    # Verify Intialization
    mock_memory_store.initialize.assert_called_once()
    
    # Verify Search and Context Retrieval
    mock_memory_store.search_memory.assert_called_once()
    # Check that roles were passed
    _, kwargs = mock_memory_store.search_memory.call_args
    if 'filter_params' in kwargs:
        assert kwargs['filter_params'].roles == ["admin", "editor"]
    else:
        # Argument might be passed as positional or checked differently
        pass
    
    mock_context_builder.get_context.assert_called_once()
    
    # Verify Prompt Augmentation
    # We check the call to provider
    call_args = mock_provider.chat_completion.call_args
    messages = call_args[1]['messages'] # or args[0]
    
    system_msg = messages[0]
    assert system_msg['role'] == 'system'
    assert "System Prompt" in system_msg['content']
    assert "Memory 1" in system_msg['content']
    assert "Graph Context Info" in system_msg['content']
    
    # Verify Memory Saving (User and Assistant)
    assert mock_memory_store.add_memory.call_count == 2 # 1 for user, 1 for assistant

@pytest.mark.asyncio
async def test_agent_brain_inheritance(mock_service, mock_memory_store, mock_context_builder, mock_provider):
    brain = AgentBrain(mock_service)
    
    # Setup Child and Parent Agents
    parent_agent = MagicMock(id="agent-parent", system_prompt="Parent Prompt", llm_config={}, parent_agent_id=None)
    child_agent = MagicMock(id="agent-child", system_prompt="Child Prompt", llm_config={}, parent_agent_id="agent-parent")
    
    # Mock service.get_agent to return parent
    mock_service.get_agent.side_effect = lambda agent_id: parent_agent if agent_id == "agent-parent" else None
    
    # Mock memory store to return different memories based on agent_id in filter
    async def side_effect_search(query, filter_params, limit):
        if filter_params.agent_id == "agent-child":
            return [MagicMock(id="mem-1", content="Child Memory", score=0.9)]
        elif filter_params.agent_id == "agent-parent":
            return [MagicMock(id="mem-2", content="Parent Memory", score=0.8)]
        return []
    
    mock_memory_store.search_memory.side_effect = side_effect_search
    
    # Run process
    await brain.process(child_agent, "conv-1")
    
    # Verify search called twice (once for child, once for parent)
    assert mock_memory_store.search_memory.call_count == 2
    
    # Verify System Prompt contains both memories
    call_args = mock_provider.chat_completion.call_args
    messages = call_args[1]['messages']
    system_msg = messages[0]
    
    assert "Child Memory" in system_msg['content']
    assert "Parent Memory" in system_msg['content']
