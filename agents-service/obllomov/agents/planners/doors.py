import random
from typing import List, Optional, Tuple

import numpy as np
from colorama import Fore
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

import obllomov.agents.prompts as prompts
from obllomov.agents.retrievers import BaseRetriever
from obllomov.schemas.domain.entries import DoorEntry, DoorPlan, ScenePlan
from obllomov.schemas.domain.raw import RawDoorEntry, RawDoorPlan
from obllomov.shared.geometry import (Polygon2D, Segment2D, Vertex2D, Vertex3D,
                                      create_offset_rectangles)
from obllomov.shared.log import logger

from .base import BasePlanner


class DoorPlanner(BasePlanner):
    def __init__(self, door_retriever: BaseRetriever, door_data: dict, llm: BaseChatModel):
        super().__init__(llm)

        self.door_retriever = door_retriever
        self.door_data = door_data
        self.door_ids = list(self.door_data.keys())
        self.used_assets = []


    def plan(
        self,
        scene_plan: ScenePlan,
        raw: Optional[RawDoorPlan] = None,
        additional_requirements: str = "N/A",
    ) -> Tuple[DoorPlan, RawDoorPlan]:
        room_types_str = str([r.room_type for r in scene_plan.rooms]).replace("'", "")[1:-1]
        room_pairs = self._get_room_pairs(scene_plan.rooms, scene_plan.walls)
        room_sizes_str = self._get_room_size_str(scene_plan)
        room_pairs_str = str(room_pairs).replace("'", "")[1:-1]

        if raw is None:
            raw = self._structured_plan(
                schema=RawDoorPlan,
                prompt_template=prompts.doorway_prompt,
                input_variables={
                    "query": scene_plan.query,
                    "rooms": room_types_str,
                    "room_sizes": room_sizes_str,
                    "room_pairs": room_pairs_str,
                    "additional_requirements": additional_requirements,
                },
            )

        doors, open_room_pairs = self._parse_raw(raw, scene_plan.rooms, scene_plan.walls)
        doors = self._ensure_all_rooms_connected(doors, open_room_pairs, scene_plan.rooms, scene_plan.walls)

        return DoorPlan(doors=doors, room_pairs=room_pairs, open_room_pairs=open_room_pairs), raw

    def _parse_raw(self, raw: RawDoorPlan, rooms, walls) -> Tuple[List[DoorEntry], list]:
        doors = []
        open_room_pairs = []
        room_types = [r.room_type for r in rooms] + ["exterior"]

        for i, entry in enumerate(raw.doors):
            if entry.room_type0 not in room_types or entry.room_type1 not in room_types:
                logger.warning(
                    f"{Fore.RED}{entry.room_type0} or {entry.room_type1} not found{Fore.RESET}"
                )
                continue

            if entry.connection_type == "open":
                open_room_pairs.append((entry.room_type0, entry.room_type1))
                continue

            exterior = "exterior" in (entry.room_type0, entry.room_type1)

            if exterior:
                connection = self._get_connection_exterior(entry.room_type0, entry.room_type1, walls)
                entry.connection_type = "doorway"
            else:
                connection = self._get_connection(entry.room_type0, entry.room_type1, walls)

            if connection is None:
                continue

            door_id = self._select_door(entry.connection_type, entry.size, entry.style)
            door_dimension = self.door_data[door_id]["boundingBox"]
            door_polygon = self._get_door_polygon(
                connection["segment"], door_dimension, entry.connection_type
            )

            if door_polygon is None:
                continue

            polygon, position, door_boxes, door_segment = door_polygon

            doors.append(DoorEntry(
                asset_id=door_id,
                id=f"door|{i}|{entry.room_type0}|{entry.room_type1}",
                openable=entry.connection_type == "doorway" and not exterior,
                openness=1 if entry.connection_type == "doorway" and not exterior else 0,
                room0=entry.room_type0,
                room1=entry.room_type1,
                wall0=connection["wall0"],
                wall1=connection["wall1"],
                hole_polygon=polygon,
                asset_position=position,
                door_boxes=door_boxes,
                door_segment=door_segment,
            ))

        return doors, open_room_pairs


    def _ensure_all_rooms_connected(
        self, doors: List[DoorEntry], open_room_pairs: list, rooms, walls,
    ) -> List[DoorEntry]:
        connected_rooms = set()
        for door in doors:
            connected_rooms.add(door.room0)
            connected_rooms.add(door.room1)
        for pair in open_room_pairs:
            connected_rooms.update(pair)

        for room in rooms:
            if room.room_type in connected_rooms:
                continue

            candidate_walls = [
                w for w in walls
                if w.room_id == room.room_type
                and "exterior" not in w.id
                and len(w.connected_rooms) != 0
            ]
            if not candidate_walls:
                continue

            widest_wall = max(candidate_walls, key=lambda w: w.width)
            room_to_connect = widest_wall.connected_rooms[0].room_id

            door_id = self._get_random_door(widest_wall.width)
            door_dimension = self.door_data[door_id]["boundingBox"]
            door_type = self.door_data[door_id]["type"]

            intersection = widest_wall.connected_rooms[0].intersection
            seg_data = [
                {"x": intersection[0].x, "y": 0.0, "z": intersection[0].z},
                {"x": intersection[1].x, "y": 0.0, "z": intersection[1].z},
            ]
            door_polygon = self._get_door_polygon(
                seg_data,
                door_dimension,
                door_type,
            )
            if door_polygon is None:
                continue

            polygon, position, door_boxes, door_segment = door_polygon

            doors.append(DoorEntry(
                asset_id=door_id,
                id=f"door|fallback|{room.room_type}|{room_to_connect}",
                openable=False,
                openness=0,
                room0=room.room_type,
                room1=room_to_connect,
                wall0=widest_wall.id,
                wall1=widest_wall.connected_rooms[0].wall_id,
                hole_polygon=polygon,
                asset_position=position,
                door_boxes=door_boxes,
                door_segment=door_segment,
            ))
            connected_rooms.add(room.room_type)
            connected_rooms.add(room_to_connect)

        return doors


    def _select_door(self, door_type: str, door_size: str, query: str) -> str:
        candidates, _ = self.door_retriever.retrieve_single(query)

        logger.debug(f"candidates: {candidates}")

        valid = [
            candidate
            for candidate in candidates
            if self.door_data[candidate]["type"] == door_type
            and self.door_data[candidate]["size"] == door_size
        ]

        logger.debug(f"valid: {valid}")
        if len(valid) == 0:
            return candidates[0]
        
        for door in valid:
            if door not in self.used_assets:
                return door

        return valid[0]

    def _get_random_door(self, wall_width: float) -> str:
        single = [d for d in self.door_ids if self.door_data[d]["size"] == "single"]
        double = [d for d in self.door_ids if self.door_data[d]["size"] == "double"]
        pool = double + single if wall_width >= 2.0 else single
        return random.choice(pool)


    def _get_door_polygon(
        self, segment_data, door_dimension, connection_type
    ) -> Optional[Tuple]:
        door_width = door_dimension["x"]
        door_height = door_dimension["y"]

        if isinstance(segment_data, list):
            start = Vertex2D(x=segment_data[0]["x"], z=segment_data[0]["z"])
            end = Vertex2D(x=segment_data[1]["x"], z=segment_data[1]["z"])
        else:
            start = Vertex2D(**segment_data["v1"])
            end = Vertex2D(**segment_data["v2"])

        seg = Segment2D(v1=start, v2=end)
        original_length = seg.length

        if door_width >= original_length:
            logger.warning(f"{Fore.RED}Wall too narrow for door{Fore.RESET}")
            return None

        door_start = random.uniform(0, original_length - door_width)
        door_end = door_start + door_width

        polygon = [
            Vertex3D(x=door_start, y=0, z=0),
            Vertex3D(x=door_end, y=door_height, z=0),
        ]
        position = Vertex3D(
            x=(polygon[0].x + polygon[1].x) / 2,
            y=(polygon[0].y + polygon[1].y) / 2,
            z=(polygon[0].z + polygon[1].z) / 2,
        )

        p1 = seg.point_at(door_start)
        p2 = seg.point_at(door_end)
        door_segment = Segment2D(v1=p1, v2=p2)
        door_boxes = create_offset_rectangles(door_segment, 1.0)

        return polygon, position, door_boxes, door_segment

    def _get_connection(self, room0_id: str, room1_id: str, walls) -> Optional[dict]:
        room0_walls = [w for w in walls if w.room_id == room0_id]
        valid_connections = []

        for wall in room0_walls:
            for connection in wall.connected_rooms:
                if connection.room_id == room1_id:
                    seg = Segment2D(
                        v1=Vertex2D(x=connection.intersection[0].x, z=connection.intersection[0].z),
                        v2=Vertex2D(x=connection.intersection[1].x, z=connection.intersection[1].z),
                    )
                    seg_data = [
                        {"x": connection.intersection[0].x, "y": 0.0, "z": connection.intersection[0].z},
                        {"x": connection.intersection[1].x, "y": 0.0, "z": connection.intersection[1].z},
                    ]
                    valid_connections.append({
                        "wall0": wall.id,
                        "wall1": connection.wall_id,
                        "segment": seg_data,
                        "_length": seg.length,
                    })

        if not valid_connections:
            logger.warning(f"{Fore.RED}No wall between {room0_id} and {room1_id}{Fore.RESET}")
            return None

        if len(valid_connections) == 1:
            return valid_connections[0]

        return max(valid_connections, key=lambda c: c["_length"])

    def _get_connection_exterior(self, room0_id: str, room1_id: str, walls) -> Optional[dict]:
        room_id = room0_id if room0_id != "exterior" else room1_id
        interior_wall_ids = [
            w.id for w in walls if w.room_id == room_id and "exterior" not in w.id
        ]
        exterior_wall_ids = [
            w.id for w in walls if w.room_id == room_id and "exterior" in w.id
        ]

        valid_connections = []
        for interior_id in interior_wall_ids:
            for exterior_id in exterior_wall_ids:
                if interior_id in exterior_id:
                    wall = next(w for w in walls if w.id == exterior_id)
                    seg = wall.segment
                    seg_data = [
                        {"x": seg.v1.x, "y": 0.0, "z": seg.v1.z},
                        {"x": seg.v2.x, "y": 0.0, "z": seg.v2.z},
                    ]
                    valid_connections.append({
                        "wall0": exterior_id,
                        "wall1": interior_id,
                        "segment": seg_data,
                        "_length": seg.length,
                    })

        if not valid_connections:
            return None

        if len(valid_connections) == 1:
            return valid_connections[0]

        return max(valid_connections, key=lambda c: c["_length"])

    def _get_room_pairs(self, rooms, walls) -> list:
        room_pairs = [
            (w.room_id, w.connected_rooms[0].room_id)
            for w in walls
            if len(w.connected_rooms) == 1 and w.width >= 2.0
        ]
        for wall in walls:
            if "exterior" in wall.id:
                room_pairs.append(("exterior", wall.room_id))

        no_dup = []
        for pair in room_pairs:
            if pair not in no_dup and (pair[1], pair[0]) not in no_dup:
                no_dup.append(pair)

        clean = []
        seen_rooms = []
        for pair in no_dup:
            if pair[0] not in seen_rooms or pair[1] not in seen_rooms:
                clean.append(pair)
            if pair[0] not in seen_rooms:
                seen_rooms.append(pair[0])
            if pair[1] not in seen_rooms:
                seen_rooms.append(pair[1])

        return clean

    def _get_room_size_str(self, scene_plan: ScenePlan) -> str:
        wall_height = scene_plan.wall_height
        result = ""
        for room in scene_plan.rooms:
            poly = Polygon2D(vertices=[Vertex2D(**v.model_dump()) for v in room.floor_polygon])
            w, d = poly.bbox_size()
            result += f"{room.room_type}: {w} m x {d} m x {wall_height} m\n"
        return result
