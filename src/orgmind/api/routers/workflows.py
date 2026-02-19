from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from temporalio.client import Client, WorkflowExecutionStatus

from orgmind.api.dependencies import get_temporal_client

router = APIRouter()

# -----------------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------------

class StartWorkflowRequest(BaseModel):
    workflow_name: str
    args: List[Any] = []
    task_queue: str = "default-queue"
    workflow_id: Optional[str] = None
    
class SignalWorkflowRequest(BaseModel):
    signal_name: str
    args: List[Any] = []

class WorkflowStatusResponse(BaseModel):
    workflow_id: str
    run_id: str
    status: str
    result: Optional[Any] = None

# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@router.post("/start", status_code=status.HTTP_201_CREATED)
async def start_workflow(
    request: StartWorkflowRequest,
    client: Client = Depends(get_temporal_client)
):
    """Start a new workflow execution."""
    try:
        # We use execute_workflow to wait for result? No, start_workflow is async (fire and forget / returns handle)
        # But for API usually we want to return the ID.
        handle = await client.start_workflow(
            request.workflow_name,
            args=request.args,
            id=request.workflow_id, # If None, Temporal generates UUID
            task_queue=request.task_queue,
        )
        return {"workflow_id": handle.id, "run_id": handle.run_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{workflow_id}/signal", status_code=status.HTTP_200_OK)
async def signal_workflow(
    workflow_id: str,
    request: SignalWorkflowRequest,
    client: Client = Depends(get_temporal_client)
):
    """Send a signal to a running workflow."""
    try:
        handle = client.get_workflow_handle(workflow_id)
        await handle.signal(request.signal_name, *request.args)
        return {"message": "Signal sent"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{workflow_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_workflow(
    workflow_id: str,
    client: Client = Depends(get_temporal_client)
):
    """Cancel a running workflow."""
    try:
        handle = client.get_workflow_handle(workflow_id)
        await handle.cancel()
        return {"message": "Cancellation requested"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{workflow_id}", response_model=WorkflowStatusResponse)
async def get_workflow_status(
    workflow_id: str,
    client: Client = Depends(get_temporal_client)
):
    """Get the status of a workflow."""
    # Getting status in Temporal is a bit tricky via Client if we don't have the RunID.
    # We can use describe().
    try:
        handle = client.get_workflow_handle(workflow_id)
        desc = await handle.describe()
        
        status_str = "UNKNOWN"
        if desc.status == WorkflowExecutionStatus.RUNNING:
            status_str = "RUNNING"
        elif desc.status == WorkflowExecutionStatus.COMPLETED:
            status_str = "COMPLETED"
        elif desc.status == WorkflowExecutionStatus.FAILED:
            status_str = "FAILED"
        elif desc.status == WorkflowExecutionStatus.CANCELED:
            status_str = "CANCELED"
        elif desc.status == WorkflowExecutionStatus.TERMINATED:
            status_str = "TERMINATED"
        elif desc.status == WorkflowExecutionStatus.CONTINUED_AS_NEW:
            status_str = "CONTINUED_AS_NEW"
        elif desc.status == WorkflowExecutionStatus.TIMED_OUT:
            status_str = "TIMED_OUT"
            
        result = None
        # If completed, we might want the result? 
        # But retrieving result requires replaying or prior fetch.
        # Handle.result() waits. We probably don't want to wait here.
        # So we just return status.
            
        return WorkflowStatusResponse(
            workflow_id=desc.id,
            run_id=desc.run_id,
            status=status_str,
            result=result
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Workflow not found or error: {e}")
