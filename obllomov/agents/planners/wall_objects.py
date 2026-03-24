import multiprocessing
import random
import time
from typing import List, Optional, Tuple

import numpy as np
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field
from shapely.geometry import Polygon

import obllomov.agents.prompts as prompts
from obllomov.shared.utils import get_bbox_dims
from obllomov.shared.log import logger
from obllomov.storage.assets import BaseAssets
from .base import BasePlanner
from obllomov.shared.dfs import DFS_Solver_Wall

class RawWallObjectConstraintEntry(BaseModel):
    object_name: str = Field(description="Wall object name")
    near_floor_object: Optional[str] = Field(
        description="Floor object it should be near, or null"
    )
    height: int = Field(description="Height from floor in cm")


class RawWallObjectConstraints(BaseModel):
    constraints: List[RawWallObjectConstraintEntry]


class WallObjectEntry(BaseModel):
    asset_id: str
    id: str
    kinematic: bool = True
    position: dict
    rotation: dict
    material: Optional[str] = None
    room_id: str
    vertices: list
    object_name: str


class WallObjectPlan(BaseModel):
    wall_objects: List[WallObjectEntry]


class WallObjectPlanner(BasePlanner):
    def __init__(self, llm: BaseChatModel, assets: BaseAssets):
        super().__init__(llm, assets)
        self.grid_size = 25
        self.default_height = 150
        self.constraint_type = "llm"

    def plan(self, scene, use_constraint=True) -> WallObjectPlan:
        packed_args = [
            (room, scene, use_constraint)
            for room in scene["rooms"]
        ]
        pool = multiprocessing.Pool(processes=4)
        all_placements = pool.map(self._plan_room, packed_args)
        pool.close()
        pool.join()

        wall_objects = [obj for placements in all_placements for obj in placements]
        return WallObjectPlan(wall_objects=wall_objects)


    def _plan_room(self, args) -> List[WallObjectEntry]:
        room, scene, use_constraint = args

        room_id = room["id"]
        room_type = room["roomType"]
        selected_wall_objects = scene["selected_objects"][room_type]["wall"]
        selected_wall_objects = self._order_by_size(selected_wall_objects)
        wall_object_name2id = {name: asset_id for name, asset_id in selected_wall_objects}

        floor_object_names = [
            obj["object_name"]
            for obj in scene["floor_objects"]
            if obj["roomId"] == room_id
        ]
        wall_object_names = list(wall_object_name2id.keys())

        if use_constraint and self.constraint_type == "llm":
            raw = self._structured_plan(
                scene=scene,
                schema=RawWallObjectConstraints,
                prompt_template=prompts.wall_object_constraints_prompt,
                cache_key=f"raw_wall_constraints_{room_id}",
                input_variables={
                    "room_type": room_type,
                    "wall_height": int(scene["wall_height"] * 100),
                    "floor_objects": ", ".join(floor_object_names),
                    "wall_objects": ", ".join(wall_object_names),
                },
            )
            constraints = self._parse_raw(raw, wall_object_names, floor_object_names)
        else:
            constraints = self._default_constraints(wall_object_names, scene["wall_height"])

        wall_object2dimension = {
            name: get_bbox_dims(self.assets.database[asset_id])
            for name, asset_id in wall_object_name2id.items()
        }
        wall_objects_list = [
            (
                name,
                (
                    wall_object2dimension[name]["x"] * 100,
                    wall_object2dimension[name]["y"] * 100,
                    wall_object2dimension[name]["z"] * 100,
                ),
            )
            for name in constraints
        ]

        for name in constraints:
            max_h = min(
                scene["wall_height"] * 100 - wall_object2dimension[name]["y"] * 100 - 20,
                constraints[name]["height"],
            )
            constraints[name]["height"] = max(max_h, 0)

        room_vertices = [(x * 100, y * 100) for x, y in room["vertices"]]
        room_poly = Polygon(room_vertices)
        initial_state = self._get_initial_state(scene, room_vertices)

        room_x = int((max(v[0] for v in room_vertices) - min(v[0] for v in room_vertices)))
        room_z = int((max(v[1] for v in room_vertices) - min(v[1] for v in room_vertices)))
        grid_size = max(room_x // 20, room_z // 20)


        solver = DFS_Solver_Wall(grid_size=grid_size, max_duration=5, constraint_bouns=100)
        solutions = solver.get_solution(room_poly, wall_objects_list, constraints, initial_state)

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
                position={"x": position_x + dx, "y": position_y, "z": position_z + dz},
                rotation={"x": 0, "y": rotation, "z": 0},
                room_id=room_id,
                vertices=list(box_coords),
                object_name=object_name,
            ))

        return entries

    def _get_initial_state(self, scene: dict, room_vertices: list) -> dict:
        room_poly = Polygon(room_vertices)
        initial_state = {}
        i = 0

        for door in scene["doors"]:
            for door_box in door["doorBoxes"]:
                door_verts = [(x * 100, z * 100) for x, z in door_box]
                door_poly = Polygon(door_verts)
                if room_poly.contains(door_poly.centroid):
                    door_height = door["assetPosition"]["y"] * 100 * 2
                    x_min, z_min, x_max, z_max = door_poly.bounds
                    initial_state[f"door-{i}"] = (
                        (x_min, 0, z_min), (x_max, door_height, z_max), 0, door_verts, 1
                    )
                    i += 1

        for window in scene["windows"]:
            for window_box in window["windowBoxes"]:
                window_verts = [(x * 100, z * 100) for x, z in window_box]
                window_poly = Polygon(window_verts)
                if room_poly.contains(window_poly.centroid):
                    y_min = window["holePolygon"][0]["y"] * 100
                    y_max = window["holePolygon"][1]["y"] * 100
                    x_min, z_min, x_max, z_max = window_poly.bounds
                    initial_state[f"window-{i}"] = (
                        (x_min, y_min, z_min), (x_max, y_max, z_max), 0, window_verts, 1
                    )
                    i += 1

        if scene.get("open_walls"):
            for open_box in scene["open_walls"]["openWallBoxes"]:
                open_verts = [(x * 100, z * 100) for x, z in open_box]
                open_poly = Polygon(open_verts)
                if room_poly.contains(open_poly.centroid):
                    x_min, z_min, x_max, z_max = open_poly.bounds
                    initial_state[f"open-{i}"] = (
                        (x_min, 0, z_min),
                        (x_max, scene["wall_height"] * 100, z_max),
                        0, open_verts, 1,
                    )
                    i += 1

        for obj in scene.get("floor_objects", []):
            if "vertices" not in obj:
                continue
            obj_poly = Polygon(obj["vertices"])
            if room_poly.contains(obj_poly.centroid):
                obj_height = obj["position"]["y"] * 100 * 2
                x_min, z_min, x_max, z_max = obj_poly.bounds
                initial_state[obj["object_name"]] = (
                    (x_min, 0, z_min), (x_max, obj_height, z_max),
                    obj["rotation"]["y"], obj["vertices"], 1,
                )

        return initial_state


    def _order_by_size(self, selected: list) -> list:
        with_size = [
            (name, asset_id, get_bbox_dims(self.assets.database[asset_id])["x"])
            for name, asset_id in selected
        ]
        with_size.sort(key=lambda x: x[2], reverse=True)
        return [(name, asset_id) for name, asset_id, _ in with_size]
