from fastapi import APIRouter, Depends, Request
from backend_service.schema.dto import TextRequest
from backend_service.services.ml_client import get_render_client
from backend_service.dependencies import get_current_user

router = APIRouter(prefix="", tags=["render"])


@router.post("/generate_furniture")
async def generate_furniture(req: TextRequest, request: Request, user: dict = Depends(get_current_user)):
    render_client = get_render_client()
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    return await render_client.generate_furniture(req.text, req.style, token)


@router.post("/auto_arrange")
async def auto_arrange(req: TextRequest, request: Request, user: dict = Depends(get_current_user)):
    render_client = get_render_client()
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    return await render_client.auto_arrange(req.text, req.style, token)


@router.post("/chat")
async def chat(req: TextRequest, request: Request, user: dict = Depends(get_current_user)):
    render_client = get_render_client()
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    return await render_client.chat(req.text, token)


@router.post("/generate")
async def generate(req: TextRequest, request: Request, user: dict = Depends(get_current_user)):
    render_client = get_render_client()
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    return await render_client.generate_furniture(req.text, req.style, token)


@router.post("/generate_scene")
async def generate_scene(req: TextRequest, request: Request, user: dict = Depends(get_current_user)):
    render_client = get_render_client()
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    return await render_client.generate_scene(req.text, token)


@router.get("/generation/{generation_id}")
async def get_generation_status(generation_id: str, request: Request, user: dict = Depends(get_current_user)):
    render_client = get_render_client()
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    response = await render_client.get_generation_status(generation_id, token)
    response.raise_for_status()
    return response.json()
