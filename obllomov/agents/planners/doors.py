import copy
import random
from typing import List, Optional, Tuple

import compress_json
import compress_pickle
import numpy as np
import torch
from colorama import Fore
from langchain_core.language_models import BaseChatModel
from PIL import Image
from pydantic import BaseModel, Field
from tqdm import tqdm

import obllomov.agents.prompts as prompts
from obllomov.shared.log import logger
from obllomov.shared.path import HOLODECK_BASE_DATA_DIR
from obllomov.storage.assets.base import BaseAssets

from .base import BasePlanner


class RawDoorEntry(BaseModel):
    room_type0: str = Field(description="First room type")
    room_type1: str = Field(description="Second room type, use 'exterior' for outside")
    connection_type: str = Field(description="One of: door, doorway, doorframe, open")
    size: str = Field(description="One of: single, double")
    style: str = Field(description="Style description, e.g. 'modern wooden'")


class RawDoorPlan(BaseModel):
    doors: List[RawDoorEntry] = Field(description="List of door connections between rooms")


class DoorEntry(BaseModel):
    asset_id: str
    id: str
    openable: bool
    openness: int
    room0: str
    room1: str
    wall0: str
    wall1: str
    hole_polygon: List[dict]
    asset_position: dict
    door_boxes: list
    door_segment: list


class DoorPlan(BaseModel):
    doors: List[DoorEntry]
    room_pairs: list
    open_room_pairs: List[Tuple[str, str]]



class DoorPlanner(BasePlanner):
    def __init__(self, clip_model, clip_preprocess, clip_tokenizer, llm: BaseChatModel, assets: BaseAssets):
        super().__init__(llm, assets)

        self.door_data = self.assets.read_json("doors/door-database.json")
        # self.door_data = compress_json.load(
        #     f"{HOLODECK_BASE_DATA_DIR}/doors/door-database.json"
        # )
        self.door_ids = list(self.door_data.keys())
        self.used_assets = []

        self.clip_model = clip_model
        self.clip_preprocess = clip_preprocess
        self.clip_tokenizer = clip_tokenizer
        self._load_features()

    def _load_features(self):
        if self.assets.exists("doors/door_feature_clip.pkl"):
            self.door_feature_clip = self.assets.read_pickle("doors/door_feature_clip.pkl")
        else:
            logger.info("Precompute image features for doors...")
            self.door_feature_clip = []
            for door_id in tqdm(self.door_ids):
                image = self.clip_preprocess(
                    Image.open(self.assets.read_bytes("/doors/images/{door_id}.png"))
                ).unsqueeze(0)
                with torch.no_grad():
                    image_features = self.clip_model.encode_image(image)
                    image_features /= image_features.norm(dim=-1, keepdim=True)
                self.door_feature_clip.append(image_features)
            self.door_feature_clip = torch.vstack(self.door_feature_clip)
            self.assets.write_pickle("doors/door_feature_clip.pkl", self.door_feature_clip)


    def plan(self, scene, additional_requirements="N/A") -> DoorPlan:
        room_types_str = str([r["roomType"] for r in scene["rooms"]]).replace("'", "")[1:-1]
        room_pairs = self._get_room_pairs(scene["rooms"], scene["walls"])
        room_sizes_str = self._get_room_size_str(scene)
        room_pairs_str = str(room_pairs).replace("'", "")[1:-1]

        raw = self._structured_plan(
            scene=scene,
            schema=RawDoorPlan,
            prompt_template=prompts.doorway_prompt,
            cache_key="raw_doorway_plan",
            input_variables={
                "input": scene["query"],
                "rooms": room_types_str,
                "room_sizes": room_sizes_str,
                "room_pairs": room_pairs_str,
                "additional_requirements": additional_requirements,
            },
        )

        doors, open_room_pairs = self._parse_raw(raw, scene)
        doors = self._ensure_all_rooms_connected(doors, open_room_pairs, scene)

        return DoorPlan(doors=doors, room_pairs=room_pairs, open_room_pairs=open_room_pairs)

    def _parse_raw(self, raw: RawDoorPlan, scene: dict) -> Tuple[List[DoorEntry], list]:
        doors = []
        open_room_pairs = []
        walls = scene["walls"]
        room_types = [r["roomType"] for r in scene["rooms"]] + ["exterior"]

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
        self, doors: List[DoorEntry], open_room_pairs: list, scene: dict
    ) -> List[DoorEntry]:
        connected_rooms = set()
        for door in doors:
            connected_rooms.add(door.room0)
            connected_rooms.add(door.room1)
        for pair in open_room_pairs:
            connected_rooms.update(pair)

        walls = scene["walls"]
        for room in scene["rooms"]:
            if room["roomType"] in connected_rooms:
                continue

            candidate_walls = [
                w for w in walls
                if w["roomId"] == room["roomType"]
                and "exterior" not in w["id"]
                and len(w["connected_rooms"]) != 0
            ]
            if not candidate_walls:
                continue

            widest_wall = max(candidate_walls, key=lambda w: w["width"])
            room_to_connect = widest_wall["connected_rooms"][0]["roomId"]

            door_id = self._get_random_door(widest_wall["width"])
            door_dimension = self.door_data[door_id]["boundingBox"]
            door_type = self.door_data[door_id]["type"]

            door_polygon = self._get_door_polygon(
                widest_wall["connected_rooms"][0]["intersection"],
                door_dimension,
                door_type,
            )
            if door_polygon is None:
                continue

            polygon, position, door_boxes, door_segment = door_polygon

            doors.append(DoorEntry(
                asset_id=door_id,
                id=f"door|fallback|{room['roomType']}|{room_to_connect}",
                openable=False,
                openness=0,
                room0=room["roomType"],
                room1=room_to_connect,
                wall0=widest_wall["id"],
                wall1=widest_wall["connected_rooms"][0]["wallId"],
                hole_polygon=polygon,
                asset_position=position,
                door_boxes=door_boxes,
                door_segment=door_segment,
            ))
            connected_rooms.add(room["roomType"])
            connected_rooms.add(room_to_connect)

        return doors


    def _select_door(self, door_type: str, door_size: str, query: str) -> str:
        with torch.no_grad():
            query_feature = self.clip_model.encode_text(self.clip_tokenizer([query]))
            query_feature /= query_feature.norm(dim=-1, keepdim=True)

        similarity = query_feature @ self.door_feature_clip.T
        sorted_indices = torch.argsort(similarity, descending=True)[0]

        valid = [
            self.door_ids[idx]
            for idx in sorted_indices
            if self.door_data[self.door_ids[idx]]["type"] == door_type
            and self.door_data[self.door_ids[idx]]["size"] == door_size
        ]

        top = valid[0]
        valid = [d for d in valid if d not in self.used_assets] or [top]
        return valid[0]

    def _get_random_door(self, wall_width: float) -> str:
        single = [d for d in self.door_ids if self.door_data[d]["size"] == "single"]
        double = [d for d in self.door_ids if self.door_data[d]["size"] == "double"]
        pool = double + single if wall_width >= 2.0 else single
        return random.choice(pool)


    def _get_door_polygon(
        self, segment, door_dimension, connection_type
    ) -> Optional[Tuple]:
        door_width = door_dimension["x"]
        door_height = door_dimension["y"]

        start = np.array([segment[0]["x"], segment[0]["z"]])
        end = np.array([segment[1]["x"], segment[1]["z"]])
        original_vector = end - start
        original_length = np.linalg.norm(original_vector)
        normalized_vector = original_vector / original_length

        if door_width >= original_length:
            logger.warning(f"{Fore.RED}Wall too narrow for door{Fore.RESET}")
            return None

        door_start = random.uniform(0, original_length - door_width)
        door_end = door_start + door_width

        polygon = [
            {"x": door_start, "y": 0, "z": 0},
            {"x": door_end, "y": door_height, "z": 0},
        ]
        position = {
            "x": (polygon[0]["x"] + polygon[1]["x"]) / 2,
            "y": (polygon[0]["y"] + polygon[1]["y"]) / 2,
            "z": (polygon[0]["z"] + polygon[1]["z"]) / 2,
        }
        door_segment = [
            list(start + normalized_vector * door_start),
            list(start + normalized_vector * door_end),
        ]
        door_boxes = self._create_rectangles(door_segment, connection_type)

        return polygon, position, door_boxes, door_segment

    def _get_connection(self, room0_id: str, room1_id: str, walls: list) -> Optional[dict]:
        room0_walls = [w for w in walls if w["roomId"] == room0_id]
        valid_connections = []

        for wall in room0_walls:
            for connection in wall["connected_rooms"]:
                if connection["roomId"] == room1_id:
                    valid_connections.append({
                        "wall0": wall["id"],
                        "wall1": connection["wallId"],
                        "segment": connection["intersection"],
                    })

        if not valid_connections:
            logger.warning(f"{Fore.RED}No wall between {room0_id} and {room1_id}{Fore.RESET}")
            return None

        if len(valid_connections) == 1:
            return valid_connections[0]

        return max(valid_connections, key=lambda c: np.linalg.norm(
            np.array([c["segment"][0]["x"], c["segment"][0]["z"]])
            - np.array([c["segment"][1]["x"], c["segment"][1]["z"]])
        ))

    def _get_connection_exterior(self, room0_id: str, room1_id: str, walls: list) -> Optional[dict]:
        room_id = room0_id if room0_id != "exterior" else room1_id
        interior_wall_ids = [
            w["id"] for w in walls if w["roomId"] == room_id and "exterior" not in w["id"]
        ]
        exterior_wall_ids = [
            w["id"] for w in walls if w["roomId"] == room_id and "exterior" in w["id"]
        ]

        valid_connections = []
        for interior_id in interior_wall_ids:
            for exterior_id in exterior_wall_ids:
                if interior_id in exterior_id:
                    wall = next(w for w in walls if w["id"] == exterior_id)
                    seg = wall["segment"]
                    valid_connections.append({
                        "wall0": exterior_id,
                        "wall1": interior_id,
                        "segment": [
                            {"x": seg[0][0], "y": 0.0, "z": seg[0][1]},
                            {"x": seg[1][0], "y": 0.0, "z": seg[1][1]},
                        ],
                    })

        if not valid_connections:
            return None

        if len(valid_connections) == 1:
            return valid_connections[0]

        return max(valid_connections, key=lambda c: np.linalg.norm(
            np.array([c["segment"][0]["x"], c["segment"][0]["z"]])
            - np.array([c["segment"][1]["x"], c["segment"][1]["z"]])
        ))

    def _create_rectangles(self, segment, connection_type) -> Tuple[list, list]:
        pt1 = np.array(segment[0])
        pt2 = np.array(segment[1])
        vec = pt2 - pt1
        perp_vec = np.array([-vec[1], vec[0]])
        perp_vec /= np.linalg.norm(perp_vec)
        perp_vec *= 1.0

        top_rectangle = [
            list(pt1 + perp_vec),
            list(pt2 + perp_vec),
            list(pt2),
            list(pt1),
        ]
        bottom_rectangle = [
            list(pt1),
            list(pt2),
            list(pt2 - perp_vec),
            list(pt1 - perp_vec),
        ]
        return top_rectangle, bottom_rectangle

    def _get_room_pairs(self, rooms: list, walls: list) -> list:
        room_pairs = [
            (w["roomId"], w["connected_rooms"][0]["roomId"])
            for w in walls
            if len(w["connected_rooms"]) == 1 and w["width"] >= 2.0
        ]
        for wall in walls:
            if "exterior" in wall["id"]:
                room_pairs.append(("exterior", wall["roomId"]))

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

    def _get_room_size_str(self, scene: dict) -> str:
        wall_height = scene["wall_height"]
        result = ""
        for room in scene["rooms"]:
            w, d = self._get_room_size(room)
            result += f"{room['roomType']}: {w} m x {d} m x {wall_height} m\n"
        return result

    def _get_room_size(self, room: dict) -> Tuple[float, float]:
        xs = [p["x"] for p in room["floorPolygon"]]
        zs = [p["z"] for p in room["floorPolygon"]]
        return round(max(xs) - min(xs), 2), round(max(zs) - min(zs), 2)
