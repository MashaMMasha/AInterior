import httpx
from typing import Optional
from ml_service.config import settings


class AuthClient:
    def __init__(self, base_url: str = None):
        self.base_url = base_url or settings.AUTH_SERVICE_URL
        self.client = httpx.AsyncClient(timeout=10.0)
    
    async def verify_token(self, token: str) -> Optional[dict]:
        try:
            response = await self.client.post(
                f"{self.base_url}/auth/verify-token",
                headers={"Authorization": f"Bearer {token}"}
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("user")
            return None
        except Exception:
            return None
    
    async def close(self):
        await self.client.aclose()


_auth_client = None


def get_auth_client() -> AuthClient:
    global _auth_client
    if _auth_client is None:
        _auth_client = AuthClient()
    return _auth_client
