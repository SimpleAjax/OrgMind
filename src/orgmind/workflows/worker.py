
import asyncio
from temporalio.worker import Worker

from orgmind.platform.config import settings
from orgmind.workflows.client import get_temporal_client
from orgmind.workflows.activities.ontology import OntologyActivities
from orgmind.workflows.activities.notifications import NotificationActivities
from orgmind.workflows.definitions.onboarding import EmployeeOnboardingWorkflow

async def run_worker() -> None:
    client = await get_temporal_client()

    # Instantiate activities (to register instance methods)
    # Note: Temporal activities can be functions or class methods.
    # Our implementation uses class methods effectively as functions,
    # but we need to register the specific callables.
    
    ontology_activities = OntologyActivities()
    await ontology_activities.connect()
    
    notification_activities = NotificationActivities()

    worker = Worker(
        client,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
        workflows=[EmployeeOnboardingWorkflow],
        activities=[
            ontology_activities.create_object_activity,
            ontology_activities.update_object_activity,
            ontology_activities.link_objects_activity,
            notification_activities.send_slack_notification,
            notification_activities.send_email_activity,
        ],
    )

    print(f"Worker started on queue: {settings.TEMPORAL_TASK_QUEUE}")
    await worker.run()

if __name__ == "__main__":
    asyncio.run(run_worker())
