from datetime import timedelta
from temporalio import workflow

# Import activity definitions. In Temporal, we usually import the interface/functions
# but for Type Checking we might need the classes if using class-based activities.
# However, standard practice is to use string names or function references.
# We will use string names here for loose coupling or better yet, duplicate the
# signature in an interface if we want strict typing, but for MVP we'll just refer
# by name or assume the worker has them registered.

# Best practice: "Activities" are just functions. If we used class based,
# we invoke methods. Let's assume we registers an instance of OntologyActivities
# and NotificationActivities.

@workflow.defn
class EmployeeOnboardingWorkflow:
    def __init__(self) -> None:
        self.approved = False

    @workflow.signal
    def approve_onboarding(self) -> None:
        self.approved = True

    @workflow.run
    async def run(self, employee_name: str, employee_email: str, department: str) -> str:
        # 1. Create Employee Object
        employee_id = await workflow.execute_activity(
            "create_object_activity",
            args=[{
                "object_type_name": "Employee",
                "properties": {
                    "name": employee_name,
                    "email": employee_email,
                    "department": department
                }
            }],
            start_to_close_timeout=timedelta(seconds=10)
        )

        # 2. Create IT Account
        it_account_id = await workflow.execute_activity(
            "create_object_activity",
            args=[{
                "object_type_name": "ITAccount",
                "properties": {
                    "username": employee_email.split('@')[0],
                    "status": "Pending" # Changed from Active to Pending until approved
                }
            }],
            start_to_close_timeout=timedelta(seconds=10)
        )

        # 3. Link Employee -> IT Account
        await workflow.execute_activity(
            "link_objects_activity",
            args=[{
                "source_id": employee_id,
                "target_id": it_account_id,
                "link_type_name": "HAS_ACCOUNT",
                "properties": {}
            }],
            start_to_close_timeout=timedelta(seconds=10)
        )

        # 3.5 Wait for Approval Signal
        # In a real scenario, we might want to notify someone that approval is pending.
        # Here we just wait.
        await workflow.wait_condition(lambda: self.approved)

        # 3.6 Update IT Account to Active (Optional step, skipping for MVP simplicity but would be logical)
        # For now we assume approval means we proceed to send email.

        # 4. Send Welcome Email
        await workflow.execute_activity(
            "send_email_activity",
            args=[
                employee_email, 
                "Welcome to OrgMind!", 
                f"Hi {employee_name}, your account is ready and approved."
            ],
            start_to_close_timeout=timedelta(seconds=10)
        )

        return employee_id
