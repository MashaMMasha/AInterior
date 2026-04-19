from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from chat_service.config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = {"schema": "chat"}

    id = Column(Integer, primary_key=True)
    conversation_id = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    user_id = Column(Integer, nullable=False)
    title = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = {"schema": "chat"}

    id = Column(Integer, primary_key=True)
    message_id = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey('chat.conversations.conversation_id', ondelete='CASCADE'), nullable=False)
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


async def get_db_session():
    async with async_session_maker() as session:
        yield session
