from typing import List, Optional, Tuple

import matplotlib.patches as patches
import matplotlib.pyplot as plt
from colorama import Fore
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field
from shapely.geometry import LineString

import obllomov.agents.prompts as prompts
from obllomov.agents.selectors import MaterialSelector
from obllomov.schemas.domain.entries import FloorPlan, RoomPlan, ScenePlan
from obllomov.schemas.domain.raw import RawFloorPlan, RawRoomPlan
from obllomov.shared.geometry import (Polygon2D, Vertex2D, Vertex3D,
                                      check_interior_angles, get_full_vertices,
                                      sort_vertices_clockwise)
from obllomov.shared.log import logger
from obllomov.storage.assets import BaseAssets

from .base import BasePlanner


class FloorPlanner(BasePlanner):
    def __init__(self, material_selector: MaterialSelector, llm: BaseChatModel, assets: BaseAssets):
        super().__init__(llm, assets)

        self.material_selector = material_selector


    def plan(
        self,
        scene_plan: ScenePlan,
        raw: Optional[RawFloorPlan] = None,
        additional_requirements: str = "N/A",
        visualize: bool = False,
    ) -> Tuple[FloorPlan, RawFloorPlan]:
        if raw is None:
            raw = self._structured_plan(
                schema=RawFloorPlan,
                prompt_template=prompts.floor_plan_prompt,
                input_variables={
                    "input": scene_plan.query,
                    "additional_requirements": additional_requirements,
                },
            )

        floor_plan = self._parse_raw(raw)
        self._validate(floor_plan)

        if visualize:
            self.visualize_floor_plan(scene_plan.query, floor_plan)

        return floor_plan, raw

    def _parse_raw(self, raw: RawFloorPlan) -> FloorPlan:
        raw_rooms_with_ids = []
        seen: list[str] = []
        for i, raw_room in enumerate(raw.rooms):
            room_id = raw_room.room_type.lower().replace("'", "").strip()
            if room_id in seen:
                room_id = f"{room_id}-{i}"
            seen.append(room_id)

            sorted_verts = sort_vertices_clockwise(raw_room.vertices)
            raw_room.vertices = sorted_verts

            raw_rooms_with_ids.append((raw_room, room_id))

        all_vertices: list[Vertex2D] = []
        for raw_room, _ in raw_rooms_with_ids:
            all_vertices += raw_room.vertices
        all_vertices = list(set(all_vertices))

        all_designs = []
        for raw_room, _ in raw_rooms_with_ids:
            all_designs.append(raw_room.floor_design.strip().lower())
            all_designs.append(raw_room.wall_design.strip().lower())
            
        design2material = self.material_selector.select_materials(all_designs, topk=5)
        logger.debug(f"design2material: {design2material}")

        rooms = []
        for raw_room, room_id in raw_rooms_with_ids:
            full_verts = get_full_vertices(raw_room.vertices, all_vertices)
            full_verts_sorted = sort_vertices_clockwise(list(set(full_verts)))

            rooms.append(RoomPlan(
                room_type=raw_room.room_type,
                floor_design=raw_room.floor_design,
                wall_design=raw_room.wall_design,
                vertices=raw_room.vertices,
                id=room_id,
                floor_polygon=[
                    Vertex3D(x=v.x, y=0.0, z=v.z) for v in full_verts_sorted
                ],
                full_vertices=full_verts_sorted,
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
                verts = [v.to_tuple() for v in room.vertices]
                for idx in range(len(verts)):
                    a, b = verts[idx], verts[(idx + 1) % len(verts)]
                    plt.plot([a[0], b[0]], [a[1], b[1]], color=colors[idx])
            plt.show()

            raise ValueError(msg)

        logger.info(f"{Fore.GREEN}{msg}{Fore.RESET}")

    def _check_validity(self, floor_plan: FloorPlan) -> tuple[bool, str]:
        rooms = floor_plan.rooms
        polygons = [Polygon2D(vertices=r.vertices) for r in rooms]

        for room in rooms:
            if not check_interior_angles(room.vertices):
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
                    or poly_i.contains_polygon(poly_j)
                    or poly_j.contains_polygon(poly_i)
                ):
                    return False, "Room polygons must not overlap."
                intersection = poly_i.intersection(poly_j)
                if isinstance(intersection, LineString):
                    has_neighbor = True
                if poly_i.contains_point_of(Polygon2D(vertices=rooms[j].vertices)):
                    return False, "No vertex of a room can be inside another room."
            if not has_neighbor:
                return False, "Each room must share an edge with at least one other room."

        return True, "The floor plan is valid."


    def _select_materials(self, designs: list[str], topk: int) -> dict:
        candidate_materials = self.material_selector.select_materials(designs, topk=topk)

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
            coords = [v.to_tuple() for v in room.vertices]
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
