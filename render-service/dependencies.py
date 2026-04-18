from fastapi import Depends, HTTPException, Request
from render_service.services.auth_client import get_auth_client


async def get_current_user(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    
    token = auth_header.split(" ", 1)[1]
    auth_client = get_auth_client()
    user = await auth_client.verify_token(token)
    
    if not user:
        raise HTTPException(status_code=401, detail="Невалидный токен")
    
    return user
