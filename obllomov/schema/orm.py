import enum
from typing import List, Optional
from uuid import UUID

from sqlalchemy import Column, DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from obllomov.shared.time import NOW


class Base(DeclarativeBase):
    id = Column(String(36), primary_key=True, index=True)



class ChatSession(Base):
    __tablename__ = "chat_sessions"
    
    # id = Column(Integer, primary_key=True, index=True)
    # id = Column(String(36), primary_key=True, index=True)
    created_at = Column(DateTime, default=NOW())
    updated_at = Column(DateTime, default=NOW(), onupdate=NOW())

class ChatRole(enum.Enum):
    human = 0
    ai = 1
    system = 2


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    # id = Column(String(36), primary_key=True, index=True)
    session_id = Column(String(36), index=True)
    role = Column(String)  # 'human', 'ai', 'system'
    content = Column(Text)
    timestamp = Column(DateTime, default=NOW())


