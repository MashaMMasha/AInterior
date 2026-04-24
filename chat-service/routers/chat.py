from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import httpx
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from chat_service.database import get_db_session
from chat_service.dependencies import get_current_user
from chat_service.services.chat_service import ChatService
from chat_service.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None  # id сессии чата; если нет — создаётся новая сессия


class ChatResponse(BaseModel):
    interaction_id: int
    conversation_id: str
    status: str
    timestamp: str


class ConversationResponse(BaseModel):
    conversation_id: str
    title: str
    created_at: str
    message_count: int


@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Отправить сообщение в чат и запустить генерацию"""
    try:
        chat_service = ChatService()
        
        if request.conversation_id:
            session = await chat_service.get_session(db, request.conversation_id)
            if not session or session.user_id != user["id"]:
                raise HTTPException(status_code=404, detail="Conversation not found")
            session_id = session.id
        else:
            # Нет привязки — новая сессия (другой проект / кнопка «новый чат»)
            new_session = await chat_service.start_session(db, user["id"])
            session_id = new_session.id
        
        # Вызываем agents-service для запуска процесса генерации
        async with httpx.AsyncClient() as client:
            try:
                payload = {
                    "query": request.message,
                    "user_id": user["id"],
                    "session_id": session_id  # Всегда передаём session_id
                }
                
                agents_base = settings.AGENTS_SERVICE_URL.rstrip("/")
                response = await client.post(
                    f"{agents_base}/generate",
                    json=payload,
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()
            except httpx.RequestError as e:
                logger.error(f"Failed to call agents-service: {e}")
                raise HTTPException(status_code=503, detail="Agents service unavailable")
            except httpx.HTTPStatusError as e:
                logger.error(f"Agents service returned error: {e.response.text}")
                raise HTTPException(status_code=e.response.status_code, detail="Agents service error")

        return ChatResponse(
            interaction_id=data["interaction_id"],
            conversation_id=session_id,  # Используем session_id который мы определили
            status=data["status"],
            timestamp=datetime.utcnow().isoformat()
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error processing message")
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")


@router.get("/conversations", response_model=List[ConversationResponse])
async def get_conversations(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Получить список бесед пользователя"""
    try:
        chat_service = ChatService()
        sessions = await chat_service.list_sessions(db, user["id"])
        
        response = []
        for session in sessions:
            title = session.interactions[0].query[:50] if session.interactions else "Новая беседа"
            response.append(ConversationResponse(
                conversation_id=session.id,
                title=title,
                created_at=session.created_at.isoformat(),
                message_count=len(session.interactions)
            ))
        
        return response
    
    except Exception as e:
        logger.exception("Error fetching conversations")
        raise HTTPException(status_code=500, detail=f"Error fetching conversations: {str(e)}")


@router.get("/conversation/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Получить все сообщения беседы (включая стадии)"""
    try:
        chat_service = ChatService()
        session = await chat_service.get_session(db, conversation_id)
        
        if not session or session.user_id != user["id"]:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        messages = []
        for interaction in session.interactions:
            messages.append({
                "interaction_id": interaction.id,
                "role": "user",
                "content": interaction.query,
                "created_at": interaction.created_at.isoformat(),
                "stages": [
                    {
                        "stage_name": stage.stage_name,
                        "scene_plan": stage.scene_plan,
                        "created_at": stage.created_at.isoformat()
                    }
                    for stage in interaction.stages
                ]
            })
            
        return messages
    
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error fetching messages")
        raise HTTPException(status_code=500, detail=f"Error fetching messages: {str(e)}")
