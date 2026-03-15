import ast
import copy
import io
import math
from difflib import SequenceMatcher

import matplotlib.colors as mcolors
import matplotlib.patches as patches
import matplotlib.pyplot as plt
import torch
from colorama import Fore
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import PromptTemplate
from PIL import Image
from shapely.geometry import LineString, Point, Polygon
from tqdm import tqdm

import obllomov.agents.prompts as prompts
from obllomov.shared.env import env
from obllomov.shared.log import logger
from obllomov.shared.path import HOLODECK_MATERIALS_DIR
from obllomov.storage.assets.base import BaseAssets

from .base import BasePlanner


class FloorPlanner(BasePlanner):
    def __init__(self, clip_model, clip_process, clip_tokenizer, llm: BaseChatModel, assets: BaseAssets):
        super().__init__(llm, assets)

        self.json_template = {
            "ceilings": [],
            "children": [],
            "vertices": None,
            "floorMaterial": {"name": None, "color": None},
            "floorPolygon": [],
            "id": None,
            "roomType": None,
        }
        self.material_selector = MaterialSelector(
            clip_model, clip_process, clip_tokenizer, assets
        )


    def plan(self, scene: dict, additional_requirements="N/A", visualize=False):
        self._raw_plan(scene, prompts.floor_plan_prompt,
                       cache_key="raw_floor_plan",
                       input_variables={
                           "input": scene["query"],
                           "additional_requirements": additional_requirements,
                       })

        rooms = self.get_plan(scene["query"], scene["raw_floor_plan"], visualize)
        return rooms

    def get_plan(self, query, raw_plan, visualize=False):
        parsed_plan = self.parse_raw_plan(raw_plan)

        all_designs = []
        for room in parsed_plan:
            all_designs.append(room["floor_design"])
            all_designs.append(room["wall_design"])
        design2material = self.select_materials(all_designs, topk=5)

        for i in range(len(parsed_plan)):
            parsed_plan[i]["floorMaterial"] = design2material[parsed_plan[i]["floor_design"]]
            parsed_plan[i]["wallMaterial"]  = design2material[parsed_plan[i]["wall_design"]]

        if visualize:
            self.visualize_floor_plan(query, parsed_plan)

        return parsed_plan

    def parse_raw_plan(self, raw_plan):
        parsed_plan = []
        room_types  = []
        plans = [plan.lower() for plan in raw_plan.split("\n") if "|" in plan]

        for i, plan in enumerate(plans):
            room_type, floor_design, wall_design, vertices = plan.split("|")
            room_type = room_type.strip().replace("'", "")

            if room_type in room_types:
                room_type += f"-{i}"
            room_types.append(room_type)

            floor_design = floor_design.strip()
            wall_design  = wall_design.strip()
            vertices     = ast.literal_eval(vertices.strip())
            vertices     = [(float(v[0]), float(v[1])) for v in vertices]

            current_plan = copy.deepcopy(self.json_template)
            current_plan["id"]       = room_type
            current_plan["roomType"] = room_type
            current_plan["vertices"], current_plan["floorPolygon"] = self.vertices2xyz(vertices)
            current_plan["floor_design"] = floor_design
            current_plan["wall_design"]  = wall_design
            parsed_plan.append(current_plan)

        all_vertices = []
        for room in parsed_plan:
            all_vertices += room["vertices"]
        all_vertices = list(set(map(tuple, all_vertices)))

        for room in parsed_plan:
            full_vertices = self.get_full_vertices(room["vertices"], all_vertices)
            full_vertices = list(set(map(tuple, full_vertices)))
            room["full_vertices"], room["floorPolygon"] = self.vertices2xyz(full_vertices)

        valid, msg = self.check_validity(parsed_plan)

        if not valid:
            logger.error(f"{Fore.RED}AI: {msg}{Fore.RESET}")

            if env.LOG_LEVEL == "DEBUG":
                import numpy as np
                colors = plt.cm.rainbow(np.linspace(0, 1, len(parsed_plan)))
                for room in parsed_plan:
                    for i in range(len(room["vertices"])):
                        a = room["vertices"][i]
                        b = room["vertices"][(i + 1) % len(room["vertices"])]
                        plt.plot([a[0], b[0]], [a[1], b[1]], color=colors[i])
                plt.show()

            raise ValueError(msg)
        else:
            logger.info(f"{Fore.GREEN}AI: {msg}{Fore.RESET}")
            return parsed_plan

    def vertices2xyz(self, vertices):
        sort_vertices = self.sort_vertices(vertices)
        xyz_vertices  = [{"x": v[0], "y": 0, "z": v[1]} for v in sort_vertices]
        return sort_vertices, xyz_vertices

    def xyz2vertices(self, xyz_vertices):
        return [(v["x"], v["z"]) for v in xyz_vertices]

    def sort_vertices(self, vertices):
        cx = sum(x for x, y in vertices) / max(len(vertices), 1)
        cy = sum(y for x, y in vertices) / max(len(vertices), 1)

        vertices_clockwise = sorted(
            vertices,
            key=lambda v: (-math.atan2(v[1] - cy, v[0] - cx)) % (2 * math.pi)
        )

        min_vertex = min(vertices_clockwise, key=lambda v: v[0])
        min_index  = vertices_clockwise.index(min_vertex)
        return vertices_clockwise[min_index:] + vertices_clockwise[:min_index]

    def get_full_vertices(self, original_vertices, all_vertices):
        lines = [
            LineString([
                original_vertices[i],
                original_vertices[(i + 1) % len(original_vertices)],
            ])
            for i in range(len(original_vertices))
        ]

        full_vertices = []
        for vertex in all_vertices:
            point = Point(vertex)
            for line in lines:
                if line.intersects(point):
                    full_vertices.append(vertex)

        return full_vertices

    def select_materials(self, designs, topk):
        candidate_materials = self.material_selector.match_material(designs, topk=topk)[0]
        candidate_colors    = self.material_selector.select_color(designs, topk=topk)[0]

        top_materials = [[materials[0]] for materials in candidate_materials]
        candidate_materials = [
            [m for m in materials if m not in self.used_assets]
            for materials in candidate_materials
        ]

        selected_materials = []
        for i in range(len(designs)):
            if len(candidate_materials[i]) == 0:
                selected_materials.append(top_materials[i][0])
            else:
                selected_materials.append(candidate_materials[i][0])

        design2materials = {design: {} for design in designs}
        for i, design in enumerate(designs):
            design2materials[design]["name"] = selected_materials[i]

        return design2materials

    def color2rgb(self, color_name):
        rgb = mcolors.to_rgb(color_name)
        return {"r": rgb[0], "g": rgb[1], "b": rgb[2]}

    def parsed2raw(self, rooms):
        raw_plan = ""
        for room in rooms:
            raw_plan += " | ".join([
                room["roomType"],
                room["floor_design"],
                room["wall_design"],
                str(room["vertices"]),
            ])
            raw_plan += "\n"
        return raw_plan

    def check_interior_angles(self, vertices):
        n = len(vertices)
        for i in range(n):
            a, b, c = vertices[i], vertices[(i + 1) % n], vertices[(i + 2) % n]
            angle = abs(math.degrees(
                math.atan2(c[1] - b[1], c[0] - b[0]) -
                math.atan2(a[1] - b[1], a[0] - b[0])
            ))
            if angle < 90 or angle > 270:
                return False
        return True

    def check_validity(self, rooms):
        room_polygons = [Polygon(room["vertices"]) for room in rooms]

        for room in rooms:
            if not self.check_interior_angles(room["vertices"]):
                return False, "All interior angles of the room must be greater than or equal to 90 degrees."

        if len(room_polygons) == 1:
            return True, "The floor plan is valid. (Only one room)"

        for i in range(len(room_polygons)):
            has_neighbor = False
            for j in range(len(room_polygons)):
                if i != j:
                    if (
                        room_polygons[i].equals(room_polygons[j])
                        or room_polygons[i].contains(room_polygons[j])
                        or room_polygons[j].contains(room_polygons[i])
                    ):
                        return False, "Room polygons must not overlap."
                    intersection = room_polygons[i].intersection(room_polygons[j])
                    if isinstance(intersection, LineString):
                        has_neighbor = True
                    for vertex in rooms[j]["vertices"]:
                        if Polygon(rooms[i]["vertices"]).contains(Point(vertex)):
                            return False, "No vertex of a room can be inside another room."
            if not has_neighbor:
                return False, "Each room polygon must share an edge with at least one other room polygon."

        return True, "The floor plan is valid."

    def visualize_floor_plan(self, query, parsed_plan):
        plt.rcParams["font.family"] = "Times New Roman"
        plt.rcParams["font.size"]   = 22
        fig, ax = plt.subplots(figsize=(10, 10))
        colors  = [
            (0.53, 0.81, 0.98, 0.5),
            (0.56, 0.93, 0.56, 0.5),
            (0.94, 0.5,  0.5,  0.5),
            (1.0,  1.0,  0.88, 0.5),
        ]

        for i, room in enumerate(parsed_plan):
            coordinates = room["vertices"]
            polygon = patches.Polygon(coordinates, closed=True, edgecolor="black", linewidth=2)
            polygon.set_facecolor(colors[i % len(colors)])
            ax.add_patch(polygon)

        for room in parsed_plan:
            coordinates = room["vertices"]
            x, y = zip(*coordinates)
            ax.text(sum(x) / len(x), sum(y) / len(y), room["roomType"], ha="center", va="center")
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
