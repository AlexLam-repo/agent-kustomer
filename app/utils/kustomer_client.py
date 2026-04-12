import logging
import httpx
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class KustomerClient:
    @property
    def _headers(self):
        return {
            "Authorization": f"Bearer {settings.kustomer_api_key}",
            "Content-Type": "application/json",
        }

    async def send_message(self, conversation_id: str, body: str) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{settings.kustomer_base_url}/v1/conversations/{conversation_id}/messages",
                json={"body": body, "direction": "out", "channel": "chat",
                      "meta": {"automatedResponse": True}},
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def get_customer(self, customer_id: str) -> dict:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{settings.kustomer_base_url}/v1/customers/{customer_id}",
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()


kustomer_client = KustomerClient()
