import sys
import os

# Add src to path explicitly
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../src"))
if src_path not in sys.path:
    sys.path.append(src_path)

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import json

# Import dependencies first to ensure initialization order
from orgmind.api.dependencies import get_db, get_current_user

from fastapi import FastAPI, APIRouter
from orgmind.api.routers.agents import router as agents_router
from orgmind.storage.models import Base
from orgmind.agents.schemas import AgentCreate, MessageCreate

app = FastAPI()
api_router = APIRouter(prefix="/api/v1")
api_router.include_router(agents_router)
app.include_router(api_router)

# DB Setup
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

from types import SimpleNamespace

def override_get_current_user():
    return SimpleNamespace(id="user_test", email="test@example.com")

client = TestClient(app)

@pytest.fixture(scope="function", autouse=True)
def setup_module():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    yield
    app.dependency_overrides = {}
    Base.metadata.drop_all(bind=engine)

def test_full_chat_flow():
    # 1. Create Agent
    resp = client.post("/api/v1/agents", json={
        "name": "Chat Bot",
        "description": "Test",
        "system_prompt": "You are a test bot.",
        "scope": "USER"
    })
    if resp.status_code != 201:
        print(f"Error Response: {resp.text}")
    assert resp.status_code == 201
    agent_id = resp.json()["id"]
    
    # 2. Start Conversation
    resp = client.post(f"/api/v1/agents/{agent_id}/conversations", json={
        "title": "Integration Test Chat"
    })
    assert resp.status_code == 201
    conv_id = resp.json()["id"]
    
    # 3. Send Message (Mock LLM)
    with patch("orgmind.agents.llm.OpenAIProvider") as MockProvider, \
         patch("orgmind.agents.llm.MemoryStore") as MockMemory, \
         patch("orgmind.agents.llm.ContextBuilder") as MockContext:
        
        # Mock Memory/Context
        MockMemory.return_value.initialize = AsyncMock()
        MockMemory.return_value.add_memory = AsyncMock()
        MockMemory.return_value.search_memory = AsyncMock(return_value=[])
        MockContext.return_value.get_context = AsyncMock(return_value="")

        mock_instance = MockProvider.return_value
        
        # Mock Response
        mock_message = MagicMock()
        mock_message.content = "Hello, how can I help?"
        mock_message.tool_calls = None
        
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        
        mock_instance.chat_completion.return_value = mock_response
        
        # Execute
        resp = client.post(f"/api/v1/agents/{agent_id}/conversations/{conv_id}/messages", json={
            "role": "user",
            "content": "Hi!"
        })
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "assistant"
        assert data["content"] == "Hello, how can I help?"

def test_tool_execution_flow():
    # 1. Create Agent
    resp = client.post("/api/v1/agents", json={
        "name": "Tool Bot",
        "description": "Test",
        "system_prompt": "You use tools.",
        "scope": "USER"
    })
    agent_id = resp.json()["id"]
    
    # 2. Start Conversation
    resp = client.post(f"/api/v1/agents/{agent_id}/conversations", json={
        "title": "Tool Test Chat"
    })
    conv_id = resp.json()["id"]
    
    # 3. Send Message with Tool Call
    with patch("orgmind.agents.llm.OpenAIProvider") as MockProvider, \
         patch("orgmind.agents.llm.MemoryStore") as MockMemory, \
         patch("orgmind.agents.llm.ContextBuilder") as MockContext:
        
        # Mock Memory/Context
        MockMemory.return_value.initialize = AsyncMock()
        MockMemory.return_value.add_memory = AsyncMock()
        MockMemory.return_value.search_memory = AsyncMock(return_value=[])
        MockContext.return_value.get_context = AsyncMock(return_value="")

        mock_instance = MockProvider.return_value
        
        # Response 1: Tool Call
        call_msg = MagicMock()
        call_msg.content = None
        tc = MagicMock()
        tc.id = "call_abc"
        tc.type = "function"
        tc.function.name = "query_objects"
        tc.function.arguments = json.dumps({"query": "Project X"})
        call_msg.tool_calls = [tc]
        
        resp1 = MagicMock()
        resp1.choices = [MagicMock(message=call_msg)]
        
        # Response 2: Final Answer
        final_msg = MagicMock()
        final_msg.content = "I found Project X."
        final_msg.tool_calls = None
        
        resp2 = MagicMock()
        resp2.choices = [MagicMock(message=final_msg)]
        
        mock_instance.chat_completion.side_effect = [resp1, resp2]
        
        # Execute
        resp = client.post(f"/api/v1/agents/{agent_id}/conversations/{conv_id}/messages", json={
            "role": "user",
            "content": "Find Project X"
        })
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "I found Project X."
        
        # Verify 2 calls to LLM
        assert mock_instance.chat_completion.call_count == 2

if __name__ == "__main__":
    # Manual setup for debugging
    try:
        print("Running setup...")
        Base.metadata.create_all(bind=engine)
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user
        
        print("Running test_full_chat_flow...")
        test_full_chat_flow()
        print("PASS: test_full_chat_flow")
        
        print("Running test_tool_execution_flow...")
        test_tool_execution_flow()
        print("PASS: test_tool_execution_flow")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        app.dependency_overrides = {}
        Base.metadata.drop_all(bind=engine)
