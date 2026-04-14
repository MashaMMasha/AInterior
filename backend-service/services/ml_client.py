import httpx
from backend_service.config import settings


class MLClient:
    def __init__(self, base_url: str = None):
        self.base_url = base_url or settings.ML_SERVICE_URL
        self.client = httpx.AsyncClient(timeout=60.0)
    
    async def generate_furniture(self, text: str, style: str = "modern"):
        response = await self.client.post(
            f"{self.base_url}/generate_furniture",
            json={"text": text, "style": style}
        )
        response.raise_for_status()
        return response.json()
    
    async def auto_arrange(self, text: str, style: str = "modern"):
        response = await self.client.post(
            f"{self.base_url}/auto_arrange",
            json={"text": text, "style": style}
        )
        response.raise_for_status()
        return response.json()
    
    async def chat(self, text: str):
        response = await self.client.post(
            f"{self.base_url}/chat",
            json={"text": text}
        )
        response.raise_for_status()
        return response.json()
    
    async def generate_scene(self, text: str):
        response = await self.client.post(
            f"{self.base_url}/generate_scene",
            json={"text": text}
        )
        response.raise_for_status()
        return response.json()
    
    async def get_generation_status(self, generation_id: str):
        response = await self.client.get(
            f"{self.base_url}/generation/{generation_id}"
        )
        return response
    
    async def close(self):
        await self.client.aclose()


_ml_client = None


def get_ml_client() -> MLClient:
    global _ml_client
    if _ml_client is None:
        _ml_client = MLClient()
    return _ml_client
