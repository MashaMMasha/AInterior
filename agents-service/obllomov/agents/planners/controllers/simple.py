import math
import random
from typing import Dict, List, Optional, Tuple

from obllomov.schemas.domain.annotations import AnnotationDict
from obllomov.schemas.domain.scene import ScenePlan
from obllomov.shared.log import logger

from .base import BaseObjectController


class SimpleObjectController(BaseObjectController):
    def __init__(self, annotations: AnnotationDict):
        self.annotations = annotations
        self._receptacles: Dict[str, dict] = {}
        self._placed_boxes: Dict[str, List[Tuple[float, float, float, float]]] = {}

    def start(self, scene_plan: ScenePlan) -> List[str]:
        self._receptacles.clear()
        self._placed_boxes.clear()

        for obj in scene_plan.floor_objects:
            ann = self.annotations.get(obj.asset_id)
            if ann is None or not ann.onObject:
                continue
            self._receptacles[obj.id] = {
                "position": obj.position,
                "rotation": obj.rotation,
                "bbox": ann.bbox,
            }
            self._placed_boxes[obj.id] = []

        logger.debug(f"SimpleObjectController: {len(self._receptacles)} receptacles")
        return list(self._receptacles.keys())

    def place_object(self, asset_id: str, receptacle_id: str, rotation: list) -> Optional[dict]:
        rec = self._receptacles.get(receptacle_id)
        if rec is None:
            return None

        obj_ann = self.annotations.get(asset_id)
        if obj_ann is None:
            return None

        rec_pos = rec["position"]
        rec_rot = rec["rotation"]
        rec_bbox = rec["bbox"]

        top_y = rec_pos.y + rec_bbox.y / 2

        angle_rad = math.radians(rec_rot.y)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)

        half_ox = obj_ann.bbox.x / 2
        half_oz = obj_ann.bbox.z / 2
        margin_x = max(rec_bbox.x / 2 - half_ox, 0)
        margin_z = max(rec_bbox.z / 2 - half_oz, 0)

        for _ in range(20):
            lx = random.uniform(-margin_x, margin_x)
            lz = random.uniform(-margin_z, margin_z)

            wx = rec_pos.x + lx * cos_a - lz * sin_a
            wz = rec_pos.z + lx * sin_a + lz * cos_a

            if not self._collides(receptacle_id, wx, wz, obj_ann.bbox.x, obj_ann.bbox.z):
                self._placed_boxes[receptacle_id].append((wx, wz, obj_ann.bbox.x, obj_ann.bbox.z))
                return {
                    "position": {"x": wx, "y": top_y, "z": wz},
                    "rotation": {"x": rotation[0], "y": rotation[1] + rec_rot.y, "z": rotation[2]},
                }

        return None

    def _collides(self, receptacle_id: str, x: float, z: float, sx: float, sz: float) -> bool:
        half_sx = sx / 2
        half_sz = sz / 2
        for px, pz, psx, psz in self._placed_boxes[receptacle_id]:
            if (abs(x - px) < (half_sx + psx / 2) * 0.9
                    and abs(z - pz) < (half_sz + psz / 2) * 0.9):
                return True
        return False

    def stop(self) -> None:
        self._receptacles.clear()
        self._placed_boxes.clear()
