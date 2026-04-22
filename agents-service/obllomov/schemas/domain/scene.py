from typing import ClassVar, Dict, List, Optional, Tuple

from pydantic import BaseModel

from .entries import (
    RoomPlan, WallEntry, DoorEntry,
    WindowEntry, WallObjectEntry,
    SmallObjectEntry, CeilingObjectEntry
    )

def _to_camel(key: str) -> str:
    parts = key.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


THOR_METADATA = {
    "schema": "1.0.0",
    "agent": {
        "horizon": 30,
        "position": {"x": 0, "y": 0.95, "z": 0},
        "rotation": {"x": 0, "y": 0, "z": 0},
        "standing": True,
    },
    "agentPoses": {},
    "roomSpecId": "",
    "warnings": {},
}

class ScenePlan(BaseModel):
    query: str = ""
    procedural_parameters: dict = {}
    rooms: List[RoomPlan] = []
    wall_height: float = 0.0
    walls: List[WallEntry] = []
    doors: List[DoorEntry] = []
    room_pairs: list = []
    open_room_pairs: List[Tuple[str, str]] = []
    open_walls: dict = {}
    windows: List[WindowEntry] = []
    object_selection_plan: dict = {}
    selected_objects: dict = {}
    floor_objects: list = []
    wall_objects: List[WallObjectEntry] = []
    small_objects: List[SmallObjectEntry] = []
    ceiling_objects: List[CeilingObjectEntry] = []
    receptacle2small_objects: dict = {}

    @staticmethod
    def _camel_keys(obj):
        if isinstance(obj, dict):
            return {_to_camel(k): ScenePlan._camel_keys(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [ScenePlan._camel_keys(i) for i in obj]
        return obj

    def to_json(self) -> dict:
        return self.model_dump()

    @classmethod
    def from_json(cls, data: dict) -> "ScenePlan":
        return cls.model_validate(data)

    def to_thor_scene(self) -> dict:
        dump = self._camel_keys(self.model_dump())
        rooms = dump.get("rooms", [])
        for room in rooms:
            room.setdefault("children", [])
            room.setdefault("ceilings", [])
        objects = (
            dump.get("floorObjects", [])
            + dump.get("wallObjects", [])
            + dump.get("smallObjects", [])
            + dump.get("ceilingObjects", [])
        )
        return {
            "metadata": THOR_METADATA,
            "rooms": rooms,
            "walls": dump.get("walls", []),
            "doors": dump.get("doors", []),
            "windows": dump.get("windows", []),
            "objects": objects,
            "proceduralParameters": dump.get("proceduralParameters", {}),
        }

