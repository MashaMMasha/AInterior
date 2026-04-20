import httpx
from backend_service.config import settings


class RenderClient:
    def __init__(self, base_url: str = None):
        self.base_url = base_url or settings.RENDER_SERVICE_URL
        self.client = httpx.AsyncClient(timeout=60.0)
    
    def _get_headers(self, token: str = None):
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers
    
    async def generate_furniture(self, text: str, style: str = "modern", token: str = None):
        response = await self.client.post(
            f"{self.base_url}/generate_furniture",
            json={"text": text, "style": style},
            headers=self._get_headers(token)
        )
        response.raise_for_status()
        return response.json()
    
    async def auto_arrange(self, text: str, style: str = "modern", token: str = None):
        response = await self.client.post(
            f"{self.base_url}/auto_arrange",
            json={"text": text, "style": style},
            headers=self._get_headers(token)
        )
        response.raise_for_status()
        return response.json()
    
    async def chat(self, text: str, token: str = None):
        response = await self.client.post(
            f"{self.base_url}/chat",
            json={"text": text},
            headers=self._get_headers(token)
        )
        response.raise_for_status()
        return response.json()
    
    async def generate_scene(self, text: str, token: str = None):
        response = await self.client.post(
            f"{self.base_url}/generate_scene",
            json={"text": text},
            headers=self._get_headers(token)
        )
        response.raise_for_status()
        return response.json()
    
    async def get_generation_status(self, generation_id: str, token: str = None):
        response = await self.client.get(
            f"{self.base_url}/generation/{generation_id}",
            headers=self._get_headers(token)
        )
        return response
    
    async def close(self):
        await self.client.aclose()


_render_client = None


def get_render_client() -> RenderClient:
    global _render_client
    if _render_client is None:
        _render_client = RenderClient()
    return _render_client
