import pytest
from temporalio.testing import WorkflowEnvironment

from orgmind.workflows.definitions.onboarding import EmployeeOnboardingWorkflow

from temporalio import activity

# Mock Activities because we don't want to hit real DB in unit tests
@activity.defn(name="create_object_activity")
async def mock_create_object_activity(input):
    return "obj_mock_123"

@activity.defn(name="link_objects_activity")
async def mock_link_objects_activity(input):
    return None

@activity.defn(name="send_email_activity")
async def mock_send_email_activity(to, subject, body):
    return None

from temporalio.worker import Worker

@pytest.mark.asyncio
async def test_employee_onboarding_workflow():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-queue",
            workflows=[EmployeeOnboardingWorkflow],
            activities=[
                mock_create_object_activity,
                mock_link_objects_activity,
                mock_send_email_activity
            ],
        ):
            
            # Note: We need to register activities with the SAME names 
            # if we are not using the function reference directly in the workflow code.
            # But wait, our workflow uses string names...
            # "create_object_activity", "link_objects_activity", "send_email_activity"
            
            # Temporal testing environment allows registering mocks but they strictly
            # need to match the name used in `workflow.execute_activity`. 
            # Since we defined them as separate functions, let's ensure the names match.
            # The name of the function is used by default.
            
            # IMPORTANT: The workflow calls "create_object_activity", "link_objects_activity", "send_email_activity".
            # Our mock functions above are named exactly that (with 'mock_' prefix removal needed 
            # or manual name override).
            # The easiest way is to name the mock functions exactly as expected, 
            # or pass name=... to @activity.defn if we were using decorators.
            
            # However, for pure unit testing without decorators, we can just name 
            # the python functions correctly.
            
            await env.client.execute_workflow(
                EmployeeOnboardingWorkflow.run,
                args=["Alice", "alice@example.com", "Engineering"],
                id="test-workflow-id",
                task_queue="test-queue",
            )
            # If execution completes without error, the flow logic is valid.
