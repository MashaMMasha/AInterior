from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ChatStage(BaseModel):
    id: int
    stage_name: str
    scene_plan: dict
    raw_scene_plan: dict
    created_at: datetime


class ChatInteraction(BaseModel):
    id: int
    sequence: int
    query: str
    stages: list[ChatStage] = []
    created_at: datetime

    @property
    def current_stage(self) -> Optional[ChatStage]:
        return self.stages[-1] if self.stages else None


class ChatSession(BaseModel):
    id: str
    user_id: str
    interactions: list[ChatInteraction] = []
    created_at: datetime

    @property
    def current(self) -> Optional[ChatInteraction]:
        return self.interactions[-1] if self.interactions else None
