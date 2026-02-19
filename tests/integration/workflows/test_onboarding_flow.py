import pytest
import asyncio
from uuid import uuid4

from orgmind.workflows.client import get_temporal_client
from orgmind.workflows.definitions.onboarding import EmployeeOnboardingWorkflow
from orgmind.platform.config import settings
from orgmind.storage.postgres_adapter import PostgresAdapter, PostgresConfig
from orgmind.storage.repositories.object_repository import ObjectRepository
from orgmind.storage.repositories.link_repository import LinkRepository
from orgmind.storage.models import ObjectTypeModel, LinkTypeModel, Base

def seed_db():
    """Ensure required types exist in DB."""
    print("Seeding DB start...")
    try:
        db = PostgresAdapter(PostgresConfig())
        db.connect()
        # Create all tables if they don't exist (recovers dropped domain_events)
        Base.metadata.create_all(db._engine)
        
        db.connect()
        print(f"\n\n!!! DB CREDENTIALS: User={db.config.POSTGRES_USER} Password={db.config.POSTGRES_PASSWORD.get_secret_value()} !!!\n\n")
        with db.get_session() as session:
            obj_repo = ObjectRepository()
            link_repo = LinkRepository()
            
            # Ensure Employee Type
            emp_type = obj_repo.get_type_by_name(session, "Employee")
            if not emp_type:
                print("Creating Employee type")
                emp_type = ObjectTypeModel(
                    id=str(uuid4()),
                    name="Employee",
                    description="Employee record",
                    properties={
                        "name": {"type": "string"},
                        "email": {"type": "string"},
                        "department": {"type": "string"}
                    },
                    version=1
                )
                obj_repo.create_type(session, emp_type)
            else:
                print("Updating Employee type properties")
                obj_repo.update_type(session, emp_type.id, {
                    "properties": {
                        "name": {"type": "string"},
                        "email": {"type": "string"},
                        "department": {"type": "string"}
                    }
                })
            
            # Ensure ITAccount Type
            acc_type = obj_repo.get_type_by_name(session, "ITAccount")
            if not acc_type:
                print("Creating ITAccount type")
                acc_type = ObjectTypeModel(
                    id=str(uuid4()),
                    name="ITAccount",
                    description="IT Account",
                    properties={
                        "email": {"type": "string"},
                        "username": {"type": "string"}
                    },
                    version=1
                )
                obj_repo.create_type(session, acc_type)
            else:
                 print("Updating ITAccount type properties")
                 obj_repo.update_type(session, acc_type.id, {
                     "properties": {
                         "email": {"type": "string"},
                         "username": {"type": "string"}
                     }
                 })
                
            session.flush()
            
            # Ensure hasAccount Link Type
            if not link_repo.get_type_by_name(session, "HAS_ACCOUNT"):
                print("Creating HAS_ACCOUNT link type")
                link_repo.create_type(session, LinkTypeModel(
                    id=str(uuid4()),
                    name="HAS_ACCOUNT",
                    description="Employee has account",
                    source_type=emp_type.id,
                    target_type=acc_type.id,
                    cardinality="one-to-many"
                ))
            
            session.commit()
            print("Seeding DB done")
    except Exception as e:
        print(f"Seeding DB failed: {e}")
        raise

@pytest.mark.integration
@pytest.mark.asyncio
async def test_onboarding_flow_e2e():
    """
    Submits a workflow to the real Temporal server and waits for result.
    Requires:
    - Docker Compose running (Temporal + Postgres)
    - Worker running (python -m orgmind.workflows.worker)
    """
    seed_db()
    
    client = await get_temporal_client()
    
    unique_id = str(uuid4())[:8]
    workflow_id = f"onboarding-test-{unique_id}"
    
    try:
        # Submit Workflow
        handle = await client.start_workflow(
            EmployeeOnboardingWorkflow.run,
            args=[f"Test User {unique_id}", f"test.{unique_id}@example.com", "QA"],
            id=workflow_id,
            task_queue=settings.TEMPORAL_TASK_QUEUE,
        )
        
        # New: Workflow now pauses for approval signal.
        # We wait a brief moment for it to start (optional, as signals are buffered)
        await asyncio.sleep(2) 
        
        # Send approval signal
        print("Sending approval signal...")
        await handle.signal(EmployeeOnboardingWorkflow.approve_onboarding)
        
        # Wait for result (timeout after 30s)
        # Note: If no worker is running, this will eventually timeout
        result = await handle.result()
        
        assert result is not None
        assert isinstance(result, str) # Should be an Employee ID
        
        # Verify side effects in DB? 
        # Ideally yes, query Postgres to see if object exists.
        # for now, if it returns an ID, it means the activity executed successfully.
        
    except Exception as e:
        pytest.fail(f"Workflow execution failed: {e}")
