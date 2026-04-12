from fastapi import APIRouter, Depends
from backend_service.schema.dto import TextRequest
from backend_service.services.ml_client import get_ml_client
from backend_service.dependencies import get_current_user

router = APIRouter(prefix="", tags=["ml"])


@router.post("/generate_furniture")
async def generate_furniture(req: TextRequest, user: dict = Depends(get_current_user)):
    ml_client = get_ml_client()
    return await ml_client.generate_furniture(req.text, req.style)


@router.post("/auto_arrange")
async def auto_arrange(req: TextRequest, user: dict = Depends(get_current_user)):
    ml_client = get_ml_client()
    return await ml_client.auto_arrange(req.text, req.style)


@router.post("/chat")
async def chat(req: TextRequest, user: dict = Depends(get_current_user)):
    ml_client = get_ml_client()
    return await ml_client.chat(req.text)


@router.post("/generate")
async def generate(req: TextRequest, user: dict = Depends(get_current_user)):
    ml_client = get_ml_client()
    return await ml_client.generate_furniture(req.text, req.style)
