from pydantic import BaseModel
from typing import List

class TextRequest(BaseModel):
    text: str
    room_type: str = "living_room"
    dimensions: List[float] = [5.0, 4.0, 2.7]  # [длина, ширина, высота] в метрах
    style: str = "modern"

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
