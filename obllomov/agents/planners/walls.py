import copy
import random
from typing import List, Optional, Tuple

import numpy as np
from colorama import Fore
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field
from shapely.geometry import LineString, Polygon, Point

import obllomov.agents.prompts as prompts
from obllomov.shared.log import logger
from .base import BasePlanner



class RawWallPlan(BaseModel):
    wall_height: float = Field(description="Height of the walls in meters, between 2.0 and 4.5", ge=2.0, le=4.5)


class WallEntry(BaseModel):
    id: str
    room_id: str
    material: dict
    polygon: List[dict]
    connected_rooms: List[dict]
    width: float
    height: float
    direction: Optional[str]
    segment: List


class WallPlan(BaseModel):
    wall_height: float
    walls: List[WallEntry]


class WallPlanner(BasePlanner):
    def __init__(self, llm: BaseChatModel):
        super().__init__(llm)

    def plan(self, scene) -> WallPlan:
        raw = self._structured_plan(
            scene=scene,
            schema=RawWallPlan,
            prompt_template=prompts.wall_height_prompt,
            cache_key="raw_wall_plan",
            input_variables={"input": scene["query"]},
        )

        wall_height = min(max(raw.wall_height, 2.0), 4.5)
        walls = self._build_walls(scene["rooms"], wall_height)

        return WallPlan(wall_height=wall_height, walls=walls)

    def update_walls(self, wall_plan: WallPlan, open_room_pairs: list) -> Tuple[WallPlan, dict]:
        updated_walls = []
        deleted_wall_ids = []

        for wall in wall_plan.walls:
            if not wall.connected_rooms:
                updated_walls.append(wall)
                continue
            room0_id = wall.room_id
            room1_id = wall.connected_rooms[0]["roomId"]
            if (room0_id, room1_id) in open_room_pairs or (room1_id, room0_id) in open_room_pairs:
                deleted_wall_ids.append(wall.id)
            else:
                updated_walls.append(wall)

        open_wall_segments = []
        for wall_id in deleted_wall_ids:
            wall = next(w for w in wall_plan.walls if w.id == wall_id)
            seg = wall.segment
            if seg not in open_wall_segments and list(reversed(seg)) not in open_wall_segments:
                open_wall_segments.append(seg)

        open_wall_rectangles = []
        for segment in open_wall_segments:
            top, bottom = self._create_rectangles(segment)
            open_wall_rectangles.append(top)
            open_wall_rectangles.append(bottom)

        open_walls = {
            "segments": open_wall_segments,
            "openWallBoxes": open_wall_rectangles,
        }

        return WallPlan(wall_height=wall_plan.wall_height, walls=updated_walls), open_walls

    def _build_walls(self, rooms: list, wall_height: float) -> List[WallEntry]:
        walls: list[WallEntry] = []
        for room in rooms:
            room_id = room["id"]
            material = room["wallMaterial"]
            full_vertices = room["full_vertices"]

            for j in range(len(full_vertices)):
                p1 = full_vertices[j]
                p2 = full_vertices[(j + 1) % len(full_vertices)]
                polygon = self._generate_wall_polygon(p1, p2, wall_height)
                connected_rooms = self._get_connected_rooms(polygon, rooms, room_id)
                wall_width, wall_direction = self._get_wall_direction(p1, p2, full_vertices)

                walls.append(WallEntry(
                    id=f"wall|{room_id}|{wall_direction}|{j}",
                    room_id=room_id,
                    material=material,
                    polygon=polygon,
                    connected_rooms=connected_rooms,
                    width=wall_width,
                    height=wall_height,
                    direction=wall_direction,
                    segment=[p1, p2],
                ))

        # update wallId in connected_rooms
        for wall in walls:
            for connection in wall.connected_rooms:
                connect_room_id = connection["roomId"]
                line1 = connection["line1"]
                for candidate in walls:
                    if candidate.room_id == connect_room_id:
                        if line1[0] in candidate.polygon and line1[1] in candidate.polygon:
                            connection["wallId"] = candidate.id

        # add exterior walls
        updated_walls = []
        for wall in walls:
            if not wall.connected_rooms:
                exterior = WallEntry(
                    id=wall.id + "|exterior",
                    room_id=wall.room_id,
                    material={"name": "Walldrywall4Tiled"},
                    polygon=list(reversed(wall.polygon)),
                    connected_rooms=[],
                    width=wall.width,
                    height=wall.height,
                    direction=wall.direction,
                    segment=list(reversed(wall.segment)),
                )
                updated_walls.append(exterior)
            updated_walls.append(wall)

        return updated_walls


    def _generate_wall_polygon(self, point, next_point, wall_height) -> List[dict]:
        return [
            {"x": point[0], "y": 0, "z": point[1]},
            {"x": point[0], "y": wall_height, "z": point[1]},
            {"x": next_point[0], "y": wall_height, "z": next_point[1]},
            {"x": next_point[0], "y": 0, "z": next_point[1]},
        ]

    def _get_connected_rooms(self, wall_polygon, rooms, room_id) -> list:
        connected_rooms = []
        vertices0 = [(v["x"], v["z"]) for v in wall_polygon if v["y"] == 0]
        lines0 = [LineString([vertices0[0], vertices0[1]])]

        for room in rooms:
            if room["id"] == room_id:
                continue
            vertices1 = [(v["x"], v["z"]) for v in room["floorPolygon"]]
            lines1 = [
                LineString([vertices1[i], vertices1[(i + 1) % len(vertices1)]])
                for i in range(len(vertices1))
            ]
            shared = self._check_connected(lines0, lines1)
            if shared:
                connection = shared[0]
                connection["roomId"] = room["id"]
                connected_rooms.append(connection)

        return connected_rooms

    def _line_to_dict(line):
        return [
                {"x": line.xy[0][0], "y": 0, "z": line.xy[1][0]},
                {"x": line.xy[0][1], "y": 0, "z": line.xy[1][1]},
            ]
    
    def _check_connected(self, lines0, lines1) -> Optional[list]:
        
        shared_segments = []
        for line0 in lines0:
            for line1 in lines1:
                if line0.intersects(line1):
                    intersection = line0.intersection(line1)
                    if intersection.geom_type == "LineString":
                        # shared_segments.append({
                        #     "intersection": [
                        #         {"x": intersection.xy[0][0], "y": 0, "z": intersection.xy[1][0]},
                        #         {"x": intersection.xy[0][1], "y": 0, "z": intersection.xy[1][1]},
                        #     ],
                        #     "line0": [
                        #         {"x": line0.xy[0][0], "y": 0, "z": line0.xy[1][0]},
                        #         {"x": line0.xy[0][1], "y": 0, "z": line0.xy[1][1]},
                        #     ],
                        #     "line1": [
                        #         {"x": line1.xy[0][0], "y": 0, "z": line1.xy[1][0]},
                        #         {"x": line1.xy[0][1], "y": 0, "z": line1.xy[1][1]},
                        #     ],
                        # })
                        shared_segments.append({
                            "intersection": self._line_to_dict(intersection),
                            "line0": self._line_to_dict(line0),
                            "line1": self._line_to_dict(line1),
                        })

        return shared_segments if shared_segments else None

    def _get_wall_direction(self, p1, p2, room_vertices) -> Tuple[float, Optional[str]]:
        wall_width = float(np.linalg.norm(np.array(p1) - np.array(p2)))
        room_polygon = Polygon(room_vertices)
        wall_center = [(p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2]
        direction = None

        if p1[1] == p2[1]:
            if room_polygon.contains(Point([wall_center[0], wall_center[1] + 0.01])):
                direction = "south"
            elif room_polygon.contains(Point([wall_center[0], wall_center[1] - 0.01])):
                direction = "north"
        elif p1[0] == p2[0]:
            if room_polygon.contains(Point([wall_center[0] + 0.01, wall_center[1]])):
                direction = "west"
            elif room_polygon.contains(Point([wall_center[0] - 0.01, wall_center[1]])):
                direction = "east"

        return wall_width, direction

    def _create_rectangles(self, segment) -> Tuple[list, list]:
        pt1 = np.array(segment[0])
        pt2 = np.array(segment[1])
        vec = pt2 - pt1
        perp_vec = np.array([-vec[1], vec[0]], dtype=np.float32)
        perp_vec /= np.linalg.norm(perp_vec)
        perp_vec *= 0.5

        top = [list(pt1 + perp_vec), list(pt2 + perp_vec), list(pt2), list(pt1)]
        bottom = [list(pt1), list(pt2), list(pt2 - perp_vec), list(pt1 - perp_vec)]
        return top, bottom
