from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query
from backend_service.services.rabbitmq_service import get_rabbitmq_service
from backend_service.services.ml_client import MLClient
from backend_service.services.auth_client import get_auth_client
import json
import asyncio

router = APIRouter(prefix="/ws", tags=["websocket"])

ml_client = MLClient()
rabbitmq = get_rabbitmq_service()


@router.websocket("/generation/{generation_id}")
async def generation_stream(websocket: WebSocket, generation_id: str, token: str = Query(...)):
    auth_client = get_auth_client()
    user = await auth_client.verify_token(token)
    
    if not user:
        await websocket.close(code=1008, reason="Unauthorized")
        return
    
    await websocket.accept()
    
    try:
        status_response = await ml_client.get_generation_status(generation_id)
        
        if status_response.status_code == 404:
            await websocket.send_json({"error": "Generation not found"})
            await websocket.close()
            return
        
        status_data = status_response.json()
        
        if status_data.get('user_id') != user["id"]:
            await websocket.send_json({"error": "Access denied"})
            await websocket.close()
            return
        
        await websocket.send_json({
            "type": "initial",
            "data": status_data
        })
        
        if status_data['status'] in ['completed', 'failed']:
            await websocket.close()
            return
        
        async def message_callback(data):
            await websocket.send_json({
                "type": "progress",
                "data": data
            })
        
        await rabbitmq.subscribe_to_generation(generation_id, message_callback)
        
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"error": str(e)})
    finally:
        try:
            await websocket.close()
        except:
            pass
