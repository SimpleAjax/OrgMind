import httpx
import logging
from typing import Optional, Dict, Any

from orgmind.platform.config import settings

logger = logging.getLogger(__name__)

class SlackService:
    """
    Client for interacting with Slack API using httpx.
    """
    
    def __init__(self, token: Optional[str] = None):
        self.token = token or settings.SLACK_BOT_TOKEN
        self.api_url = settings.SLACK_API_URL
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json; charset=utf-8"
        }

    async def _post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Helper to make POST requests to Slack API."""
        if not self.token:
            logger.warning("Slack token is not configured. Skipping API call.")
            return {"ok": False, "error": "not_configured"}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.api_url}/{endpoint}",
                    json=data,
                    headers=self.headers
                )
                response.raise_for_status()
                res_data = response.json()
                
                if not res_data.get("ok"):
                    logger.error(f"Slack API error: {res_data.get('error')} for {endpoint}")
                
                return res_data
            except Exception as e:
                logger.error(f"Failed to call Slack API {endpoint}: {e}")
                return {"ok": False, "error": str(e)}

    async def send_message(self, channel: str, text: str, thread_ts: Optional[str] = None) -> bool:
        """Send a message to a channel."""
        payload = {"channel": channel, "text": text}
        if thread_ts:
            payload["thread_ts"] = thread_ts
            
        result = await self._post("chat.postMessage", payload)
        return result.get("ok", False)

    async def open_im(self, user_id: str) -> Optional[str]:
        """Open a DM with a user and return the channel ID."""
        result = await self._post("conversations.open", {"users": user_id})
        if result.get("ok"):
            return result.get("channel", {}).get("id")
        return None

    async def lookup_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Find a user by email."""
        # This is a GET request usually but POST with x-www-form-urlencoded works too, 
        # but let's check doc. users.lookupByEmail supports GET/POST.
        # However, for httpx client used above (json post), simpler to reimplement if needed or try post.
        # The docs say GET is preferred usually but POST works.
        pass # Placeholder for now as Nudge logic might need it later.

    async def send_dm(self, user_id: str, text: str) -> bool:
        """Send a direct message to a user."""
        channel_id = await self.open_im(user_id)
        if channel_id:
            return await self.send_message(channel_id, text)
        return False
