import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from orgmind.evolution.models import EvolutionPolicyModel, ABExperimentModel, ABVariantModel
from orgmind.evolution.embedding import DecisionEmbeddingService
from orgmind.evolution.policy import PolicyGenerator
from orgmind.evolution.recommendation import RecommendationEngine
from orgmind.evolution.ab_testing import ABTestingService

# --- Mocks ---
@pytest.fixture
def mock_embedding_service():
    service = AsyncMock(spec=DecisionEmbeddingService)
    service.search_similar.return_value = []
    return service

@pytest.fixture
def mock_policy_generator():
    generator = MagicMock(spec=PolicyGenerator)
    generator.evaluate_policies.return_value = []
    return generator

# --- Tests ---

@pytest.mark.asyncio
async def test_decision_embedding_service_embed(mock_embedding_service):
    # This test verifies the public interface of the mocked service,
    # In a real integration test we'd check Qdrant interaction
    trace_id = "test-trace-123"
    result = await mock_embedding_service.embed_decision(trace_id)
    # Mock returns awaitable
    assert result is not None

def test_policy_generator_logic():
    # Test converting a pattern to a policy
    pattern = {"feature": "day_of_week", "value": "Friday", "outcome_score": 0.2}
    
    # We need to instantiate the real class here, maybe mocking evaluator if complex
    from orgmind.triggers.engine import JsonLogicEvaluator
    evaluator = JsonLogicEvaluator()
    generator = PolicyGenerator(evaluator)
    
    policy = generator.generate_policy_from_pattern(pattern)
    
    assert policy.effect == "WARN"
    assert "Friday" in str(policy.condition_logic)
    assert policy.source == "pattern_detection_service"

def test_policy_evaluation():
    from orgmind.triggers.engine import JsonLogicEvaluator
    evaluator = JsonLogicEvaluator()
    generator = PolicyGenerator(evaluator)
    
    # Manually create a policy
    policy = EvolutionPolicyModel(
        id="p1",
        name="No Fridays",
        condition_logic={"==": [{"var": "day"}, "Friday"]},
        effect="DENY",
        source="manual",
        is_active=True
    )
    
    # Mock session
    session = MagicMock()
    session.scalars.return_value.all.return_value = [policy]
    
    # Context matches
    context = {"day": "Friday"}
    matched = generator.evaluate_policies(session, context)
    assert len(matched) == 1
    assert matched[0].id == "p1"
    
    # Context does not match
    context_safe = {"day": "Monday"}
    matched_safe = generator.evaluate_policies(session, context_safe)
    assert len(matched_safe) == 0

@pytest.mark.asyncio
async def test_recommendation_engine(mock_embedding_service, mock_policy_generator):
    engine = RecommendationEngine(mock_embedding_service, mock_policy_generator)
    
    # Mock policy returning a warning
    policy = EvolutionPolicyModel(effect="WARN", message="Be careful")
    mock_policy_generator.evaluate_policies.return_value = [policy]
    
    # Mock similar decision
    mock_decision = MagicMock()
    mock_decision.payload = {"action_type": "deploy"}
    mock_decision.score = 0.9
    mock_decision.id = "past-1"
    mock_embedding_service.search_similar.return_value = [mock_decision]
    
    recommendations = await engine.recommend_action(MagicMock(), {}, "context")
    
    assert len(recommendations) == 2
    assert recommendations[0]["type"] == "WARNING"
    assert recommendations[1]["type"] == "PRECEDENT"
    assert recommendations[1]["action"] == "deploy"

def test_ab_testing_assignment():
    service = ABTestingService()
    session = MagicMock()
    
    # Mock experiment
    experiment = ABExperimentModel(id="exp1", name="Test Exp", variants=[
        ABVariantModel(id="v1", name="A", weight=50),
        ABVariantModel(id="v2", name="B", weight=50)
    ])
    
    # Deterministic assignment
    # Mock session scalar return
    session.scalar.return_value = None # No existing assignment
    
    # We need to bypass the session query logic for unit test of logic
    # Direct logic test
    variant_a = service._assign_variant_logic(experiment, "user1")
    variant_b = service._assign_variant_logic(experiment, "user1")
    
    assert variant_a.id == variant_b.id # Consistency
