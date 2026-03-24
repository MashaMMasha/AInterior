from typing import List, Optional, Dict
import copy
from pydantic import BaseModel, Field
from langchain_core.language_models import BaseChatModel

import obllomov.agents.prompts as prompts
from obllomov.storage.assets import BaseAssets
from .base import BasePlanner


class RawObjectEntry(BaseModel):
    description: str
    location: str = Field(description="One of: floor, wall")
    size: Optional[List[int]] = Field(description="[x, y, z] in cm")
    quantity: int
    variance_type: str = Field(description="One of: same, varied")
    objects_on_top: List[dict] = Field(default_factory=list)


class RawRoomObjects(BaseModel):
    objects: Dict[str, RawObjectEntry] = Field(description="Map of object_name to object info")


class ObjectSelectorPlanner(BasePlanner):
    def __init__(self, llm: BaseChatModel, assets: BaseAssets):
        super().__init__(llm, assets)

    def plan(self, scene, additional_requirements="N/A") -> dict:
        selected_objects = {}

        for room in scene["rooms"]:
            room_type = room["roomType"]
            room_size = self._get_room_size(room, scene["wall_height"])
            room_size_str = (
                f"{int(room_size[0])*100}cm x {int(room_size[1])*100}cm x {int(room_size[2])*100}cm"
            )

            raw = self._structured_plan(
                scene=scene,
                schema=RawRoomObjects,
                prompt_template=prompts.object_selection_prompt_new_1,
                cache_key=f"raw_object_plan_{room_type}",
                input_variables={
                    "input": scene["query"],
                    "room_type": room_type,
                    "room_size": room_size_str,
                    "requirements": additional_requirements,
                },
            )

            floor_objects, wall_objects = self._parse_raw(raw, scene, room)
            selected_objects[room_type] = {"floor": floor_objects, "wall": wall_objects}

        return selected_objects

    def _parse_raw(self, raw: RawRoomObjects, scene: dict, room: dict):
        floor_object_list = []
        wall_object_list = []

        for object_name, info in raw.objects.items():
            entry = info.model_dump()
            entry["object_name"] = object_name
            if info.location == "floor":
                floor_object_list.append(entry)
            else:
                wall_object_list.append(entry)

        # rest of retrieval/placement logic unchanged
        ...
