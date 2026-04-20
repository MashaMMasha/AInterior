from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import uuid

from chat_service.database import get_db_session, Conversation, Message
from chat_service.dependencies import get_current_user
from chat_service.mock.responses import get_mock_response, parse_intent

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    message_id: str
    conversation_id: str
    response: str
    intent: dict
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
    """Отправить сообщение в чат (mock ответы)"""
    try:
        # Если нет conversation_id, создаем новую беседу
        if not request.conversation_id:
            conversation = Conversation(
                conversation_id=uuid.uuid4(),
                user_id=user["id"],
                title=request.message[:50]  # Первые 50 символов как заголовок
            )
            db.add(conversation)
            await db.commit()
            await db.refresh(conversation)
            conversation_id = conversation.conversation_id
        else:
            conversation_id = uuid.UUID(request.conversation_id)
            
            # Проверяем что беседа существует и принадлежит пользователю
            result = await db.execute(
                select(Conversation).where(
                    Conversation.conversation_id == conversation_id,
                    Conversation.user_id == user["id"]
                )
            )
            conversation = result.scalar_one_or_none()
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Сохраняем сообщение пользователя
        user_message = Message(
            message_id=uuid.uuid4(),
            conversation_id=conversation_id,
            role="user",
            content=request.message
        )
        db.add(user_message)
        
        # Генерируем mock ответ
        mock_response = get_mock_response(request.message)
        intent = parse_intent(request.message)
        
        # Сохраняем ответ ассистента
        assistant_message = Message(
            message_id=uuid.uuid4(),
            conversation_id=conversation_id,
            role="assistant",
            content=mock_response
        )
        db.add(assistant_message)
        
        # Обновляем время последнего обновления беседы
        await db.execute(
            update(Conversation)
            .where(Conversation.conversation_id == conversation_id)
            .values(updated_at=datetime.utcnow())
        )
        
        await db.commit()
        await db.refresh(assistant_message)
        
        return ChatResponse(
            message_id=str(assistant_message.message_id),
            conversation_id=str(conversation_id),
            response=mock_response,
            intent=intent,
            timestamp=assistant_message.created_at.isoformat()
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")


@router.get("/conversations", response_model=List[ConversationResponse])
async def get_conversations(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Получить список бесед пользователя"""
    try:
        result = await db.execute(
            select(Conversation)
            .where(Conversation.user_id == user["id"])
            .order_by(Conversation.updated_at.desc())
        )
        conversations = result.scalars().all()
        
        response = []
        for conv in conversations:
            # Подсчитываем количество сообщений
            message_count_result = await db.execute(
                select(Message).where(Message.conversation_id == conv.conversation_id)
            )
            message_count = len(message_count_result.scalars().all())
            
            response.append(ConversationResponse(
                conversation_id=str(conv.conversation_id),
                title=conv.title or "Новая беседа",
                created_at=conv.created_at.isoformat(),
                message_count=message_count
            ))
        
        return response
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching conversations: {str(e)}")


@router.get("/conversation/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Получить все сообщения беседы"""
    try:
        conv_uuid = uuid.UUID(conversation_id)
        
        # Проверяем доступ
        result = await db.execute(
            select(Conversation).where(
                Conversation.conversation_id == conv_uuid,
                Conversation.user_id == user["id"]
            )
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Получаем сообщения
        messages_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conv_uuid)
            .order_by(Message.created_at.asc())
        )
        messages = messages_result.scalars().all()
        
        return [
            {
                "message_id": str(msg.message_id),
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.isoformat()
            }
            for msg in messages
        ]
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching messages: {str(e)}")
