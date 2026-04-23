import random
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

import obllomov.agents.prompts as prompts
from obllomov.schemas.domain.annotations import Annotation, AnnotationDict
from obllomov.schemas.domain.entries import (WallObjectEntry, WallObjectPlan)
from obllomov.schemas.domain.scene import ScenePlan
from obllomov.schemas.domain.raw import (RawWallObjectConstraintEntry,
                                         RawWallObjectConstraints)
from obllomov.agents.selectors.placement import DFS_Solver_Wall
from obllomov.shared.geometry import Polygon2D, Vertex2D, Vertex3D
from obllomov.shared.log import logger
from obllomov.agents.retrievers import ObjathorRetriever
from obllomov.storage.assets import BaseAssets

from .base import BasePlanner


class WallObjectPlanner(BasePlanner):
    def __init__(self, llm: BaseChatModel, assets: BaseAssets, annotations: AnnotationDict):
        super().__init__(llm, assets)
        self.grid_size = 25
        self.default_height = 150
        self.constraint_type = "llm"
        self.annotations = annotations

    def plan(
        self,
        scene_plan: ScenePlan,
        raw: Optional[Dict[str, RawWallObjectConstraints]] = None,
        use_constraint: bool = True,
    ) -> Tuple[WallObjectPlan, Dict[str, RawWallObjectConstraints]]:
        if raw is None:
            raw = {}

        packed_args = [
            (room, scene_plan, use_constraint, raw)
            for room in scene_plan.rooms
        ]
        with ThreadPoolExecutor(max_workers=4) as ex:
            all_placements = list(ex.map(self._plan_room, packed_args))

        wall_objects = [obj for placements in all_placements for obj in placements]
        return WallObjectPlan(wall_objects=wall_objects), raw


    def _plan_room(self, args) -> List[WallObjectEntry]:
        from obllomov.agents.planners.floor import RoomPlan
        room: RoomPlan
        room, scene_plan, use_constraint, raw_cache = args

        room_id = room.id
        room_type = room.room_type
        selected_wall_objects = scene_plan.selected_objects[room_type]["wall"]
        selected_wall_objects = self._order_by_size(selected_wall_objects)
        wall_object_name2id = {name: asset_id for name, asset_id in selected_wall_objects}

        floor_object_names = [
            obj.object_name
            for obj in scene_plan.floor_objects
            if obj.room_id == room_id
        ]
        wall_object_names = list(wall_object_name2id.keys())

        if use_constraint and self.constraint_type == "llm":
            if room_id in raw_cache:
                raw_constraints = raw_cache[room_id]
            else:
                raw_constraints = self._structured_plan(
                    schema=RawWallObjectConstraints,
                    prompt_template=prompts.wall_object_constraints_prompt,
                    input_variables={
                        "room_type": room_type,
                        "wall_height": int(scene_plan.wall_height * 100),
                        "floor_objects": ", ".join(floor_object_names),
                        "wall_objects": ", ".join(wall_object_names),
                    },
                )
                raw_cache[room_id] = raw_constraints
            constraints = self._parse_raw(raw_constraints, wall_object_names, floor_object_names)
        else:
            constraints = self._default_constraints(wall_object_names, scene_plan.wall_height)

        wall_object2dimension = {
            name: self.annotations[asset_id].bbox
            for name, asset_id in wall_object_name2id.items()
        }
        wall_objects_list = [
            (name, tuple(wall_object2dimension[name].convert_m_to_cm().size()))
            for name in constraints
        ]

        for name in constraints:
            max_h = min(
                scene_plan.wall_height * 100 - wall_object2dimension[name].convert_m_to_cm().y - 20,
                constraints[name]["height"],
            )
            constraints[name]["height"] = max(max_h, 0)

        room_vertices = [v.scaled(100) for v in room.vertices]
        room_poly = Polygon2D(vertices=room_vertices)
        initial_state = self._get_initial_state(scene_plan, room_poly)

        room_x = int(room_poly.bbox_size()[0])
        room_z = int(room_poly.bbox_size()[1])
        grid_size = max(room_x // 20, room_z // 20)

        solver = DFS_Solver_Wall(grid_size=grid_size, max_duration=5, constraint_bouns=100)
        solutions = solver.get_solution(room_poly.to_shapely(), wall_objects_list, constraints, initial_state)

        return self._solutions_to_entries(solutions, wall_object_name2id, room_id)

    def _parse_raw(
        self,
        raw: RawWallObjectConstraints,
        wall_object_names: list,
        floor_object_names: list,
    ) -> dict:
        constraints = {}
        for entry in raw.constraints:
            if entry.object_name not in wall_object_names:
                continue
            constraints[entry.object_name] = {
                "target_floor_object_name": (
                    entry.near_floor_object
                    if entry.near_floor_object in floor_object_names
                    else None
                ),
                "height": entry.height,
            }
        return constraints

    def _default_constraints(self, wall_object_names: list, wall_height: float) -> dict:
        return {
            name: {
                "target_floor_object_name": None,
                "height": random.randint(0, int(wall_height * 100)),
            }
            for name in wall_object_names
        }


    def _solutions_to_entries(
        self, solutions: dict, wall_object_name2id: dict, room_id: str
    ) -> List[WallObjectEntry]:
        entries = []
        for object_name, solution in solutions.items():
            if object_name not in wall_object_name2id:
                continue

            vertex_min, vertex_max, rotation, box_coords, _ = solution
            position_x = (vertex_min[0] + vertex_max[0]) / 200
            position_y = (vertex_min[1] + vertex_max[1]) / 200
            position_z = (vertex_min[2] + vertex_max[2]) / 200

            offsets = {0: (0, 0.01), 90: (0.01, 0), 180: (0, -0.01), 270: (-0.01, 0)}
            dx, dz = offsets.get(rotation, (0, 0))

            entries.append(WallObjectEntry(
                asset_id=wall_object_name2id[object_name],
                id=f"{object_name} ({room_id})",
                position=Vertex3D(x=position_x + dx, y=position_y, z=position_z + dz),
                rotation=Vertex3D(x=0, y=rotation, z=0),
                room_id=room_id,
                vertices=list(box_coords),
                object_name=object_name,
            ))

        return entries

    def _get_initial_state(self, scene_plan: ScenePlan, room_poly: Polygon2D) -> dict:
        shapely_poly = room_poly.to_shapely()
        initial_state = {}
        i = 0

        for door in scene_plan.doors:
            for door_box in door.door_boxes:
                door_verts = [(x * 100, z * 100) for x, z in door_box]
                door_poly = Polygon2D(vertices=[Vertex2D(x=v[0], z=v[1]) for v in door_verts])
                if shapely_poly.contains(door_poly.to_shapely().centroid):
                    door_height = door.asset_position.y * 100 * 2
                    x_min, z_min, x_max, z_max = door_poly.bounds
                    initial_state[f"door-{i}"] = (
                        (x_min, 0, z_min), (x_max, door_height, z_max), 0, door_verts, 1
                    )
                    i += 1

        for window in scene_plan.windows:
            for window_box in window.window_boxes:
                window_verts = [(x * 100, z * 100) for x, z in window_box]
                window_poly = Polygon2D(vertices=[Vertex2D(x=v[0], z=v[1]) for v in window_verts])
                if shapely_poly.contains(window_poly.to_shapely().centroid):
                    y_min = window.hole_polygon[0].y * 100
                    y_max = window.hole_polygon[1].y * 100
                    x_min, z_min, x_max, z_max = window_poly.bounds
                    initial_state[f"window-{i}"] = (
                        (x_min, y_min, z_min), (x_max, y_max, z_max), 0, window_verts, 1
                    )
                    i += 1

        open_walls = scene_plan.open_walls
        if open_walls:
            for open_box in open_walls.open_wall_boxes:
                open_verts = [(x * 100, z * 100) for x, z in open_box]
                open_poly = Polygon2D(vertices=[Vertex2D(x=v[0], z=v[1]) for v in open_verts])
                if shapely_poly.contains(open_poly.to_shapely().centroid):
                    x_min, z_min, x_max, z_max = open_poly.bounds
                    initial_state[f"open-{i}"] = (
                        (x_min, 0, z_min),
                        (x_max, scene_plan.wall_height * 100, z_max),
                        0, open_verts, 1,
                    )
                    i += 1

        for obj in scene_plan.floor_objects:
            if not obj.vertices:
                continue
            obj_poly = Polygon2D(vertices=[Vertex2D(x=v[0], z=v[1]) for v in obj.vertices])
            if shapely_poly.contains(obj_poly.to_shapely().centroid):
                obj_height = obj.position.y * 100 * 2
                x_min, z_min, x_max, z_max = obj_poly.bounds
                initial_state[obj.object_name] = (
                    (x_min, 0, z_min), (x_max, obj_height, z_max),
                    obj.rotation.y, obj.vertices, 1,
                )

        return initial_state


    def _order_by_size(self, selected: list) -> list:
        with_size = [
            (name, asset_id, self.annotations[asset_id].bbox.x)
            for name, asset_id in selected
        ]
        with_size.sort(key=lambda x: x[2], reverse=True)
        return [(name, asset_id) for name, asset_id, _ in with_size]
