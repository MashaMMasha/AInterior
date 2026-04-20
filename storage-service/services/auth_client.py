import httpx
from storage_service.config import settings


class AuthClient:
    def __init__(self, base_url: str = None):
        self.base_url = base_url or settings.AUTH_SERVICE_URL
        self.client = httpx.AsyncClient(timeout=10.0)
    
    async def verify_token(self, token: str):
        try:
            response = await self.client.post(
                f"{self.base_url}/auth/verify-token",
                json={"token": token}
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Auth verification failed: {e}")
            return None
    
    async def close(self):
        await self.client.aclose()


_auth_client = None


def get_auth_client() -> AuthClient:
    global _auth_client
    if _auth_client is None:
        _auth_client = AuthClient()
    return _auth_client
