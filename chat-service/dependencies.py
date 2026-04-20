from chat_service.services.auth_client import get_auth_client
from fastapi import HTTPException, Request


async def get_current_user(request: Request):
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    
    token = auth_header.replace("Bearer ", "")
    
    auth_client = get_auth_client()
    user = await auth_client.verify_token(token)
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return user
