import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Optional, Tuple, Dict

import torch
import torch.nn.functional as F
from ai2thor.controller import Controller
from ai2thor.hooks.procedural_asset_hook import ProceduralAssetHookRunner
from langchain_core.language_models import BaseChatModel
from procthor.constants import FLOOR_Y
from procthor.utils.types import Vector3
from pydantic import BaseModel, Field

from obllomov.agents.retrievers import BaseRetriever
from obllomov.agents.selectors import BaseSelector
from obllomov.agents.retrievers import ObjathorRetriever
from obllomov.schemas.domain.entries import (ScenePlan, SmallObjectEntry,
                                             SmallObjectPlan)
from obllomov.schemas.domain.annotations import Annotation, AnnotationDict
from obllomov.shared.geometry import BBox3D, Box3D, Vertex3D
from obllomov.shared.log import logger
from obllomov.shared.path import OBJATHOR_ASSETS_DIR
from obllomov.shared.utils import THOR_COMMIT_ID
from obllomov.storage.assets import BaseAssets

from .base import BasePlanner


class SmallObjectPlanner(BasePlanner):
    def __init__(
        self,
        llm: BaseChatModel,
        assets: BaseAssets,
        objathor_retriever: BaseRetriever,
        annotations: AnnotationDict,
    ):
        super().__init__(llm, assets)
        self.objathor_retriever = objathor_retriever
        self.annotations = annotations
        self.clip_threshold = 30
        self.reuse_assets = True

    def plan(self, scene_plan: ScenePlan, controller, receptacle_ids) -> SmallObjectPlan:
        object_selection_plan = scene_plan.object_selection_plan
        receptacle2asset_id = {}

        if scene_plan.receptacle2small_objects and self.reuse_assets:
            receptacle2small_objects = scene_plan.receptacle2small_objects
        else:
            receptacle2small_objects = self._select_small_objects(
                object_selection_plan, receptacle_ids, receptacle2asset_id
            )

        small_objects = self._place_objects(
            scene_plan.wall_height, controller, receptacle2small_objects,
        )

        return SmallObjectPlan(
            small_objects=small_objects,
            receptacle2small_objects=receptacle2small_objects,
        )

    def _select_small_objects(
        self, object_selection_plan: dict, receptacle_ids: list, receptacle2asset_id: dict
    ) -> dict:
        children_plans = []
        for room_type, objects in object_selection_plan.items():
            for object_name, object_info in objects.items():
                for child in object_info["objects_on_top"]:
                    child_plan = dict(child)
                    child_plan["room_type"] = room_type
                    child_plan["parent"] = object_name
                    children_plans.append(child_plan)

        receptacle2plans = {}
        for receptacle_id in receptacle_ids:
            plans = [
                p for p in children_plans
                if p["room_type"] in receptacle_id and p["parent"] in receptacle_id
            ]
            if plans:
                receptacle2plans[receptacle_id] = plans

        packed_args = [(receptacle, plans, receptacle2asset_id) for receptacle, plans in receptacle2plans.items()]

        with ThreadPoolExecutor(max_workers=4) as ex:
            results = list(ex.map(self._select_per_receptacle, packed_args))

        return {receptacle: objects for receptacle, objects in results}

    def _select_per_receptacle(self, args) -> Tuple[str, list]:
        receptacle, small_objects, receptacle2asset_id = args

        receptacle_dims = self.annotations[receptacle2asset_id[receptacle]].bbox
        receptacle_area = receptacle_dims.x * receptacle_dims.z
        capacity = 0
        num_objects = 0
        results = []

        for small_object in small_objects:
            object_name = small_object["object_name"]
            quantity = min(small_object["quantity"], 5)
            variance_type = small_object["variance_type"]

            items, scores = self.objathor_retriever.retrieve(
                [f"a 3D model of {object_name}"], topk=80
            )
            candidates = list(zip(items[0], scores[0]))
            candidates = [
                c for c in candidates
                if self.annotations[c[0]].onObject
                and self.annotations[c[0]].bbox.x < receptacle_dims.x * 0.9
                and self.annotations[c[0]].bbox.z < receptacle_dims.z * 0.9
            ]

            if not candidates:
                continue

            top = candidates[0]
            filtered = [c for c in candidates if c[0] not in self.used_assets]
            candidates = (filtered or [top])[:5]

            selected_ids = []
            if variance_type == "same":
                selected_ids = [BaseSelector.random_select(candidates)[0]] * quantity
            else:
                for _ in range(quantity):
                    selected = BaseSelector.random_select(candidates)
                    selected_ids.append(selected[0])
                    if len(candidates) > 1:
                        candidates.remove(selected)

            for i, asset_id in enumerate(selected_ids):
                dims = self.annotations[asset_id].bbox
                sizes = sorted([dims.x, dims.y, dims.z])
                obj_area = sizes[1] * sizes[2] * 0.8
                capacity += obj_area
                num_objects += 1

                if (capacity > receptacle_area * 0.9 and num_objects > 1) or num_objects > 15:
                    break

                results.append((f"{object_name}-{i}", asset_id, max(dims.x, dims.z)))

        results.sort(key=lambda x: x[2], reverse=True)
        return receptacle, results


    def _place_objects(
        self, wall_height: float, controller: Controller, receptacle2small_objects: dict,
    ) -> List[SmallObjectEntry]:
        results = []

        for receptacle, small_objects in receptacle2small_objects.items():
            placements = []

            for object_name, asset_id, _ in small_objects:
                thin, rotation = self._check_thin(asset_id)
                small, y_rotation = self._check_small(asset_id)

                obj = self._place_object(controller, asset_id, receptacle, rotation)
                if obj is None:
                    continue

                asset_height = self.annotations[asset_id].bbox.y
                if obj["position"]["y"] + asset_height > wall_height:
                    continue

                position = Vertex3D(
                    x=obj["position"]["x"],
                    y=obj["position"]["y"] + asset_height / 2 + 0.001,
                    z=obj["position"]["z"],
                )
                room_id = receptacle.split("(")[1].split(")")[0]

                kinematic = not (small or thin)
                if "CanBreak" in self.annotations[asset_id].secondary_properties:
                    kinematic = True

                rotation_v = Vertex3D(**obj["rotation"])
                if thin:
                    position, rotation_v = self._fix_thin_placement(asset_id, position, rotation_v)
                if small:
                    rotation_v = Vertex3D(x=rotation_v.x, y=y_rotation, z=rotation_v.z)

                placements.append(SmallObjectEntry(
                    asset_id=asset_id,
                    id=f"{object_name}|{receptacle}",
                    kinematic=kinematic,
                    position=position,
                    rotation=rotation_v,
                    room_id=room_id,
                ))

            results.extend(self._filter_collisions(placements))

        return results

    def _place_object(self, controller, asset_id, receptacle_id, rotation) -> Optional[dict]:
        generated_id = f"small|{asset_id}"
        controller.step(
            action="SpawnAsset",
            assetId=asset_id,
            generatedId=generated_id,
            position=Vector3(x=0, y=FLOOR_Y - 20, z=0),
            rotation=Vector3(x=0, y=0, z=0),
            renderImage=False,
        )
        event = controller.step(
            action="InitialRandomSpawn",
            randomSeed=random.randint(0, 1_000_000_000),
            objectIds=[generated_id],
            receptacleObjectIds=[receptacle_id],
            forceVisible=False,
            allowFloor=False,
            renderImage=False,
            allowMoveable=True,
            numPlacementAttempts=10,
        )
        obj = next(o for o in event.metadata["objects"] if o["objectId"] == generated_id)
        if event and obj["axisAlignedBoundingBox"]["center"]["y"] > FLOOR_Y:
            return obj
        controller.step(action="DisableObject", objectId=generated_id, renderImage=False)
        return None


    def _check_thin(self, asset_id: str) -> Tuple[bool, list]:
        dims_cm = self.annotations[asset_id].bbox.convert_m_to_cm()
        threshold = 5.0
        if dims_cm.x < threshold:
            return True, [0, 90, 0]
        if dims_cm.z < threshold:
            return True, [90, 0, 0]
        return False, [0, 0, 0]

    def _check_small(self, asset_id: str) -> Tuple[bool, int]:
        size = self.annotations[asset_id].bbox.convert_m_to_cm().size()
        if size[0] * size[2] <= 625 and all(s <= 25 for s in size):
            return True, random.randint(0, 360)
        return False, 0

    def _fix_thin_placement(self, asset_id: str, position: Vertex3D, rotation: Vertex3D) -> Tuple[Vertex3D, Vertex3D]:
        dims = self.annotations[asset_id].bbox
        threshold = 0.03
        bottom_y = position.y - dims.y / 2

        if dims.x <= threshold:
            rotation = Vertex3D(x=rotation.x, y=rotation.y, z=rotation.z + 90)
            position = Vertex3D(x=position.x, y=bottom_y + dims.x / 2, z=position.z)
        elif dims.z <= threshold:
            rotation = Vertex3D(x=rotation.x + 90, y=rotation.y, z=rotation.z)
            position = Vertex3D(x=position.x, y=bottom_y + dims.z / 2, z=position.z)

        return position, rotation

    def _filter_collisions(self, placements: List[SmallObjectEntry]) -> List[SmallObjectEntry]:
        static = [p for p in placements if p.kinematic]
        if len(static) <= 1:
            return placements

        colliding_pairs = []
        for i, p1 in enumerate(static[:-1]):
            for p2 in static[i + 1:]:
                if self._get_box(p1).intersects(self._get_box(p2)):
                    colliding_pairs.append((p1.id, p2.id))

        if not colliding_pairs:
            return placements

        remove_ids = set()
        all_ids = list(set(pid for pair in colliding_pairs for pid in pair))
        all_ids.sort(
            key=lambda x: self.annotations[
                next(p.asset_id for p in placements if p.id == x)
            ].bbox.x
        )
        for obj_id in all_ids:
            remove_ids.add(obj_id)
            colliding_pairs = [p for p in colliding_pairs if obj_id not in p]
            if not colliding_pairs:
                break

        return [p for p in placements if p.id not in remove_ids]

    def _get_box(self, placement: SmallObjectEntry) -> Box3D:
        dims = self.annotations[placement.asset_id].bbox.convert_m_to_cm()
        center = placement.position.convert_m_to_cm()
        return Box3D.from_center_and_size(center, dims)

    def start_controller(self, scene) -> Controller:
        objathor_assets_dir = self.assets.get_local_dir(OBJATHOR_ASSETS_DIR)
        return Controller(
            commit_id=THOR_COMMIT_ID,
            agentMode="default",
            makeAgentsVisible=False,
            visibilityDistance=1.5,
            scene=scene,
            width=224,
            height=224,
            fieldOfView=40,
            action_hook_runner=ProceduralAssetHookRunner(
                asset_directory=str(objathor_assets_dir),
                asset_symlink=True,
                verbose=True,
            ),
        )
