from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
import uuid

from render_service.config import DATABASE_URL


engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


class GenerationProgress(Base):
    __tablename__ = "generation_progress"
    __table_args__ = {"schema": "interior"}
    
    id = Column(Integer, primary_key=True)
    generation_id = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    user_id = Column(Integer, nullable=True)
    query = Column(Text, nullable=False)
    status = Column(String(50), nullable=False, default='pending')
    current_step = Column(String(100), nullable=True)
    total_steps = Column(Integer, default=8)
    completed_steps = Column(Integer, default=0)
    scene_json = Column(JSONB, nullable=False, default={})
    error_message = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)


async def get_db_session():
    async with async_session_maker() as session:
        yield session
