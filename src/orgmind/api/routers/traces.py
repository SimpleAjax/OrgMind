from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from orgmind.api.dependencies import get_postgres_adapter, get_llm_provider
from orgmind.storage.postgres_adapter import PostgresAdapter
from orgmind.agents.llm import OpenAIProvider
from orgmind.engine.inference_engine import InferenceEngine
from orgmind.engine.suggestion_generator import SuggestionGenerator
from orgmind.storage.models_traces import DecisionTraceModel, ContextSuggestionModel

router = APIRouter()

# --- Pydantic Schemas ---

class SuggestionResponse(BaseModel):
    id: str
    trace_id: str
    suggestion_text: str
    source: str
    confidence: float
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class SuggestionFeedbackRequest(BaseModel):
    status: str # accepted, rejected

# --- Endpoints ---

@router.post("/{trace_id}/suggestions", response_model=List[SuggestionResponse])
def generate_suggestions(
    trace_id: str,
    postgres: PostgresAdapter = Depends(get_postgres_adapter),
    llm: OpenAIProvider = Depends(get_llm_provider)
):
    """
    Run inference engine + AI suggestion generator for a specific trace.
    Returns existing suggestions if any, or generates new ones.
    """
    engine = InferenceEngine(postgres)
    generator = SuggestionGenerator(llm)
    
    # 1. Run deterministic inference
    try:
        engine.evaluate_trace(trace_id)
    except Exception as e:
        # Log error but continue to AI
        print(f"Inference engine error: {e}")
        pass
        
    with postgres.get_session() as session:
        existing_suggestions = session.query(ContextSuggestionModel).filter_by(trace_id=trace_id).all()
        return [SuggestionResponse.model_validate(s) for s in existing_suggestions]

@router.post("/{trace_id}/suggestions/ai", response_model=SuggestionResponse)
async def generate_ai_suggestion(
    trace_id: str,
    postgres: PostgresAdapter = Depends(get_postgres_adapter),
    llm: OpenAIProvider = Depends(get_llm_provider)
):
    """
    Explicitly trigger AI suggestion generation.
    """
    generator = SuggestionGenerator(llm)
    
    with postgres.get_session() as session:
        trace = session.query(DecisionTraceModel).filter_by(id=trace_id).first()
        if not trace:
            raise HTTPException(status_code=404, detail="Trace not found")
        
        snapshot = None
        if trace.snapshot_id:
             snapshot = trace.snapshot 
        
        suggestion_text = await generator.generate_suggestion(trace, snapshot)
        
        if not suggestion_text:
             raise HTTPException(status_code=500, detail="Failed to generate suggestion")
             
        # Save it
        import uuid
        suggestion = ContextSuggestionModel(
            id=str(uuid.uuid4()),
            trace_id=trace_id,
            suggestion_text=suggestion_text,
            source="ai:llm",
            confidence=0.8,
            status="pending"
        )
        session.add(suggestion)
        session.commit()
        session.refresh(suggestion)
        return SuggestionResponse.model_validate(suggestion)


@router.patch("/suggestions/{suggestion_id}/feedback", response_model=SuggestionResponse)
def update_suggestion_feedback(
    suggestion_id: str,
    feedback: SuggestionFeedbackRequest,
    postgres: PostgresAdapter = Depends(get_postgres_adapter)
):
    """
    Accept or reject a suggestion.
    """
    if feedback.status not in ["accepted", "rejected", "pending"]:
        raise HTTPException(status_code=400, detail="Invalid status")
        
    with postgres.get_session() as session:
        suggestion = session.query(ContextSuggestionModel).filter_by(id=suggestion_id).first()
        if not suggestion:
            raise HTTPException(status_code=404, detail="Suggestion not found")
            
        suggestion.status = feedback.status
        session.commit()
        session.refresh(suggestion)
        return SuggestionResponse.model_validate(suggestion)

@router.get("/{trace_id}/suggestions", response_model=List[SuggestionResponse])
def get_suggestions(
    trace_id: str,
    postgres: PostgresAdapter = Depends(get_postgres_adapter)
):
    with postgres.get_session() as session:
         suggestions = session.query(ContextSuggestionModel).filter_by(trace_id=trace_id).all()
         return [SuggestionResponse.model_validate(s) for s in suggestions]
