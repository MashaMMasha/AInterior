from typing import Dict, List, Optional, Tuple

from langchain_core.language_models import BaseChatModel

import obllomov.agents.prompts as prompts
from obllomov.schemas.domain.annotations import Annotation, AnnotationDict
from obllomov.schemas.domain.scene import ScenePlan
from obllomov.schemas.domain.raw import RawFloorObjectConstraints
from obllomov.agents.selectors.placement import DFS_Solver_Floor
from obllomov.shared.geometry import Polygon2D, Vertex2D
from obllomov.shared.log import logger
from obllomov.storage.assets import BaseAssets

from .base import BasePlanner


class FloorObjectPlanner(BasePlanner):
    def __init__(self, llm: BaseChatModel, assets: BaseAssets, annotations: AnnotationDict):
        super().__init__(llm, assets)
        self.annotations = annotations
        self.grid_density = 20
        self.size_buffer = 10
        self.constraint_type = "llm"

    def plan(
        self,
        scene_plan: ScenePlan,
        raw: Optional[Dict[str, RawFloorObjectConstraints]] = None,
        use_constraint: bool = True,
    ) -> Tuple[list, Dict[str, RawFloorObjectConstraints]]:
        if raw is None:
            raw = {}

        all_placements = [
            self._plan_room(room, scene_plan, use_constraint, raw)
            for room in scene_plan.rooms
        ]
        floor_objects = [obj for placements in all_placements for obj in placements]
        return floor_objects, raw

    def _plan_room(self, room, scene_plan, use_constraint, raw_cache) -> list:
        room_id = room.id
        room_type = room.room_type

        selected = scene_plan.selected_objects.get(room_type, {}).get("floor", [])
        object_name2id = {name: asset_id for name, asset_id in selected}
        object_names = list(object_name2id.keys())
        if not object_names:
            return []

        room_vertices = [v.scaled(100) for v in room.vertices]
        room_poly = Polygon2D(vertices=room_vertices)
        room_x, room_z = int(room_poly.bbox_size()[0]), int(room_poly.bbox_size()[1])
        room_size = f"{room_x} cm x {room_z} cm"
        grid_size = max(room_x // self.grid_density, room_z // self.grid_density)

        if use_constraint and self.constraint_type == "llm":
            if room_id in raw_cache:
                raw_constraints = raw_cache[room_id]
            else:
                raw_constraints = self._structured_plan(
                    schema=RawFloorObjectConstraints,
                    prompt_template=prompts.object_constraints_prompt,
                    input_variables={
                        "room_type": room_type,
                        "room_size": room_size,
                        "objects": ", ".join(object_names),
                    },
                )
                raw_cache[room_id] = raw_constraints
            constraints = self._parse_raw(raw_constraints, object_names)
        else:
            constraints = {
                name: [{"type": "global", "constraint": "edge"}]
                for name in object_names
            }

        object2dim = {
            name: self.annotations[asset_id].bbox.convert_m_to_cm()
            for name, asset_id in object_name2id.items()
        }
        objects_list = [
            (name, (object2dim[name].x + self.size_buffer, object2dim[name].z + self.size_buffer))
            for name in constraints
            if name in object2dim
        ]

        initial_state = self._get_initial_state(scene_plan, room_poly)

        solver = DFS_Solver_Floor(grid_size=grid_size, max_duration=30, constraint_bouns=1)
        solution = solver.get_solution(room_poly.to_shapely(), objects_list, constraints, initial_state)

        return self._solution_to_placements(solution, object_name2id, room_id)

    def _parse_raw(self, raw: RawFloorObjectConstraints, object_names: list) -> dict:
        constraints = {}
        for entry in raw.entries:
            if entry.object_name not in object_names:
                continue
            constraints[entry.object_name] = [
                {k: v for k, v in c.model_dump().items() if v is not None}
                for c in entry.constraints
            ]
        return constraints

    def _solution_to_placements(self, solutions: dict, object_name2id: dict, room_id: str) -> list:
        placements = []
        for name, solution in solutions.items():
            if any(p in name for p in ("door", "window", "open")):
                continue
            if name not in object_name2id:
                continue
            dims = self.annotations[object_name2id[name]].bbox
            placements.append({
                "asset_id": object_name2id[name],
                "id": f"{name} ({room_id})",
                "kinematic": True,
                "position": {
                    "x": solution[0][0] / 100,
                    "y": dims.y / 2,
                    "z": solution[0][1] / 100,
                },
                "rotation": {"x": 0, "y": solution[1], "z": 0},
                "material": None,
                "roomId": room_id,
                "vertices": list(solution[2]),
                "object_name": name,
            })
        return placements

    def _get_initial_state(self, scene_plan: ScenePlan, room_poly: Polygon2D) -> dict:
        # shapely_poly = room_poly.to_shapely()
        initial_state = {}
        i = 0


        for door in scene_plan.doors:
            for door_box in door.door_boxes:
                verts = [(x * 100, z * 100) for x, z in door_box]
                poly = Polygon2D(vertices=[Vertex2D(x=v[0], z=v[1]) for v in verts])
                if room_poly.contains(poly.centroid):
                    c = poly.centroid
                    initial_state[f"door-{i}"] = ((c.x, c.z), 0, verts, 1)
                    i += 1

        open_walls = scene_plan.open_walls
        if open_walls:
            for open_box in open_walls.get("openWallBoxes", []):
                verts = [(x * 100, z * 100) for x, z in open_box]
                poly = Polygon2D(vertices=[Vertex2D(x=v[0], z=v[1]) for v in verts])
                if room_poly.contains(poly.centroid):
                    c = poly.centroid
                    initial_state[f"open-{i}"] = ((c.x, c.z), 0, verts, 1)
                    i += 1

        return initial_state
