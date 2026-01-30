from typing import *

from pydantic import BaseModel, Field

from langchain_core.messages import BaseMessage

from uuid import UUID



class TextRequest(BaseModel):
    text: str
    room_type: str = "living_room"
    dimensions: List[float] = [5.0, 4.0, 2.7]  # [длина, ширина, высота] в метрах
    style: str = "modern"


class ChatMessage(BaseModel):
    role: str = Field(default="user")
    content: str
    session_id: str = Field(default="None")

class ChatSession(BaseModel):
    content: str 
    history: Optional[List[BaseMessage]] = []
    session_id: Optional[str] = None

class FurnitureItem(BaseModel):
    type: str
    position: List[float]  # [x, y, z]
    rotation: List[float] = [0.0, 0.0, 0.0]  # углы Эйлера
    scale: List[float] = [1.0, 1.0, 1.0]
    color: List[float] = [0.5, 0.5, 0.5]

class RoomScene(BaseModel):
    room_id: str
    dimensions: List[float]
    furniture: List[FurnitureItem]
    style: str
    created_at: str


