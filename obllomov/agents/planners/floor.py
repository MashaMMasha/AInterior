import io
import math
import os
from difflib import SequenceMatcher
from typing import List

import matplotlib.colors as mcolors
import matplotlib.patches as patches
import matplotlib.pyplot as plt
import torch
from PIL import Image
from colorama import Fore
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from shapely.geometry import LineString, Point, Polygon
from tqdm import tqdm

import obllomov.agents.prompts as prompts
from obllomov.shared.path import HOLODECK_MATERIALS_DIR
from obllomov.storage.assets import BaseAssets
from obllomov.shared.log import logger

from .base import BasePlanner


class RawRoomPlan(BaseModel):
    room_type: str = Field(
        description="Type of the room, e.g. 'living room', 'bedroom'"
    )
    floor_design: str = Field(
        description="Floor material/design description, e.g. 'oak wood'"
    )
    wall_design: str = Field(
        description="Wall material/design description, e.g. 'white paint'"
    )
    vertices: List[List[float]] = Field(
        description=(
            "List of 2D [x, z] vertices in meters defining the room polygon. "
            "Must be in clockwise order and form a rectilinear (all angles >= 90°) shape."
        )
    )


class RawFloorPlan(BaseModel):
    rooms: List[RawRoomPlan] = Field(description="List of rooms in the floor plan")


class RoomPlan(BaseModel):
    room_type: str
    floor_design: str
    wall_design: str
    vertices: List[List[float]]

    id: str
    floor_polygon: List[dict]
    full_vertices: List[List[float]]
    floor_material: dict
    wall_material: dict

    model_config = {"arbitrary_types_allowed": True}


class FloorPlan(BaseModel):
    rooms: List[RoomPlan]



class FloorPlanner(BasePlanner):
    def __init__(self, clip_model, clip_process, clip_tokenizer, llm: BaseChatModel, assets: BaseAssets):
        super().__init__(llm, assets)

        self.material_selector = MaterialSelector(clip_model, clip_process, clip_tokenizer, assets)


    def plan(self, scene, additional_requirements="N/A", visualize=False) -> FloorPlan:
        raw_floor_plan = self._structured_plan(
            scene=scene,
            schema=RawFloorPlan,
            prompt_template=prompts.floor_plan_prompt,
            cache_key="raw_floor_plan",
            input_variables={
                "input": scene["query"],
                "additional_requirements": additional_requirements,
            },
        )

        floor_plan = self._parse_raw(raw_floor_plan)
        self._validate(floor_plan)

        if visualize:
            self.visualize_floor_plan(scene["query"], floor_plan)

        return floor_plan

    def _parse_raw(self, raw: RawFloorPlan) -> FloorPlan:
        raw_rooms_with_ids = []
        seen: list[str] = []
        for i, raw_room in enumerate(raw.rooms):
            room_id = raw_room.room_type.lower().replace("'", "").strip()
            if room_id in seen:
                room_id = f"{room_id}-{i}"
            seen.append(room_id)

            sorted_verts = self._sort_vertices([(v[0], v[1]) for v in raw_room.vertices])
            raw_room.vertices = [list(v) for v in sorted_verts]

            raw_rooms_with_ids.append((raw_room, room_id))

        # Pass 2: compute full_vertices across all rooms
        all_vertices: list[tuple] = []
        for raw_room, _ in raw_rooms_with_ids:
            all_vertices += [tuple(v) for v in raw_room.vertices]
        all_vertices = list(set(all_vertices))

        # Pass 3: select materials
        all_designs = []
        for raw_room, _ in raw_rooms_with_ids:
            all_designs.append(raw_room.floor_design.strip().lower())
            all_designs.append(raw_room.wall_design.strip().lower())
        design2material = self._select_materials(all_designs, topk=5)

        rooms = []
        for raw_room, room_id in raw_rooms_with_ids:
            full_verts = self._get_full_vertices(
                [tuple(v) for v in raw_room.vertices], all_vertices
            )
            full_verts_sorted = self._sort_vertices(list(set(full_verts)))

            rooms.append(RoomPlan(
                room_type=raw_room.room_type,
                floor_design=raw_room.floor_design,
                wall_design=raw_room.wall_design,
                vertices=raw_room.vertices,
                id=room_id,
                floor_polygon=[
                    {"x": v[0], "y": 0.0, "z": v[1]} for v in full_verts_sorted
                ],
                full_vertices=[list(v) for v in full_verts_sorted],
                floor_material=design2material[raw_room.floor_design.strip().lower()],
                wall_material=design2material[raw_room.wall_design.strip().lower()],
            ))

        return FloorPlan(rooms=rooms)

    def _validate(self, floor_plan: FloorPlan) -> None:
        valid, msg = self._check_validity(floor_plan)
        if not valid:
            logger.error(f"{Fore.RED}Floor plan validation failed: {msg}{Fore.RESET}")

            import numpy as np
            colors = plt.cm.rainbow(np.linspace(0, 1, len(floor_plan.rooms)+1))
            for room in floor_plan.rooms:
                verts = [tuple(v) for v in room.vertices]
                for idx in range(len(verts)):
                    a, b = verts[idx], verts[(idx + 1) % len(verts)]
                    plt.plot([a[0], b[0]], [a[1], b[1]], color=colors[idx])
            plt.show()

            raise ValueError(msg)

        logger.info(f"{Fore.GREEN}{msg}{Fore.RESET}")

    def _sort_vertices(self, vertices: list[tuple]) -> list[tuple]:
        cx = sum(x for x, y in vertices) / max(len(vertices), 1)
        cy = sum(y for x, y in vertices) / max(len(vertices), 1)
        clockwise = sorted(
            vertices,
            key=lambda v: (-math.atan2(v[1] - cy, v[0] - cx)) % (2 * math.pi),
        )
        min_vertex = min(clockwise, key=lambda v: v[0])
        idx = clockwise.index(min_vertex)
        return clockwise[idx:] + clockwise[:idx]

    def _get_full_vertices(
        self, original_vertices: list[tuple], all_vertices: list[tuple]
    ) -> list[tuple]:
        lines = [
            LineString([
                original_vertices[i],
                original_vertices[(i + 1) % len(original_vertices)],
            ])
            for i in range(len(original_vertices))
        ]
        full = []
        for vertex in all_vertices:
            point = Point(vertex)
            for line in lines:
                if line.intersects(point):
                    full.append(vertex)
                    break
        return full

    def _check_interior_angles(self, vertices: list[tuple]) -> bool:
        n = len(vertices)
        for i in range(n):
            a, b, c = vertices[i], vertices[(i + 1) % n], vertices[(i + 2) % n]
            angle = abs(math.degrees(
                math.atan2(c[1] - b[1], c[0] - b[0])
                - math.atan2(a[1] - b[1], a[0] - b[0])
            ))
            if angle < 90 or angle > 270:
                return False
        return True

    def _check_validity(self, floor_plan: FloorPlan) -> tuple[bool, str]:
        rooms = floor_plan.rooms
        polygons = [Polygon([tuple(v) for v in r.vertices]) for r in rooms]

        for room in rooms:
            if not self._check_interior_angles([tuple(v) for v in room.vertices]):
                return False, "All interior angles must be >= 90 degrees."

        if len(polygons) == 1:
            return True, "The floor plan is valid. (Only one room)"

        for i, poly_i in enumerate(polygons):
            has_neighbor = False
            for j, poly_j in enumerate(polygons):
                if i == j:
                    continue
                if (
                    poly_i.equals(poly_j)
                    or poly_i.contains(poly_j)
                    or poly_j.contains(poly_i)
                ):
                    return False, "Room polygons must not overlap."
                if isinstance(poly_i.intersection(poly_j), LineString):
                    has_neighbor = True
                for vertex in rooms[j].vertices:
                    if poly_i.contains(Point(vertex)):
                        return False, "No vertex of a room can be inside another room."
            if not has_neighbor:
                return False, "Each room must share an edge with at least one other room."

        return True, "The floor plan is valid."


    def _select_materials(self, designs: list[str], topk: int) -> dict:
        candidate_materials = self.material_selector.match_material(designs, topk=topk)[0]
        top_materials = [materials[0] for materials in candidate_materials]
        filtered = [
            [m for m in materials if m not in self.used_assets]
            for materials in candidate_materials
        ]
        selected = [
            (filtered[i][0] if filtered[i] else top_materials[i])
            for i in range(len(designs))
        ]
        return {design: {"name": selected[i]} for i, design in enumerate(designs)}

    def visualize_floor_plan(self, query: str, floor_plan: FloorPlan) -> None:
        plt.rcParams["font.family"] = "Times New Roman"
        plt.rcParams["font.size"] = 22
        fig, ax = plt.subplots(figsize=(10, 10))
        colors = [
            (0.53, 0.81, 0.98, 0.5),
            (0.56, 0.93, 0.56, 0.5),
            (0.94, 0.5, 0.5, 0.5),
            (1.0, 1.0, 0.88, 0.5),
        ]
        for i, room in enumerate(floor_plan.rooms):
            coords = [tuple(v) for v in room.vertices]
            patch = patches.Polygon(coords, closed=True, edgecolor="black", linewidth=2)
            patch.set_facecolor(colors[i % len(colors)])
            ax.add_patch(patch)
            x, y = zip(*coords)
            ax.scatter(x, y, s=100, color="black")

        ax.set_aspect("equal")
        ax.autoscale_view()
        ax.axis("off")
        plt.savefig(f"{query.replace(' ', '_')}.pdf", bbox_inches="tight", dpi=300)
        plt.show()



class MaterialSelector:
    def __init__(self, clip_model, clip_preprocess, clip_tokenizer, assets: BaseAssets):
        self.assets = assets

        materials = self.assets.read_json(HOLODECK_MATERIALS_DIR / "material-database.json")
        self.selected_materials = materials["Wall"] + materials["Wood"] + materials["Fabric"]
        self.colors = list(mcolors.CSS4_COLORS.keys())

        self.clip_model      = clip_model
        self.clip_preprocess = clip_preprocess
        self.clip_tokenizer  = clip_tokenizer

        self.load_features()

    def load_features(self):
        clip_pkl_path  = HOLODECK_MATERIALS_DIR / "material_feature_clip.pkl"
        color_pkl_path = HOLODECK_MATERIALS_DIR / "color_feature_clip.pkl"

        # ── CLIP-признаки материалов ──────────────────────────────────────
        if self.assets.exists(clip_pkl_path):
            self.material_feature_clip = self.assets.read_pickle(clip_pkl_path)
        else:
            logger.debug("Precompute image features for materials...")
            self.material_feature_clip = []
            for material in tqdm(self.selected_materials):
                img_bytes = self.assets.read_bytes(
                    HOLODECK_MATERIALS_DIR / f"images/{material}.png"
                )
                image = self.clip_preprocess(
                    Image.open(io.BytesIO(img_bytes))
                ).unsqueeze(0)
                with torch.no_grad():
                    image_features = self.clip_model.encode_image(image)
                    image_features /= image_features.norm(dim=-1, keepdim=True)
                self.material_feature_clip.append(image_features)
            self.material_feature_clip = torch.vstack(self.material_feature_clip)
            self.assets.write_pickle(clip_pkl_path, self.material_feature_clip)

        # ── CLIP-признаки цветов ──────────────────────────────────────────
        if self.assets.exists(color_pkl_path):
            self.color_feature_clip = self.assets.read_pickle(color_pkl_path)
        else:
            logger.debug("Precompute text features for colors...")
            with torch.no_grad():
                self.color_feature_clip = self.clip_model.encode_text(
                    self.clip_tokenizer(self.colors)
                )
                self.color_feature_clip /= self.color_feature_clip.norm(dim=-1, keepdim=True)
            self.assets.write_pickle(color_pkl_path, self.color_feature_clip)

    def match_material(self, queries, topk=5):
        with torch.no_grad():
            query_feature_clip  = self.clip_model.encode_text(self.clip_tokenizer(queries))
            query_feature_clip /= query_feature_clip.norm(dim=-1, keepdim=True)

        clip_similarity = query_feature_clip @ self.material_feature_clip.T
        string_similarity = torch.tensor([
            [self.string_match(query, material) for material in self.selected_materials]
            for query in queries
        ])

        joint_similarity = string_similarity + clip_similarity

        results, scores = [], []
        for sim in joint_similarity:
            indices = torch.argsort(sim, descending=True)[:topk]
            results.append([self.selected_materials[ind] for ind in indices])
            scores.append([sim[ind] for ind in indices])
        return results, scores

    def select_color(self, queries, topk=5):
        with torch.no_grad():
            query_feature_clip  = self.clip_model.encode_text(self.clip_tokenizer(queries))
            query_feature_clip /= query_feature_clip.norm(dim=-1, keepdim=True)

        clip_similarity = query_feature_clip @ self.color_feature_clip.T

        results, scores = [], []
        for sim in clip_similarity:
            indices = torch.argsort(sim, descending=True)[:topk]
            results.append([self.colors[ind] for ind in indices])
            scores.append([sim[ind] for ind in indices])
        return results, scores

    def string_match(self, a, b):
        return SequenceMatcher(None, a, b).ratio()
