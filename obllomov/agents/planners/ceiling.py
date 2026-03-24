from typing import List, Optional
import copy
from pydantic import BaseModel, Field
from langchain_core.language_models import BaseChatModel
from shapely.geometry import Polygon

import obllomov.agents.prompts as prompts
from obllomov.shared.utils import get_bbox_dims, get_annotations
from obllomov.storage.assets import BaseAssets
from obllomov.shared.log import logger
from .base import BasePlanner


class RawCeilingEntry(BaseModel):
    room_type: str = Field(description="Room type")
    object_description: str = Field(description="Description of the ceiling object, e.g. 'modern LED panel light'")


class RawCeilingPlan(BaseModel):
    ceiling_objects: List[RawCeilingEntry] = Field(description="List of ceiling objects per room")


class CeilingPlanner(BasePlanner):
    def __init__(self, llm: BaseChatModel, assets: BaseAssets):
        super().__init__(llm, assets)

    def plan(self, scene, additional_requirements="N/A"):
        room_types_str = str([r["roomType"] for r in scene["rooms"]]).replace("'", "")[1:-1]

        raw = self._structured_plan(
            scene=scene,
            schema=RawCeilingPlan,
            prompt_template=prompts.ceiling_selection_prompt,
            cache_key="raw_ceiling_plan",
            input_variables={
                "input": scene["query"],
                "rooms": room_types_str,
                "additional_requirements": additional_requirements,
            },
        )

        return self._parse_raw(raw, scene)

    def _parse_raw(self, raw: RawCeilingPlan, scene: dict) -> list:
        ceiling_objects = []

        for entry in raw.ceiling_objects:
            room = next((r for r in scene["rooms"] if r["roomType"] == entry.room_type), None)
            if room is None:
                logger.warning(f"Room type {entry.room_type} not found")
                continue

            asset_id = self._select_asset(entry.object_description)
            if asset_id is None:
                continue

            dimension = get_bbox_dims(self.assets.database[asset_id])
            floor_polygon = Polygon(room["vertices"])
            x = floor_polygon.centroid.x
            z = floor_polygon.centroid.y
            y = scene["wall_height"] - dimension["y"] / 2

            ceiling_objects.append({
                "assetId": asset_id,
                "id": f"ceiling ({entry.room_type})",
                "kinematic": True,
                "position": {"x": x, "y": y, "z": z},
                "rotation": {"x": 0, "y": 0, "z": 0},
                "material": None,
                "roomId": room["id"],
                "object_name": get_annotations(self.assets.database[asset_id])["category"],
            })

        return ceiling_objects
