import ast
import copy
import json
import random
import re
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import *

import torch
import torch.nn.functional as F
from colorama import Fore
from langchain_core.language_models import BaseChatModel
from shapely import Polygon

import obllomov.agents.prompts as prompts
from obllomov.agents.retrievers import ObjathorRetriever
from obllomov.shared.dfs import DFS_Solver_Floor, DFS_Solver_Wall
from obllomov.shared.utils import get_annotations, get_bbox_dims

from .base import BaseSelector

EXPECTED_OBJECT_ATTRIBUTES = [
    "description",
    "location",
    "size",
    "quantity",
    "variance_type",
    "objects_on_top",
]


class ObjectSelector(BaseSelector):

    def __init__(
        self,
        retriever: ObjathorRetriever,
        llm: BaseChatModel,
        floor_capacity_ratio: float = 0.4,
        wall_capacity_ratio: float = 0.5,
        object_size_tolerance: float = 0.8,
        similarity_threshold_floor: float = 31.0,
        similarity_threshold_wall: float = 31.0,
        thin_threshold: float = 3.0,
        size_buffer: int = 10,
        consider_size: bool = True,
        random_selection: bool = False,
        use_multiprocessing: bool = True,
    ):
        super().__init__()

        self.retriever = retriever
        self.annotations = retriever.annotations
        self.llm = llm

        self.floor_capacity_ratio = floor_capacity_ratio
        self.wall_capacity_ratio = wall_capacity_ratio
        self.object_size_tolerance = object_size_tolerance
        self.similarity_threshold_floor = similarity_threshold_floor
        self.similarity_threshold_wall = similarity_threshold_wall
        self.thin_threshold = thin_threshold
        self.size_buffer = size_buffer
        self.consider_size = consider_size
        self.random_selection = random_selection
        self.use_multiprocessing = use_multiprocessing

        self.object_selection_template_1 = prompts.object_selection_prompt_new_1
        self.object_selection_template_2 = prompts.object_selection_prompt_new_2

    def select(self, scene: dict, additional_requirements: str = "N/A"):
        rooms_types = [room["roomType"] for room in scene["rooms"]]

        room2area       = {room["roomType"]: self._get_room_area(room)     for room in scene["rooms"]}
        room2size       = {room["roomType"]: self._get_room_size(room, scene["wall_height"]) for room in scene["rooms"]}
        room2perimeter  = {room["roomType"]: self._get_room_perimeter(room) for room in scene["rooms"]}
        room2vertices   = {
            room["roomType"]: [(x * 100, y * 100) for (x, y) in room["vertices"]]
            for room in scene["rooms"]
        }

        room2floor_capacity = {
            rt: [room2area[rt] * self.floor_capacity_ratio, 0]
            for rt in rooms_types
        }
        room2floor_capacity = self._update_floor_capacity(room2floor_capacity, scene)

        room2wall_capacity = {
            rt: [room2perimeter[rt] * self.wall_capacity_ratio, 0]
            for rt in rooms_types
        }

        selected_objects = {
            room["roomType"]: {"floor": [], "wall": []}
            for room in scene["rooms"]
        }

        if "object_selection_plan" in scene:
            object_selection_plan = scene["object_selection_plan"]
            for room_type in rooms_types:
                floor_objects, _, wall_objects, _ = self._get_objects_by_room(
                    object_selection_plan[room_type],
                    scene,
                    room2size[room_type],
                    room2floor_capacity[room_type],
                    room2wall_capacity[room_type],
                    room2vertices[room_type],
                )
                selected_objects[room_type]["floor"] = floor_objects
                selected_objects[room_type]["wall"]  = wall_objects
        else:
            object_selection_plan = {room["roomType"]: [] for room in scene["rooms"]}
            packed_args = [
                (
                    room_type, scene, additional_requirements,
                    room2size, room2floor_capacity,
                    room2wall_capacity, room2vertices,
                )
                for room_type in rooms_types
            ]

            if self.use_multiprocessing:
                with ThreadPoolExecutor(max_workers=4) as executor:
                    results = list(executor.map(self._plan_room, packed_args))
            else:
                results = [self._plan_room(args) for args in packed_args]

            for room_type, result in results:
                selected_objects[room_type]["floor"] = result["floor"]
                selected_objects[room_type]["wall"]  = result["wall"]
                object_selection_plan[room_type]     = result["plan"]

        print(
            f"\n{Fore.GREEN}AI: Here is the object selection plan:\n"
            f"{object_selection_plan}{Fore.RESET}"
        )
        return object_selection_plan, selected_objects


    def _plan_room(self, args):
        (
            room_type, scene, additional_requirements,
            room2size, room2floor_capacity,
            room2wall_capacity, room2vertices,
        ) = args

        print(f"\n{Fore.GREEN}AI: Selecting objects for {room_type}...{Fore.RESET}\n")

        room_size_str = (
            f"{int(room2size[room_type][0]) * 100}cm in length, "
            f"{int(room2size[room_type][1]) * 100}cm in width, "
            f"{int(room2size[room_type][2]) * 100}cm in height"
        )

        prompt_1 = (
            self.object_selection_template_1
            .replace("INPUT", scene["query"])
            .replace("ROOM_TYPE", room_type)
            .replace("ROOM_SIZE", room_size_str)
            .replace("REQUIREMENTS", additional_requirements)
        )

        output_1 = self.llm.invoke(prompt_1).content.lower()
        plan_1   = self._extract_json(output_1)

        if plan_1 is None:
            print(f"Error while extracting the JSON for {room_type}.")
            return room_type, {"floor": [], "wall": [], "plan": {}}

        floor_objects, floor_capacity, wall_objects, _ = self._get_objects_by_room(
            plan_1,
            scene,
            room2size[room_type],
            room2floor_capacity[room_type],
            room2wall_capacity[room_type],
            room2vertices[room_type],
        )

        result = {
            "floor": floor_objects,
            "wall":  wall_objects,
            "plan":  plan_1,
        }
        return room_type, result


    def _get_objects_by_room(
        self, parsed_plan, scene, room_size,
        floor_capacity, wall_capacity, vertices,
    ):
        floor_object_list, wall_object_list = [], []
        for object_name, object_info in parsed_plan.items():
            object_info["object_name"] = object_name
            if object_info["location"] == "floor":
                floor_object_list.append(object_info)
            else:
                wall_object_list.append(object_info)

        floor_objects, floor_capacity = self._get_floor_objects(
            floor_object_list, floor_capacity, room_size, vertices, scene
        )
        wall_objects, wall_capacity = self._get_wall_objects(
            wall_object_list, wall_capacity, room_size, vertices, scene
        )
        return floor_objects, floor_capacity, wall_objects, wall_capacity

    def _get_floor_objects(
        self, floor_object_list, floor_capacity, room_size, room_vertices, scene
    ):
        selected_all = []

        for obj in floor_object_list:
            object_type        = obj["object_name"]
            object_description = obj["description"]
            object_size        = obj["size"]
            quantity           = min(obj["quantity"], 10)
            variance_type      = obj.get("variance_type", "same")

            candidates = self.retriever.retrieve_single(
                f"a 3D model of {object_type}, {object_description}",
                threshold=self.similarity_threshold_floor,
            )

            candidates = self._filter_floor_annotations(candidates)
            candidates = self._check_object_size(candidates, room_size)
            candidates = self._check_floor_placement(candidates[:20], room_vertices, scene)

            if not candidates:
                print(f"No candidates found for {object_type} {object_description}")
                continue

            candidates = self._filter_used_assets(candidates)

            if self.consider_size and object_size is not None:
                candidates = self._apply_size_difference(object_size, candidates)

            candidates = candidates[:10]
            selected_ids = self._select_by_variance(candidates, quantity, variance_type)

            for i, asset_id in enumerate(selected_ids):
                selected_all.append((f"{object_type}-{i}", asset_id))

        return self._apply_floor_capacity(selected_all, floor_capacity)

    def _get_wall_objects(
        self, wall_object_list, wall_capacity, room_size, room_vertices, scene
    ):
        selected_all = []

        for obj in wall_object_list:
            object_type        = obj["object_name"]
            object_description = obj["description"]
            object_size        = obj["size"]
            quantity           = min(obj["quantity"], 10)
            variance_type      = obj["variance_type"]

            candidates = self.retriever.retrieve_single(
                f"a 3D model of {object_type}, {object_description}",
                threshold=self.similarity_threshold_wall,
            )

            candidates = self._filter_wall_annotations(candidates)
            candidates = self._check_object_size(candidates, room_size)
            candidates = self._check_thin_object(candidates)
            candidates = self._check_wall_placement(candidates[:20], room_vertices, scene)

            if not candidates:
                print(f"No candidates found for {object_type} {object_description}")
                continue

            candidates = self._filter_used_assets(candidates)

            if self.consider_size and object_size is not None:
                candidates = self._apply_size_difference(object_size, candidates)

            candidates = candidates[:10]
            selected_ids = self._select_by_variance(candidates, quantity, variance_type)

            for i, asset_id in enumerate(selected_ids):
                selected_all.append((f"{object_type}-{i}", asset_id))

        return self._apply_wall_capacity(selected_all, wall_capacity)

    def _filter_floor_annotations(
        self, candidates: list[tuple[str, float]]
    ) -> list[tuple[str, float]]:
        return [
            c for c in candidates
            if (
                get_annotations(self.annotations[c[0]])["onFloor"]
                and not get_annotations(self.annotations[c[0]])["onCeiling"]
                and all(
                    k not in get_annotations(self.annotations[c[0]])["category"].lower()
                    for k in ["door", "window", "frame"]
                )
            )
        ]

    def _filter_wall_annotations(
        self, candidates: list[tuple[str, float]]
    ) -> list[tuple[str, float]]:
        return [
            c for c in candidates
            if (
                get_annotations(self.annotations[c[0]])["onWall"]
                and "door"   not in get_annotations(self.annotations[c[0]])["category"].lower()
                and "window" not in get_annotations(self.annotations[c[0]])["category"].lower()
            )
        ]

    def _filter_used_assets(
        self, candidates: list[tuple[str, float]]
    ) -> list[tuple[str, float]]:
        top = candidates[0]
        filtered = [c for c in candidates if c[0] not in self.used_assets]
        return filtered if filtered else [top]

    def _check_object_size(
        self,
        candidates: list[tuple[str, float]],
        room_size: tuple,
    ) -> list[tuple[str, float]]:
        valid = []
        for c in candidates:
            dim  = get_bbox_dims(self.annotations[c[0]])
            size = sorted([dim["x"], dim["y"], dim["z"]])
            if (
                size[2] <= room_size[0] * self.object_size_tolerance
                and size[1] <= room_size[1] * self.object_size_tolerance
                and size[0] <= room_size[2] * self.object_size_tolerance
                and size[2] * size[0] <= room_size[0] * room_size[2] * 0.5
            ):
                valid.append(c)
        return valid

    def _check_thin_object(
        self, candidates: list[tuple[str, float]]
    ) -> list[tuple[str, float]]:
        valid = []
        for c in candidates:
            dim  = get_bbox_dims(self.annotations[c[0]])
            size = [dim["x"], dim["y"], dim["z"]]
            if size[2] <= min(size[0], size[1]) * self.thin_threshold:
                valid.append(c)
        return valid

    def _check_floor_placement(
        self,
        candidates: list[tuple[str, float]],
        room_vertices: list,
        scene: dict,
    ) -> list[tuple[str, float]]:
        room_x   = max(v[0] for v in room_vertices) - min(v[0] for v in room_vertices)
        room_z   = max(v[1] for v in room_vertices) - min(v[1] for v in room_vertices)
        grid_size = int(max(room_x // 20, room_z // 20))

        solver       = DFS_Solver_Floor(grid_size=grid_size)
        room_poly    = Polygon(room_vertices)
        initial_state = self._get_initial_state_floor(room_vertices, scene)
        grid_points  = solver.create_grids(room_poly)
        grid_points  = solver.remove_points(grid_points, initial_state)

        valid = []
        for c in candidates:
            dim = get_bbox_dims(self.annotations[c[0]])
            object_dim = (
                dim["x"] * 100 + self.size_buffer,
                dim["z"] * 100 + self.size_buffer,
            )
            solutions = solver.get_all_solutions(room_poly, grid_points, object_dim)
            solutions = solver.filter_collision(initial_state, solutions)
            solutions = solver.place_edge(room_poly, solutions, object_dim)
            if solutions:
                valid.append(c)
            else:
                print(f"Floor Object {c[0]} (size: {object_dim}) cannot be placed in room")
        return valid

    def _check_wall_placement(
        self,
        candidates: list[tuple[str, float]],
        room_vertices: list,
        scene: dict,
    ) -> list[tuple[str, float]]:
        room_x    = max(v[0] for v in room_vertices) - min(v[0] for v in room_vertices)
        room_z    = max(v[1] for v in room_vertices) - min(v[1] for v in room_vertices)
        grid_size = int(max(room_x // 20, room_z // 20))

        solver        = DFS_Solver_Wall(grid_size=grid_size)
        room_poly     = Polygon(room_vertices)
        initial_state = self._get_initial_state_wall(room_vertices, scene)
        grid_points   = solver.create_grids(room_poly)

        valid = []
        for c in candidates:
            dim = get_bbox_dims(self.annotations[c[0]])
            object_dim = (dim["x"] * 100, dim["y"] * 100, dim["z"] * 100)
            solutions  = solver.get_all_solutions(room_poly, grid_points, object_dim, height=0)
            solutions  = solver.filter_collision(initial_state, solutions)
            if solutions:
                valid.append(c)
            else:
                print(f"Wall Object {c[0]} (size: {object_dim}) cannot be placed in room")
        return valid


    def _apply_size_difference(
        self,
        target_size: list,
        candidates: list[tuple[str, float]],
    ) -> list[tuple[str, float]]:
        candidate_sizes = []
        for uid, _ in candidates:
            dim  = get_bbox_dims(self.annotations[uid])
            s    = sorted([dim["x"] * 100, dim["y"] * 100, dim["z"] * 100])
            candidate_sizes.append(s)

        candidate_sizes_t = torch.tensor(candidate_sizes)
        target_sorted     = torch.tensor(sorted(target_size), dtype=torch.float32)
        size_diff         = (candidate_sizes_t - target_sorted).abs().mean(dim=1) / 100

        result = [
            (uid, score - size_diff[i].item() * 10)
            for i, (uid, score) in enumerate(candidates)
        ]
        result.sort(key=lambda x: x[1], reverse=True)
        return result

    def _select_by_variance(
        self,
        candidates: list[tuple[str, float]],
        quantity: int,
        variance_type: str,
    ) -> list[str]:
        selected = []
        if variance_type == "same":
            chosen = self._pick_candidate(candidates)
            selected = [chosen] * quantity
        else:  # varied
            pool = list(candidates)
            for _ in range(quantity):
                chosen = self._pick_candidate(pool)
                selected.append(chosen)
                if len(pool) > 1:
                    pool = [c for c in pool if c[0] != chosen]
        return selected

    def _pick_candidate(self, candidates: list[tuple[str, float]]) -> str:
        if self.random_selection:
            return random.choice(candidates)[0]
        scores  = torch.tensor([c[1] for c in candidates])
        probas  = F.softmax(scores, dim=0)
        idx     = torch.multinomial(probas, 1).item()
        return candidates[idx][0]

    def _apply_floor_capacity(
        self,
        selected_all: list[tuple[str, str]],
        floor_capacity: list,
    ) -> tuple[list, list]:
        selected = []
        while selected_all:
            current_ids   = []
            count_before  = len(selected)

            for object_name, asset_id in list(selected_all):
                if asset_id in current_ids:
                    continue
                dim      = get_bbox_dims(self.annotations[asset_id])
                capacity = dim["x"] * dim["z"]
                if floor_capacity[1] + capacity > floor_capacity[0] and selected:
                    continue
                current_ids.append(asset_id)
                selected.append((object_name, asset_id))
                selected_all.remove((object_name, asset_id))
                floor_capacity[1] += capacity

            if len(selected) == count_before:
                break

        return self._sort_by_type(selected), floor_capacity

    def _apply_wall_capacity(
        self,
        selected_all: list[tuple[str, str]],
        wall_capacity: list,
    ) -> tuple[list, list]:
        selected = []
        while selected_all:
            current_ids  = []
            count_before = len(selected)

            for object_name, asset_id in list(selected_all):
                if asset_id in current_ids:
                    continue
                dim      = get_bbox_dims(self.annotations[asset_id])
                capacity = dim["x"]
                if wall_capacity[1] + capacity > wall_capacity[0] and selected:
                    continue
                current_ids.append(asset_id)
                selected.append((object_name, asset_id))
                selected_all.remove((object_name, asset_id))
                wall_capacity[1] += capacity

            if len(selected) == count_before:
                break

        return self._sort_by_type(selected), wall_capacity

    @staticmethod
    def _sort_by_type(
        objects: list[tuple[str, str]]
    ) -> list[tuple[str, str]]:
        type2objects: dict[str, list] = {}
        for name, asset_id in objects:
            obj_type = name.split("-")[0]
            type2objects.setdefault(obj_type, []).append((name, asset_id))
        result = []
        for obj_type in type2objects:
            result += sorted(type2objects[obj_type])
        return result

    def _get_initial_state_floor(
        self, room_vertices: list, scene: dict, add_window: bool = False
    ) -> dict:
        doors, windows, open_walls = (
            scene["doors"], scene["windows"], scene["open_walls"]
        )
        room_poly     = Polygon(room_vertices)
        initial_state = {}
        i = 0

        for door in doors:
            for door_box in door["doorBoxes"]:
                verts    = [(x * 100, z * 100) for x, z in door_box]
                poly     = Polygon(verts)
                centroid = poly.centroid
                if room_poly.contains(centroid):
                    initial_state[f"door-{i}"] = (
                        (centroid.x, centroid.y), 0, verts, 1
                    )
                    i += 1

        if add_window:
            for window in windows:
                for window_box in window["windowBoxes"]:
                    verts    = [(x * 100, z * 100) for x, z in window_box]
                    poly     = Polygon(verts)
                    centroid = poly.centroid
                    if room_poly.contains(centroid):
                        initial_state[f"window-{i}"] = (
                            (centroid.x, centroid.y), 0, verts, 1
                        )
                        i += 1

        if open_walls:
            for box in open_walls["openWallBoxes"]:
                verts    = [(x * 100, z * 100) for x, z in box]
                poly     = Polygon(verts)
                centroid = poly.centroid
                if room_poly.contains(centroid):
                    initial_state[f"open-{i}"] = (
                        (centroid.x, centroid.y), 0, verts, 1
                    )
                    i += 1

        return initial_state

    def _get_initial_state_wall(self, room_vertices: list, scene: dict) -> dict:
        doors, windows, open_walls = (
            scene["doors"], scene["windows"], scene["open_walls"]
        )
        room_poly     = Polygon(room_vertices)
        initial_state = {}
        i = 0

        for door in doors:
            for door_box in door["doorBoxes"]:
                verts    = [(x * 100, z * 100) for x, z in door_box]
                poly     = Polygon(verts)
                centroid = poly.centroid
                if room_poly.contains(centroid):
                    door_height      = door["assetPosition"]["y"] * 100 * 2
                    x_min, z_min, x_max, z_max = poly.bounds
                    initial_state[f"door-{i}"] = (
                        (x_min, 0, z_min), (x_max, door_height, z_max),
                        0, verts, 1,
                    )
                    i += 1

        for window in windows:
            for window_box in window["windowBoxes"]:
                verts    = [(x * 100, z * 100) for x, z in window_box]
                poly     = Polygon(verts)
                centroid = poly.centroid
                if room_poly.contains(centroid):
                    y_min = window["holePolygon"][0]["y"] * 100
                    y_max = window["holePolygon"][1]["y"] * 100
                    x_min, z_min, x_max, z_max = poly.bounds
                    initial_state[f"window-{i}"] = (
                        (x_min, y_min, z_min), (x_max, y_max, z_max),
                        0, verts, 1,
                    )
                    i += 1

        if open_walls:
            for box in open_walls["openWallBoxes"]:
                verts    = [(x * 100, z * 100) for x, z in box]
                poly     = Polygon(verts)
                centroid = poly.centroid
                if room_poly.contains(centroid):
                    x_min, z_min, x_max, z_max = poly.bounds
                    initial_state[f"open-{i}"] = (
                        (x_min, 0, z_min),
                        (x_max, scene["wall_height"] * 100, z_max),
                        0, verts, 1,
                    )
                    i += 1

        return initial_state


    @staticmethod
    def _get_room_size(room: dict, wall_height: float) -> tuple:
        xs = [p["x"] for p in room["floorPolygon"]]
        zs = [p["z"] for p in room["floorPolygon"]]
        x_dim = max(xs) - min(xs)
        z_dim = max(zs) - min(zs)
        return (max(x_dim, z_dim), wall_height, min(x_dim, z_dim))

    @staticmethod
    def _get_room_area(room: dict) -> float:
        return Polygon(room["vertices"]).area

    @staticmethod
    def _get_room_perimeter(room: dict) -> float:
        return Polygon(room["vertices"]).length


    def _update_floor_capacity(
        self, room2floor_capacity: dict, scene: dict
    ) -> dict:
        for room in scene["rooms"]:
            room_poly = Polygon(room["vertices"])
            for door in scene["doors"]:
                for door_vertices in door["doorBoxes"]:
                    door_poly = Polygon(door_vertices)
                    if room_poly.contains(door_poly.centroid):
                        room2floor_capacity[room["id"]][1] += door_poly.area * 0.6
            if scene["open_walls"]:
                for box in scene["open_walls"]["openWallBoxes"]:
                    poly = Polygon(box)
                    if room_poly.contains(poly.centroid):
                        room2floor_capacity[room["id"]][1] += poly.area * 0.6
        return room2floor_capacity
    
    def _extract_json(self, input_string: str) -> dict | None:
        match = re.search(r"{.*}", input_string, re.DOTALL)
        if not match:
            print(f"No valid JSON found in:\n{input_string}", flush=True)
            return None

        json_dict = None
        try:
            json_dict = json.loads(match.group(0))
        except Exception:
            try:
                json_dict = ast.literal_eval(match.group(0))
            except Exception:
                pass

        if json_dict is None:
            print(
                f"{Fore.RED}[ERROR] while parsing the JSON for:\n{input_string}{Fore.RESET}",
                flush=True,
            )
            return None

        json_dict = self._normalize_keys(json_dict)
        try:
            json_dict = self._validate_dict(json_dict)
        except Exception as e:
            print(
                f"{Fore.RED}[ERROR] Dictionary check failed:\n"
                f"{traceback.format_exception_only(type(e), e)}{Fore.RESET}",
                flush=True,
            )
        return json_dict

    def _normalize_keys(self, obj):
        if isinstance(obj, dict):
            return {
                k.strip().lower().replace(" ", "_"): self._normalize_keys(v)
                for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [self._normalize_keys(v) for v in obj]
        return obj

    def _validate_dict(self, d: dict) -> dict | None:
        for key, value in d.items():
            if not isinstance(value, dict):
                return None
            for attr in EXPECTED_OBJECT_ATTRIBUTES:
                if attr not in value:
                    return None
            if value.get("location") not in ["floor", "wall"]:
                d[key]["location"] = "floor"
            if (
                not isinstance(value.get("size"), list)
                or len(value["size"]) != 3
                or not all(isinstance(i, int) for i in value["size"])
            ):
                d[key]["size"] = None
            if not isinstance(value.get("quantity"), int):
                d[key]["quantity"] = 1
            if value.get("variance_type") not in ["same", "varied"]:
                d[key]["variance_type"] = "same"
            if not isinstance(value.get("objects_on_top"), list):
                d[key]["objects_on_top"] = []
            for i, child in enumerate(value["objects_on_top"]):
                if not isinstance(child, dict):
                    return None
                if not isinstance(child.get("object_name"), str):
                    return None
                if not isinstance(child.get("quantity"), int):
                    d[key]["objects_on_top"][i]["quantity"] = 1
                if child.get("variance_type") not in ["same", "varied"]:
                    d[key]["objects_on_top"][i]["variance_type"] = "same"
        return d
