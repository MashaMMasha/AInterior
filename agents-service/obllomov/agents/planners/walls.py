from typing import List, Optional, Tuple

from colorama import Fore
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

import obllomov.agents.prompts as prompts
from obllomov.schemas.domain.entries import (WallConnection, WallEntry, WallPlan, OpenWalls)
from obllomov.schemas.domain.scene import ScenePlan

from obllomov.schemas.domain.raw import RawWallPlan
from obllomov.shared.geometry import (Polygon2D, Segment2D, Vertex2D, Vertex3D,
                                      create_offset_rectangles,
                                      generate_wall_polygon,
                                      get_wall_direction)
from obllomov.shared.log import logger

from .base import BasePlanner
from .floor import RoomPlan


class WallPlanner(BasePlanner):
    def __init__(self, llm: BaseChatModel):
        super().__init__(llm)

    def plan(
        self,
        scene_plan: ScenePlan,
        raw: Optional[RawWallPlan] = None,
        additional_requirements: str = "N/A",
    ) -> Tuple[WallPlan, RawWallPlan]:
        if raw is None:
            raw = self._structured_plan(
                schema=RawWallPlan,
                prompt_template=prompts.wall_height_prompt,
                input_variables={
                    "query": scene_plan.query,
                    "additional_requirements": additional_requirements,
                },
            )

        wall_height = min(max(raw.wall_height, 2.0), 4.5)
        walls = self._build_walls(scene_plan.rooms, wall_height)

        return WallPlan(wall_height=wall_height, walls=walls), raw



    def update_walls(self, wall_plan: WallPlan, open_room_pairs: list) -> Tuple[WallPlan, dict]:
        updated_walls = []
        deleted_wall_ids = []

        for wall in wall_plan.walls:
            if not wall.connected_rooms:
                updated_walls.append(wall)
                continue
            room0_id = wall.room_id
            room1_id = wall.connected_rooms[0].room_id
            if (room0_id, room1_id) in open_room_pairs or (room1_id, room0_id) in open_room_pairs:
                deleted_wall_ids.append(wall.id)
            else:
                updated_walls.append(wall)

        open_wall_segments = []
        for wall_id in deleted_wall_ids:
            wall = next(w for w in wall_plan.walls if w.id == wall_id)
            seg = wall.segment
            rev = seg.reversed()
            already = any(
                s == seg or s == rev for s in open_wall_segments
            )
            if not already:
                open_wall_segments.append(seg)

        open_wall_rectangles = []
        for segment in open_wall_segments:
            top, bottom = create_offset_rectangles(segment, 0.5)
            open_wall_rectangles.append(top)
            open_wall_rectangles.append(bottom)

        # OpenWalls(segments=open_wall_segments, boxes=open_wall_rectangles)
        
        open_walls = {
            "segments": [s.model_dump() for s in open_wall_segments],
            "openWallBoxes": open_wall_rectangles,
        }

        return WallPlan(wall_height=wall_plan.wall_height, walls=updated_walls), open_walls

    def _build_walls(self, rooms: List[RoomPlan], wall_height: float) -> List[WallEntry]:
        walls: list[WallEntry] = []
        for room in rooms:
            room_id = room.id
            material = room.wall_material
            full_vertices = list(room.full_vertices)
            room_polygon = Polygon2D(vertices=list(room.vertices))

            for j in range(len(full_vertices)):
                p1 = full_vertices[j]
                p2 = full_vertices[(j + 1) % len(full_vertices)]
                segment = Segment2D(v1=p1, v2=p2)
                polygon = generate_wall_polygon(p1, p2, wall_height)
                connected_rooms = self._get_connected_rooms(polygon, rooms, room_id)
                wall_width, wall_direction = get_wall_direction(p1, p2, room_polygon)

                walls.append(WallEntry(
                    id=f"wall|{room_id}|{wall_direction}|{j}",
                    room_id=room_id,
                    material=material,
                    polygon=polygon,
                    connected_rooms=connected_rooms,
                    width=wall_width,
                    height=wall_height,
                    direction=wall_direction,
                    segment=segment,
                ))

        for wall in walls:
            for connection in wall.connected_rooms:
                connect_room_id = connection.room_id
                line1 = connection.line1
                for candidate in walls:
                    if candidate.room_id == connect_room_id:
                        line1_dicts = [v.model_dump() for v in line1]
                        candidate_dicts = [v.model_dump() for v in candidate.polygon]
                        if line1_dicts[0] in candidate_dicts and line1_dicts[1] in candidate_dicts:
                            connection.wall_id = candidate.id

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
                    segment=wall.segment.reversed(),
                )
                updated_walls.append(exterior)
            updated_walls.append(wall)

        return updated_walls


    def _get_connected_rooms(self, wall_polygon: list[Vertex3D], rooms: List[RoomPlan], room_id: str) -> list[WallConnection]:
        connected_rooms = []
        floor_verts = [v.to_2d() for v in wall_polygon if v.y == 0]
        seg0 = Segment2D(v1=floor_verts[0], v2=floor_verts[1])

        for room in rooms:
            if room.id == room_id:
                continue
            room_verts = list(room.floor_polygon)
            room_segments = [
                Segment2D(v1=room_verts[i].to_2d(), v2=room_verts[(i + 1) % len(room_verts)].to_2d())
                for i in range(len(room_verts))
            ]
            shared = self._check_connected(seg0, room_segments)
            if shared:
                connection = shared[0]
                connection.room_id = room.id
                connected_rooms.append(connection)

        return connected_rooms

    def _check_connected(self, seg0: Segment2D, segments: list[Segment2D]) -> Optional[list[WallConnection]]:
        shared = []
        for seg1 in segments:
            if seg0.intersects(seg1):
                intersection = seg0.intersection(seg1)
                if intersection is not None:
                    shared.append(WallConnection(
                        intersection=seg0.intersection(seg1).to_vertex3d_list(),
                        line0=seg0.to_vertex3d_list(),
                        line1=seg1.to_vertex3d_list(),
                    ))

        return shared if shared else None
