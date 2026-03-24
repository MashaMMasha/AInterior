import copy
import random
from typing import List, Optional, Tuple

import compress_json
import numpy as np
from colorama import Fore
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

import obllomov.agents.prompts as prompts
from obllomov.shared.log import logger
from obllomov.shared.path import HOLODECK_BASE_DATA_DIR
from .base import BasePlanner

class RawWindowEntry(BaseModel):
    room_id: str = Field(description="Room type id")
    wall_direction: str = Field(description="One of: north, south, east, west")
    window_type: str = Field(description="One of: fixed, hung, and slider")
    window_size: List[float] = Field(description="[width, height] in meters")
    quantity: int = Field(description="Number of windows on this wall")
    window_height: float = Field(description="Height from floor to bottom of window in cm")


class RawWindowPlan(BaseModel):
    windows: List[RawWindowEntry] = Field(description="List of windows per room wall")


class WindowEntry(BaseModel):
    asset_id: str
    id: str
    room0: str
    room1: str
    wall0: str
    wall1: str
    room_id: str
    hole_polygon: List[dict]
    asset_position: dict
    window_segment: list
    window_boxes: list


class WindowPlan(BaseModel):
    windows: List[WindowEntry]
    walls: list


class WindowPlanner(BasePlanner):
    def __init__(self, llm: BaseChatModel):
        super().__init__(llm)

        self.window_data = compress_json.load(
            f"{HOLODECK_BASE_DATA_DIR}/windows/window-database.json"
        )
        self.window_ids = list(self.window_data.keys())
        self.hole_offset = 0.05
        self.used_assets = []

    def plan(self, scene, additional_requirements="N/A") -> WindowPlan:
        organized_walls, available_wall_str = self._get_wall_for_windows(scene)

        raw = self._structured_plan(
            scene=scene,
            schema=RawWindowPlan,
            prompt_template=prompts.window_prompt,
            cache_key="raw_window_plan",
            input_variables={
                "input": scene["query"],
                "walls": available_wall_str,
                "wall_height": int(scene["wall_height"] * 100),
                "additional_requirements": additional_requirements,
            },
        )

        return self._parse_raw(raw, scene, organized_walls)



    def _parse_raw(self, raw: RawWindowPlan, scene: dict, organized_walls: dict) -> WindowPlan:
        walls = scene["walls"]
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
        wall_segment = wall_info["segment"]

        window_height = min(window_height / 100.0, wall_height - window_y)
        quantity = min(quantity, int(wall_width / window_x))

        if quantity == 0:
            return [], [], [], [], [], walls

        wall_start = np.array(wall_segment[0])
        wall_end = np.array(wall_segment[1])
        original_vector = wall_end - wall_start
        original_length = np.linalg.norm(original_vector)
        normalized_vector = original_vector / original_length

        if quantity == 1:
            w_start = random.uniform(0, wall_width - window_x)
            w_end = w_start + window_x
            polygon = [
                {"x": w_start, "y": window_height, "z": 0},
                {"x": w_end, "y": window_height + window_y, "z": 0},
            ]
            position = {
                "x": (polygon[0]["x"] + polygon[1]["x"]) / 2,
                "y": (polygon[0]["y"] + polygon[1]["y"]) / 2,
                "z": 0,
            }
            window_segment = [
                list(wall_start + normalized_vector * w_start),
                list(wall_start + normalized_vector * w_end),
            ]
            window_boxes = self._create_rectangles(window_segment)
            return [polygon], [position], [window_segment], [window_boxes], [wall_info["id"]], walls

        # multiple windows — split wall into subwalls
        subwall_length = original_length / quantity
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
            current_wall["segment"] = [seg_start.tolist(), seg_end.tolist()]
            current_wall["width"] = subwall_length
            current_wall["polygon"] = self._generate_wall_polygon(
                seg_start.tolist(), seg_end.tolist(), wall_height
            )
            current_wall["connect_exterior"] = current_wall["id"] + "|exterior"

            exterior = copy.deepcopy(current_wall)
            exterior["id"] = current_wall["id"] + "|exterior"
            exterior["material"] = {"name": "Walldrywall4Tiled"}
            exterior["polygon"] = list(reversed(current_wall["polygon"]))
            exterior["segment"] = list(reversed(current_wall["segment"]))
            exterior.pop("connect_exterior", None)

            updated_walls.extend([current_wall, exterior])
            new_wall_ids.append(current_wall["id"])

        window_polygons, window_positions, window_segments, window_boxes_list = [], [], [], []
        for i, (seg_start, _) in enumerate(segments):
            w_start = random.uniform(0, subwall_length - window_x)
            w_end = w_start + window_x
            polygon = [
                {"x": w_start, "y": window_height, "z": 0},
                {"x": w_end, "y": window_height + window_y, "z": 0},
            ]
            position = {
                "x": (polygon[0]["x"] + polygon[1]["x"]) / 2,
                "y": (polygon[0]["y"] + polygon[1]["y"]) / 2,
                "z": 0,
            }
            window_segment = [
                list(seg_start + normalized_vector * w_start),
                list(seg_start + normalized_vector * w_end),
            ]
            window_polygons.append(polygon)
            window_positions.append(position)
            window_segments.append(window_segment)
            window_boxes_list.append(self._create_rectangles(window_segment))

        return window_polygons, window_positions, window_segments, window_boxes_list, new_wall_ids, updated_walls

    def _generate_wall_polygon(self, point, next_point, wall_height) -> List[dict]:
        return [
            {"x": point[0], "y": 0, "z": point[1]},
            {"x": point[0], "y": wall_height, "z": point[1]},
            {"x": next_point[0], "y": wall_height, "z": next_point[1]},
            {"x": next_point[0], "y": 0, "z": next_point[1]},
        ]

    def _create_rectangles(self, segment) -> Tuple[list, list]:
        pt1 = np.array(segment[0])
        pt2 = np.array(segment[1])
        vec = pt2 - pt1
        perp_vec = np.array([-vec[1], vec[0]], dtype=np.float64)
        perp_vec /= np.linalg.norm(perp_vec)
        perp_vec *= 0.1

        top = [list(pt1 + perp_vec), list(pt2 + perp_vec), list(pt2), list(pt1)]
        bottom = [list(pt1), list(pt2), list(pt2 - perp_vec), list(pt1 - perp_vec)]
        return top, bottom

    def _get_wall_for_windows(self, scene: dict) -> Tuple[dict, str]:
        walls_with_door = set()
        for door in scene["doors"]:
            walls_with_door.add(door["wall0"])
            walls_with_door.add(door["wall1"])

        organized_walls = {}
        for wall in scene["walls"]:
            if "connect_exterior" not in wall or wall["id"] in walls_with_door:
                continue
            if wall["width"] < 2.0:
                continue

            room_id = wall["roomId"]
            direction = wall["direction"]

            if room_id not in organized_walls:
                organized_walls[room_id] = {}

            if direction not in organized_walls[room_id] or \
                    wall["width"] > organized_walls[room_id][direction]["wall_width"]:
                organized_walls[room_id][direction] = {
                    "wall_id": wall["id"],
                    "wall_width": wall["width"],
                }

        available_wall_str = ""
        for room_id, directions in organized_walls.items():
            current_str = f"{room_id}: "
            for direction, info in directions.items():
                current_str += f"{direction}, {int(info['wall_width'] * 100)} cm; "
            available_wall_str += current_str + "\n"

        return organized_walls, available_wall_str
