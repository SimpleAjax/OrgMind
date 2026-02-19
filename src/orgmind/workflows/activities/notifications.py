from temporalio import activity

class NotificationActivities:
    @activity.defn
    async def send_slack_notification(self, channel: str, message: str) -> None:
        # Mock implementation for now
        activity.logger.info(f"Sending Slack message to {channel}: {message}")
        print(f"[MOCK] Slack to {channel}: {message}")

    @activity.defn
    async def send_email_activity(self, to: str, subject: str, body: str) -> None:
        # Mock implementation for now
        activity.logger.info(f"Sending Email to {to}: {subject}")
        print(f"[MOCK] Email to {to}: {subject}\n{body}")
