from typing import List, Optional, Tuple

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

import obllomov.agents.prompts as prompts
from obllomov.agents.retrievers import BaseRetriever
from obllomov.agents.selectors.base import BaseSelector
from obllomov.schemas.domain.annotations import Annotation, AnnotationDict
from obllomov.schemas.domain.entries import (CeilingObjectEntry, CeilingPlan,
                                             ScenePlan)
from obllomov.schemas.domain.raw import RawCeilingEntry, RawCeilingPlan
from obllomov.shared.geometry import Polygon2D, Vertex2D, Vertex3D
from obllomov.shared.log import logger
from obllomov.agents.retrievers import ObjathorRetriever
from obllomov.storage.assets import BaseAssets

from .base import BasePlanner


class CeilingPlanner(BasePlanner):
    def __init__(
        self,
        llm: BaseChatModel,
        assets: BaseAssets,
        objathor_retriever: BaseRetriever,
        annotations: AnnotationDict,
    ):
        super().__init__(llm, assets)
        self.objathor_retriever = objathor_retriever
        self.annotations = annotations

    def plan(
        self,
        scene_plan: ScenePlan,
        raw: Optional[RawCeilingPlan] = None,
        additional_requirements: str = "N/A",
    ) -> Tuple[CeilingPlan, RawCeilingPlan]:
        room_types_str = str([r.room_type for r in scene_plan.rooms]).replace("'", "")[1:-1]

        if raw is None:
            raw = self._structured_plan(
                schema=RawCeilingPlan,
                prompt_template=prompts.ceiling_selection_prompt,
                input_variables={
                    "input": scene_plan.query,
                    "rooms": room_types_str,
                    "additional_requirements": additional_requirements,
                },
            )

        return self._parse_raw(raw, scene_plan), raw

    def _parse_raw(self, raw: RawCeilingPlan, scene_plan: ScenePlan) -> CeilingPlan:
        ceiling_objects = []

        for entry in raw.ceiling_objects:
            room = next(
                (r for r in scene_plan.rooms if r.room_type == entry.room_type), None
            )
            if room is None:
                logger.warning(f"Room type {entry.room_type} not found")
                continue

            asset_id = self._select_asset(entry.object_description)
            if asset_id is None:
                continue

            annotation = self.annotations[asset_id]
            dims = annotation.bbox
            floor_polygon = Polygon2D(vertices=room.vertices)
            centroid = floor_polygon.centroid
            y = scene_plan.wall_height - dims.y / 2

            ceiling_objects.append(CeilingObjectEntry(
                asset_id=asset_id,
                id=f"ceiling ({entry.room_type})",
                position=Vertex3D(x=centroid.x, y=y, z=centroid.z),
                rotation=Vertex3D(x=0, y=0, z=0),
                room_id=room.id,
                object_name=annotation.category,
            ))

        return CeilingPlan(ceiling_objects=ceiling_objects)

    def _select_asset(self, description: str) -> Optional[str]:
        candidates = self.objathor_retriever.retrieve_single(
            query=f"a 3D model of {description}",
            topk=50
        )

        candidates = [
            c for c in candidates
            if self.annotations[c[0]].onCeiling
            and self.annotations[c[0]].bbox.y <= 1.0
        ]

        if not candidates:
            logger.warning(f"No ceiling asset found for: {description}")
            return None

        return BaseSelector.random_select(candidates)[0]
