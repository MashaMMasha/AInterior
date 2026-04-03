import copy
import random
from typing import List, Optional, Tuple

import numpy as np
from colorama import Fore
from langchain_core.language_models import BaseChatModel

import obllomov.agents.prompts as prompts
from obllomov.schemas.domain.entries import ScenePlan, WindowEntry, WindowPlan
from obllomov.schemas.domain.raw import RawWindowEntry, RawWindowPlan
from obllomov.shared.geometry import (Segment2D, Vertex2D, Vertex3D,
                                      create_offset_rectangles,
                                      generate_wall_polygon)
from obllomov.shared.log import logger

from .base import BasePlanner


class WindowPlanner(BasePlanner):
    def __init__(self, window_data: dict, llm: BaseChatModel):
        super().__init__(llm)

        self.window_data = window_data
        self.window_ids = list(self.window_data.keys())
        self.hole_offset = 0.05
        self.used_assets = []

    def plan(
        self,
        scene_plan: ScenePlan,
        raw: Optional[RawWindowPlan] = None,
        additional_requirements: str = "N/A",
    ) -> Tuple[WindowPlan, RawWindowPlan]:
        organized_walls, available_wall_str = self._get_wall_for_windows(scene_plan)

        logger.debug(organized_walls)
        logger.debug(available_wall_str)

        if raw is None:
            raw = self._structured_plan(
                schema=RawWindowPlan,
                prompt_template=prompts.window_prompt,
                input_variables={
                    "input": scene_plan.query,
                    "walls": available_wall_str,
                    "wall_height": int(scene_plan.wall_height * 100),
                    "additional_requirements": additional_requirements,
                },
            )

        walls_data = [w.model_dump() for w in scene_plan.walls]
        window_plan = self._parse_raw(raw, walls_data, organized_walls)
        return window_plan, raw

    def _parse_raw(self, raw: RawWindowPlan, walls: list, organized_walls: dict) -> WindowPlan:
        windows = []
        window_ids_seen = []
        rooms_with_windows = []

        for entry in raw.windows:
            room_id = entry.room_id

            if room_id in rooms_with_windows:
                logger.warning(f"Room {room_id} already has windows, skipping")
                continue
            rooms_with_windows.append(room_id)

            try:
                wall_id = organized_walls[room_id][entry.wall_direction]["wall_id"]
            except KeyError:
                logger.warning(f"No available wall for {room_id} {entry.wall_direction}")
                continue

            wall_info = next((w for w in walls if w["id"] == wall_id), None)
            if wall_info is None:
                continue

            window_id = self._select_window(entry.window_type, entry.window_size)

            window_polygons, window_positions, window_segments, window_boxes, new_wall_ids, walls = (
                self._get_window_polygon(window_id, entry.window_height, entry.quantity, wall_info, walls)
            )

            if not window_polygons:
                logger.warning(f"No windows generated for {room_id}")
                continue

            for i in range(len(window_polygons)):
                current_wall_id = new_wall_ids[i]
                window_entry_id = f"window|{current_wall_id}|{i}"

                if window_entry_id in window_ids_seen:
                    logger.warning(f"Duplicated window id: {window_entry_id}")
                    continue

                window_ids_seen.append(window_entry_id)
                windows.append(WindowEntry(
                    asset_id=window_id,
                    id=window_entry_id,
                    room0=room_id,
                    room1=room_id,
                    wall0=current_wall_id,
                    wall1=current_wall_id + "|exterior",
                    room_id=room_id,
                    hole_polygon=window_polygons[i],
                    asset_position=window_positions[i],
                    window_segment=window_segments[i],
                    window_boxes=window_boxes[i],
                ))

        return WindowPlan(windows=windows, walls=walls)


    def _select_window(self, window_type: str, window_size: List[float]) -> str:
        candidates = [
            wid for wid in self.window_ids
            if self.window_data[wid]["type"] == window_type
        ]
        size_diffs = [
            np.linalg.norm(np.array(window_size) - np.array(self.window_data[wid]["size"]))
            for wid in candidates
        ]
        sorted_ids = [wid for _, wid in sorted(zip(size_diffs, candidates))]

        top = sorted_ids[0]
        filtered = [wid for wid in sorted_ids if wid not in self.used_assets]
        return filtered[0] if filtered else top


    def _get_window_polygon(
        self, window_id, window_height, quantity, wall_info, walls
    ) -> Tuple[list, list, list, list, list, list]:
        window_x = self.window_data[window_id]["boundingBox"]["x"] - self.hole_offset
        window_y = self.window_data[window_id]["boundingBox"]["y"] - self.hole_offset

        wall_width = wall_info["width"]
        wall_height = wall_info["height"]
        wall_segment_data = wall_info["segment"]

        window_height = min(window_height / 100.0, wall_height - window_y)
        quantity = min(quantity, int(wall_width / window_x))

        if quantity == 0:
            return [], [], [], [], [], walls

        if isinstance(wall_segment_data, dict) and "v1" in wall_segment_data:
            wall_seg = Segment2D(
                v1=Vertex2D(**wall_segment_data["v1"]),
                v2=Vertex2D(**wall_segment_data["v2"]),
            )
        else:
            wall_seg = Segment2D(
                v1=Vertex2D(x=wall_segment_data[0][0], z=wall_segment_data[0][1]),
                v2=Vertex2D(x=wall_segment_data[1][0], z=wall_segment_data[1][1]),
            )

        original_length = wall_seg.length
        normalized_vector = wall_seg.direction_vector

        if quantity == 1:
            w_start = random.uniform(0, wall_width - window_x)
            w_end = w_start + window_x
            polygon = [
                Vertex3D(x=w_start, y=window_height, z=0),
                Vertex3D(x=w_end, y=window_height + window_y, z=0),
            ]
            position = Vertex3D(
                x=(polygon[0].x + polygon[1].x) / 2,
                y=(polygon[0].y + polygon[1].y) / 2,
                z=0,
            )
            p1 = wall_seg.point_at(w_start)
            p2 = wall_seg.point_at(w_end)
            win_segment = Segment2D(v1=p1, v2=p2)
            window_boxes = create_offset_rectangles(win_segment, 0.1)
            return [polygon], [position], [win_segment], [window_boxes], [wall_info["id"]], walls

        subwall_length = original_length / quantity
        wall_start = wall_seg.v1.to_np()

        segments = [
            (
                wall_start + i * subwall_length * normalized_vector,
                wall_start + (i + 1) * subwall_length * normalized_vector,
            )
            for i in range(quantity)
        ]

        updated_walls = [w for w in walls if wall_info["id"] not in w["id"]]
        new_wall_ids = []

        for i, (seg_start, seg_end) in enumerate(segments):
            current_wall = copy.deepcopy(wall_info)
            current_wall["id"] = f"{wall_info['id']}|{i}"
            s1 = Vertex2D(x=float(seg_start[0]), z=float(seg_start[1]))
            s2 = Vertex2D(x=float(seg_end[0]), z=float(seg_end[1]))
            current_wall["segment"] = Segment2D(v1=s1, v2=s2).model_dump()
            current_wall["width"] = subwall_length
            current_wall["polygon"] = [
                v.model_dump() for v in generate_wall_polygon(s1, s2, wall_height)
            ]
            current_wall["connect_exterior"] = current_wall["id"] + "|exterior"

            exterior = copy.deepcopy(current_wall)
            exterior["id"] = current_wall["id"] + "|exterior"
            exterior["material"] = {"name": "Walldrywall4Tiled"}
            exterior["polygon"] = list(reversed(current_wall["polygon"]))
            rev_seg = Segment2D(v1=s2, v2=s1)
            exterior["segment"] = rev_seg.model_dump()
            exterior.pop("connect_exterior", None)

            updated_walls.extend([current_wall, exterior])
            new_wall_ids.append(current_wall["id"])

        window_polygons, window_positions, window_segments, window_boxes_list = [], [], [], []
        for i, (seg_start, _) in enumerate(segments):
            w_start = random.uniform(0, subwall_length - window_x)
            w_end = w_start + window_x
            polygon = [
                Vertex3D(x=w_start, y=window_height, z=0),
                Vertex3D(x=w_end, y=window_height + window_y, z=0),
            ]
            position = Vertex3D(
                x=(polygon[0].x + polygon[1].x) / 2,
                y=(polygon[0].y + polygon[1].y) / 2,
                z=0,
            )
            p1_np = seg_start + normalized_vector * w_start
            p2_np = seg_start + normalized_vector * w_end
            win_segment = Segment2D(
                v1=Vertex2D(x=float(p1_np[0]), z=float(p1_np[1])),
                v2=Vertex2D(x=float(p2_np[0]), z=float(p2_np[1])),
            )
            window_polygons.append(polygon)
            window_positions.append(position)
            window_segments.append(win_segment)
            window_boxes_list.append(create_offset_rectangles(win_segment, 0.1))

        return window_polygons, window_positions, window_segments, window_boxes_list, new_wall_ids, updated_walls

    def _get_wall_for_windows(self, scene_plan: ScenePlan) -> Tuple[dict, str]:
        walls_with_door = set()
        for door in scene_plan.doors:
            walls_with_door.add(door.wall0)
            walls_with_door.add(door.wall1)

        logger.debug(f"walls_with_door: {walls_with_door}")

        available_wall = []
        for wall in scene_plan.walls:
            if wall.id not in walls_with_door and "exterior" in wall.id:
                available_wall.append(wall)

        organized_walls = {}
        for wall in scene_plan.walls:
            if wall.width < 2.0:
                continue

            room_id = wall.room_id
            direction = wall.direction

            if room_id not in organized_walls:
                organized_walls[room_id] = {}

            if direction not in organized_walls[room_id] or \
                    wall.width > organized_walls[room_id][direction]["wall_width"]:
                organized_walls[room_id][direction] = {
                    "wall_id": wall.id,
                    "wall_width": wall.width,
                }

        available_wall_str = ""
        for room_id, directions in organized_walls.items():
            current_str = f"{room_id}: "
            for direction, info in directions.items():
                current_str += f"{direction}, {int(info['wall_width'] * 100)} cm; "
            available_wall_str += current_str + "\n"

        return organized_walls, available_wall_str
