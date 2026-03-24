from typing import List, Optional, Tuple
import copy
import random
import numpy as np
from pydantic import BaseModel, Field
from langchain_core.language_models import BaseChatModel

import obllomov.agents.prompts as prompts
from obllomov.shared.log import logger
from .base import BasePlanner


class RawWindowEntry(BaseModel):
    room_id: str = Field(description="Room type id")
    wall_direction: str = Field(description="One of: north, south, east, west")
    window_type: str = Field(description="Window type, e.g. 'single-hung'")
    window_size: List[float] = Field(description="[width, height] in meters")
    quantity: int = Field(description="Number of windows on this wall")
    window_height: float = Field(description="Height from floor to bottom of window in cm")


class RawWindowPlan(BaseModel):
    windows: List[RawWindowEntry] = Field(description="List of windows per room wall")


class WindowPlanner(BasePlanner):
    def __init__(self, llm: BaseChatModel):
        super().__init__(llm)
        self._load_window_data()

    def plan(self, scene, additional_requirements="N/A"):
        organized_walls, available_wall_str = self._get_wall_for_windows(scene)

        raw = self._structured_plan(
            scene=scene,
            schema=RawWindowPlan,
            prompt_template=prompts.window_prompt,
            cache_key="raw_window_plan",
            input_variables={
                "input": scene["query"],
                "walls": available_wall_str,
                "wall_height": int(scene["wall_height"] * 100),
                "additional_requirements": additional_requirements,
            },
        )

        return self._parse_raw(raw, scene, organized_walls)

    def _parse_raw(self, raw: RawWindowPlan, scene: dict, organized_walls: dict):
        walls = scene["walls"]
        windows = []
        room_with_windows = []

        for entry in raw.windows:
            if entry.room_id in room_with_windows:
                logger.warning(f"Room {entry.room_id} already has windows")
                continue
            room_with_windows.append(entry.room_id)

            # rest of placement logic unchanged
            ...

        return walls, windows
    
