from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class ProjectCreate(BaseModel):
    name: str


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    objects: Optional[List[Dict[str, Any]]] = None


class Project(BaseModel):
    id: str
    name: str
    objects: List[Dict[str, Any]] = []
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class TextRequest(BaseModel):
    text: str
    room_type: str = "living_room"
    dimensions: List[float] = [5.0, 4.0, 2.7]
    style: str = "modern"
