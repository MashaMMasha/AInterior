import random
from concurrent.futures import ThreadPoolExecutor
from typing import *

import torch
import torch.nn.functional as F
from colorama import Fore
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

import obllomov.agents.prompts as prompts
from obllomov.agents.base import BaseAgent
from obllomov.agents.retrievers import ObjathorRetriever
from obllomov.schemas.domain.entries import ScenePlan
from obllomov.schemas.domain.raw import RawRoomObjects, RawTopObjectEntry
from obllomov.agents.selectors.placement import DFS_Solver_Floor, DFS_Solver_Wall
from obllomov.shared.geometry import Polygon2D, Vertex2D
from obllomov.shared.log import logger
from obllomov.schemas.domain.annotations import Annotation, AnnotationDict

from .base import BaseSelector
from .constraints import (
    Constraint,
    FloorAnnotationConstraint,
    FloorPlacementConstraint,
    ObjectSizeConstraint,
    ThinConstraint,
    UsedAssetsConstraint,
    WallAnnotationConstraint,
    WallPlacementConstraint,
)


class ObjectSelector(BaseAgent, BaseSelector):

    def __init__(
        self,
        retriever: ObjathorRetriever,
        llm: BaseChatModel,
        annotations: AnnotationDict,
        floor_capacity_ratio: float = 0.4,
        wall_capacity_ratio: float = 0.5,
        object_size_tolerance: float = 0.8,
        similarity_threshold_floor: float = 31.0,
        similarity_threshold_wall: float = 31.0,
        thin_threshold: float = 10.0,
        size_buffer: int = 10,
        consider_size: bool = True,
        random_selection: bool = False,
        use_multiprocessing: bool = True,
    ):
        BaseAgent.__init__(self, llm)
        BaseSelector.__init__(self)

        self.retriever = retriever
        # self.annotations = retriever.items
        self.annotations = annotations
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

    def select(
        self,
        scene_plan: ScenePlan,
        raw: Optional[Dict[str, RawRoomObjects]] = None,
        additional_requirements: str = "N/A",
    ):
        rooms_types = [room.room_type for room in scene_plan.rooms]

        room2polygon = {
            room.room_type: Polygon2D(vertices=room.vertices)
            for room in scene_plan.rooms
        }
        room2area       = {rt: room2polygon[rt].area for rt in rooms_types}
        room2size       = {rt: self._get_room_size(room2polygon[rt], scene_plan.wall_height) for rt in rooms_types}
        room2perimeter  = {rt: room2polygon[rt].perimeter for rt in rooms_types}
        room2vertices   = {
            rt: [v.scaled(100).to_tuple() for v in room2polygon[rt].vertices]
            for rt in rooms_types
        }

        room2floor_capacity = {
            rt: [room2area[rt] * self.floor_capacity_ratio, 0]
            for rt in rooms_types
        }
        room2floor_capacity = self._update_floor_capacity(room2floor_capacity, scene_plan)

        room2wall_capacity = {
            rt: [room2perimeter[rt] * self.wall_capacity_ratio, 0]
            for rt in rooms_types
        }

        selected_objects = {
            room.room_type: {"floor": [], "wall": []}
            for room in scene_plan.rooms
        }

        if raw is not None:
            object_selection_plan = raw
            for room_type in rooms_types:
                floor_objects, _, wall_objects, _ = self._get_objects_by_room(
                    object_selection_plan[room_type],
                    scene_plan,
                    room2size[room_type],
                    room2floor_capacity[room_type],
                    room2wall_capacity[room_type],
                    room2vertices[room_type],
                )
                selected_objects[room_type]["floor"] = floor_objects
                selected_objects[room_type]["wall"]  = wall_objects
        else:
            object_selection_plan = {room.room_type: [] for room in scene_plan.rooms}
            packed_args = [
                (
                    room_type, scene_plan, additional_requirements,
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

        # print(
        #     f"\n{Fore.GREEN}AI: Here is the object selection plan:\n"
        #     f"{object_selection_plan}{Fore.RESET}"
        # )
        return object_selection_plan, selected_objects


    def _plan_room(self, args):
        (
            room_type, scene_plan, additional_requirements,
            room2size, room2floor_capacity,
            room2wall_capacity, room2vertices,
        ) = args

        logger.info(f"\n{Fore.GREEN}AI: Selecting objects for {room_type}...{Fore.RESET}\n")

        room_size_str = (
            f"{int(room2size[room_type][0]) * 100}cm in length, "
            f"{int(room2size[room_type][1]) * 100}cm in width, "
            f"{int(room2size[room_type][2]) * 100}cm in height"
        )

        plan_1 = self._structured_plan(
            schema=RawRoomObjects,
            prompt_template=self.object_selection_template_1,
            input_variables={
                "input": scene_plan.query,
                "room_type": room_type,
                "room_size": room_size_str,
                "additional_requirements": additional_requirements,
            },
        )

        floor_objects, floor_capacity, wall_objects, _ = self._get_objects_by_room(
            plan_1,
            scene_plan,
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
        self, plan: RawRoomObjects, scene_plan: ScenePlan, room_size,
        floor_capacity, wall_capacity, vertices,
    ):
        floor_object_list, wall_object_list = [], []

        for object_info in plan.objects:
            entry = object_info.model_dump()

            if object_info.location == "floor":
                floor_object_list.append(entry)
            else:
                wall_object_list.append(entry)

        floor_objects, floor_capacity = self._get_floor_objects(
            floor_object_list, floor_capacity, room_size, vertices, scene_plan
        )
        wall_objects, wall_capacity = self._get_wall_objects(
            wall_object_list, wall_capacity, room_size, vertices, scene_plan
        )
        return floor_objects, floor_capacity, wall_objects, wall_capacity

    def _select_candidates_for_object(
        self,
        *,
        object_type: str,
        object_description: str,
        object_size: Any,
        quantity: int,
        variance_type: str,
        similarity_threshold: float,
        constraints: list[Constraint],
    ) -> list[str] | None:
        uids, scores = self.retriever.retrieve_single(
            f"a 3D model of {object_type}, {object_description}",
            threshold=similarity_threshold,
            topk=200
        )

        candidates = list(zip(uids, scores))

        # logger.debug(f"candidates: {candidates}")

        for constraint in constraints:
            
            candidates = constraint.apply(candidates)
            logger.debug(f"After {constraint.__class__.__name__} canditates for {object_type}: {candidates}")
            if not candidates:
                return None

        if self.consider_size and object_size is not None:
            candidates = self._apply_size_difference(object_size, candidates)

        candidates = candidates[:10]
        return self._select_by_variance(candidates, quantity, variance_type)

    def _get_floor_objects(
        self, floor_object_list, floor_capacity, room_size, room_vertices, scene_plan: ScenePlan,
    ):
        selected_all = []
        initial_state = self._get_initial_state(room_vertices, scene_plan, mode="floor")

        for obj in floor_object_list:
            object_type        = obj["object_name"]
            object_description = obj["description"]
            object_size        = obj["size"]
            quantity           = min(obj["quantity"], 10)
            variance_type      = obj.get("variance_type", "same")

            constraints = [
                FloorAnnotationConstraint(self.annotations),
                ObjectSizeConstraint(self.annotations, room_size, self.object_size_tolerance),
                FloorPlacementConstraint(
                    self.annotations, room_vertices, initial_state,
                    self.size_buffer, max_candidates=20,
                ),
                UsedAssetsConstraint(self.used_assets),
            ]

            selected_ids = self._select_candidates_for_object(
                object_type=object_type,
                object_description=object_description,
                object_size=object_size,
                quantity=quantity,
                variance_type=variance_type,
                similarity_threshold=self.similarity_threshold_floor,
                constraints=constraints,
            )

            if not selected_ids:
                logger.error(
                    f"No candidates found for {object_type} {object_description}"
                )
                continue

            for i, asset_id in enumerate(selected_ids):
                selected_all.append((f"{object_type}-{i}", asset_id))

        return self._apply_floor_capacity(selected_all, floor_capacity)

    def _get_wall_objects(
        self, wall_object_list, wall_capacity, room_size, room_vertices, scene_plan: ScenePlan,
    ):
        selected_all = []
        initial_state = self._get_initial_state(room_vertices, scene_plan, mode="wall")

        for obj in wall_object_list:
            object_type        = obj["object_name"]
            object_description = obj["description"]
            object_size        = obj["size"]
            quantity           = min(obj["quantity"], 10)
            variance_type      = obj.get("variance_type", "same")

            constraints = [
                WallAnnotationConstraint(self.annotations),
                ObjectSizeConstraint(self.annotations, room_size, self.object_size_tolerance),
                ThinConstraint(self.annotations, self.thin_threshold),
                WallPlacementConstraint(
                    self.annotations, room_vertices, initial_state,
                    max_candidates=20,
                ),
                UsedAssetsConstraint(self.used_assets),
            ]

            selected_ids = self._select_candidates_for_object(
                object_type=object_type,
                object_description=object_description,
                object_size=object_size,
                quantity=quantity,
                variance_type=variance_type,
                similarity_threshold=self.similarity_threshold_wall,
                constraints=constraints,
            )

            if not selected_ids:
                logger.error(
                    f"No candidates found for {object_type} {object_description}"
                )
                continue

            for i, asset_id in enumerate(selected_ids):
                selected_all.append((f"{object_type}-{i}", asset_id))

        return self._apply_wall_capacity(selected_all, wall_capacity)
    
    def _apply_size_difference(
        self,
        target_size: list,
        candidates: list[tuple[str, float]],
    ) -> list[tuple[str, float]]:
        candidate_sizes = []
        for uid, _ in candidates:
            dim  = self.annotations[uid].bbox
            s    = sorted(dim.convert_m_to_cm().size())
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
                dim      = self.annotations[asset_id].bbox
                capacity = dim.x * dim.z
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
                dim      = self.annotations[asset_id].bbox
                capacity = dim.x
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

    def _iter_room_openings(
        self, room_poly: Polygon2D, scene_plan: ScenePlan, include_windows: bool,
    ) -> Iterable[tuple[str, list[tuple[float, float]], Polygon2D, Any]]:
        for door in scene_plan.doors:
            for box in door.door_boxes:
                verts = [(x * 100, z * 100) for x, z in box]
                poly = Polygon2D(vertices=[Vertex2D(x=v[0], z=v[1]) for v in verts])
                if room_poly.contains(poly.centroid):
                    yield "door", verts, poly, door

        if include_windows:
            for window in scene_plan.windows:
                for box in window.window_boxes:
                    verts = [(x * 100, z * 100) for x, z in box]
                    poly = Polygon2D(vertices=[Vertex2D(x=v[0], z=v[1]) for v in verts])
                    if room_poly.contains(poly.centroid):
                        yield "window", verts, poly, window

        open_walls = scene_plan.open_walls
        if open_walls:
            for box in open_walls.get("openWallBoxes", []):
                verts = [(x * 100, z * 100) for x, z in box]
                poly = Polygon2D(vertices=[Vertex2D(x=v[0], z=v[1]) for v in verts])
                if room_poly.contains(poly.centroid):
                    yield "open", verts, poly, None

    def _get_initial_state(
        self,
        room_vertices: list,
        scene_plan: ScenePlan,
        *,
        mode: Literal["floor", "wall"],
        add_window: bool = False,
    ) -> dict:
        room_poly = Polygon2D(vertices=[Vertex2D(x=v[0], z=v[1]) for v in room_vertices])
        include_windows = mode == "wall" or add_window
        initial_state = {}

        for i, (prefix, verts, poly, source) in enumerate(
            self._iter_room_openings(room_poly, scene_plan, include_windows=include_windows)
        ):
            if mode == "floor":
                centroid = poly.centroid
                initial_state[f"{prefix}-{i}"] = ((centroid.x, centroid.z), 0, verts, 1)
                continue

            x_min, z_min, x_max, z_max = poly.bounds
            if prefix == "door":
                y_min, y_max = 0, source.asset_position.y * 100 * 2
            elif prefix == "window":
                y_min = source.hole_polygon[0].y * 100
                y_max = source.hole_polygon[1].y * 100
            else:
                y_min, y_max = 0, scene_plan.wall_height * 100

            initial_state[f"{prefix}-{i}"] = (
                (x_min, y_min, z_min),
                (x_max, y_max, z_max),
                0,
                verts,
                1,
            )

        return initial_state

    def _get_initial_state_floor(
        self, room_vertices: list, scene_plan: ScenePlan, add_window: bool = False,
    ) -> dict:
        return self._get_initial_state(
            room_vertices, scene_plan, mode="floor", add_window=add_window
        )

    def _get_initial_state_wall(self, room_vertices: list, scene_plan: ScenePlan) -> dict:
        return self._get_initial_state(room_vertices, scene_plan, mode="wall")

    def _get_initial_state_walls(self, room_vertices: list, scene_plan: ScenePlan) -> dict:
        return self._get_initial_state_wall(room_vertices, scene_plan)


    @staticmethod
    def _get_room_size(polygon: Polygon2D, wall_height: float) -> tuple:
        w, d = polygon.bbox_size()
        return (max(w, d), wall_height, min(w, d))

    def _update_floor_capacity(
        self, room2floor_capacity: dict, scene_plan: ScenePlan,
    ) -> dict:
        for room in scene_plan.rooms:
            room_poly = Polygon2D(vertices=room.vertices)
            for door in scene_plan.doors:
                for door_vertices in door.door_boxes:
                    door_poly = Polygon2D(vertices=[Vertex2D(x=v[0], z=v[1]) for v in door_vertices])
                    if room_poly.contains(door_poly.centroid):
                        room2floor_capacity[room.id][1] += door_poly.area * 0.6
            if scene_plan.open_walls:
                for box in scene_plan.open_walls.get("openWallBoxes", []):
                    poly = Polygon2D(vertices=[Vertex2D(x=v[0], z=v[1]) for v in box])
                    if room_poly.contains(poly.centroid):
                        room2floor_capacity[room.id][1] += poly.area * 0.6
        return room2floor_capacity
