import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

from orgmind.storage.models import Base
from orgmind.agents.schemas import AgentCreate, AgentUpdate, ConversationCreate, MessageCreate
from orgmind.agents.service import AgentService

# Use in-memory SQLite for unit testing
@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_agent_crud(session):
    service = AgentService(session)
    owner_id = "user_123"
    
    # Create
    agent_data = AgentCreate(
        name="Test Agent",
        description="A test agent",
        system_prompt="You are a helper.",
        scope="USER",
        model_config={"model": "gpt-4o"}
    )
    agent = service.create_agent(agent_data, owner_id)
    
    assert agent.id is not None
    assert agent.name == "Test Agent"
    assert agent.owner_id == owner_id
    assert agent.llm_config["model"] == "gpt-4o"
    
    # Get
    fetched = service.get_agent(agent.id)
    assert fetched.name == "Test Agent"
    
    # List
    agents = service.list_agents(owner_id=owner_id)
    assert len(agents) == 1
    assert agents[0].id == agent.id
    
    # Update
    update_data = AgentUpdate(name="Updated Name")
    updated = service.update_agent(agent.id, update_data)
    assert updated.name == "Updated Name"
    assert updated.system_prompt == "You are a helper." # Unchanged
    
    # Delete
    success = service.delete_agent(agent.id)
    assert success is True
    assert service.get_agent(agent.id) is None

def test_conversation_flow(session):
    service = AgentService(session)
    owner_id = "user_123"
    
    # Setup Agent
    agent = service.create_agent(AgentCreate(
        name="ChatBot", 
        system_prompt="Hi",
        scope="USER"
    ), owner_id)
    
    # Start Conversation
    conv_data = ConversationCreate(agent_id=agent.id, title="My Chat")
    conv = service.create_conversation(conv_data, user_id=owner_id)
    
    assert conv.id is not None
    assert conv.agent_id == agent.id
    assert conv.title == "My Chat"
    
    # Add User Message
    msg1 = service.add_message(conv.id, MessageCreate(role="user", content="Hello"))
    assert msg1.role == "user"
    assert msg1.content == "Hello"
    
    # Add Assistant Message
    msg2 = service.add_message(conv.id, MessageCreate(role="assistant", content="Hi there"))
    
    # Get History
    history = service.get_conversation_history(conv.id)
    assert len(history) == 2
    assert history[0].role == "user"
    assert history[1].role == "assistant"
    
    # Check timestamps roughly order
    assert history[0].created_at <= history[1].created_at

def test_tool_message_storage(session):
    service = AgentService(session)
    owner_id = "user_123"
    agent = service.create_agent(AgentCreate(
        name="ToolBot", 
        system_prompt="Hi",
    ), owner_id)
    conv = service.create_conversation(ConversationCreate(agent_id=agent.id), user_id=owner_id)
    
    # Tool Call from Assistant
    tool_call_data = [{"id": "call_1", "type": "function", "function": {"name": "test_tool", "arguments": "{}"}}]
    msg_ask = service.add_message(conv.id, MessageCreate(
        role="assistant", 
        content=None, # Standard if just tool call, but schema allows str
        tool_calls=tool_call_data
    ))
    
    # Tool Output
    msg_out = service.add_message(conv.id, MessageCreate(
        role="tool",
        content="Result",
        tool_calls=[{"tool_call_id": "call_1"}] # Storing generic JSON
    ))
    
    history = service.get_conversation_history(conv.id)
    assert len(history) == 2
    # Ensure tool message is present
    tool_msgs = [m for m in history if m.role == "tool"]
    assert len(tool_msgs) == 1
    assert tool_msgs[0].content == "Result"

@pytest.mark.skip(reason="Environment issues with async loop in test runner")
def test_agent_brain_flow(session):
    # Test AgentBrain logic with mocked LLM provider
    from unittest.mock import MagicMock, patch, AsyncMock
    from orgmind.agents.llm import AgentBrain, OpenAIProvider
    
    service = AgentService(session)
    owner_id = "user_123"
    agent = service.create_agent(AgentCreate(name="BrainBot", system_prompt="Hi"), owner_id)
    conv = service.create_conversation(ConversationCreate(agent_id=agent.id), user_id=owner_id)
    service.add_message(conv.id, MessageCreate(role="user", content="Hello"))
    
    # Mock Provider
    with patch("orgmind.agents.llm.OpenAIProvider") as MockProvider:
        mock_instance = MockProvider.return_value
        
        # Mock Response
        mock_msg = MagicMock()
        mock_msg.content = "Hi there!"
        mock_msg.tool_calls = None
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        
        mock_instance.chat_completion.return_value = mock_resp
        
        # Init Brain
        brain = AgentBrain(service)
        # Verify provider is mocked
        brain.provider = mock_instance
        
        # Call Process (Async)
        import asyncio
        import sys
        
        # Use existing loop if available (e.g. pytest-asyncio) or new one
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        msg = loop.run_until_complete(brain.process(agent, conv.id))
        
        assert msg.role == "assistant"
        assert msg.content == "Hi there!"
        
        # Verify history
        history = service.get_conversation_history(conv.id)
        assert len(history) == 2 # User + Assistant
