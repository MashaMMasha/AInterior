from time import sleep
import os
from typing import *

import compress_json
import matplotlib.colors as mcolors
import numpy as np
import open_clip
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

from obllomov.agents.encoders import CLIPEncoder, SBERTEncoder
from obllomov.agents.planners import (CeilingPlanner, DoorPlanner,
                                      FloorObjectPlanner, FloorPlanner,
                                      SmallObjectPlanner, WallObjectPlanner,
                                      WallPlanner, WindowPlanner)
from obllomov.agents.planners.controllers import AI2thorObjectController
from obllomov.agents.retrievers import (BaseRetriever, ItemRetriever,
                                        ObjathorRetriever, ObjectRetriever)
from obllomov.agents.selectors import MaterialSelector, ObjectSelector
from obllomov.agents.editors import SceneEditor

from obllomov.schemas.domain.annotations import Annotation, AnnotationDict
from obllomov.schemas.domain.scene import ScenePlan
from obllomov.schemas.domain.raw import RawScenePlan
from obllomov.services.events import AsyncEventCallback, EventCallback, StageEvent

from obllomov.shared.log import logger
from obllomov.shared.path import (ABS_ROOT_PATH, HOLODECK_BASE_DATA_DIR,
                                  HOLODECK_THOR_ANNOTATIONS_PATH, HOLODECK_THOR_FEATURES_DIR, 
                                  OBJATHOR_ANNOTATIONS_PATH, OBJATHOR_FEATURES_DIR)

from obllomov.shared.time import NOW

from obllomov.storage.assets import BaseAssets
from obllomov.storage.annotations import load_annotations


class StageResult(BaseModel):
    stage: str
    scene_plan: ScenePlan
    raw_scene_plan: RawScenePlan


class ObLLoMov:
    def __init__(self, llm: BaseChatModel, assets: BaseAssets):
        self.llm = llm
        self.assets = assets

        self._init_encoders()

        self._init_retrievers()

        self._init_selectors()

        self._init_planners()

        self._init_editors()

        self.additional_requirements_room = "N/A"


    def _init_encoders(self):
        sbert_model = SentenceTransformer("all-mpnet-base-v2", device="cpu")

        (
            clip_model,
            _,
            clip_preprocess,
        ) = open_clip.create_model_and_transforms(
            "ViT-L-14", pretrained="laion2b_s32b_b82k"
        )

        clip_tokenizer = open_clip.get_tokenizer("ViT-L-14")

        self.clip_encoder = CLIPEncoder(clip_model, clip_tokenizer, clip_preprocess)
        self.sbert_encoder = SBERTEncoder(sbert_model)


    def _init_retrievers(self):
        logger.debug("Initing retrievers...")

        materials_data = self.assets.read_json(HOLODECK_BASE_DATA_DIR / "materials/material-database.json")
        self.selected_materials = materials_data["Wall"] + materials_data["Wood"] + materials_data["Fabric"]
        self.material_retriever = ItemRetriever.from_assets(
            self.assets,
            feature_path=HOLODECK_BASE_DATA_DIR / "materials/material_feature_clip.pkl",
            encoder=self.clip_encoder,
            items=self.selected_materials
        )

        colors = list(mcolors.CSS4_COLORS.keys())
        self.color_retriever = ItemRetriever.from_assets(
            self.assets,
            feature_path=HOLODECK_BASE_DATA_DIR / "materials/color_feature_clip.pkl",
            encoder=self.clip_encoder,
            items=colors
        )

        self.door_data = self.assets.read_json(HOLODECK_BASE_DATA_DIR / "doors/door-database.json")
        doors =list(self.door_data.keys())
        self.door_retriever = ItemRetriever.from_assets(
            self.assets,
            feature_path=HOLODECK_BASE_DATA_DIR / "doors/door_feature_clip.pkl",
            encoder=self.clip_encoder,
            items=doors
        )

        self.window_data =  self.assets.read_json(HOLODECK_BASE_DATA_DIR / "windows/window-database.json")

        self.annotations = load_annotations(self.assets, 
                                            sources=[OBJATHOR_ANNOTATIONS_PATH, HOLODECK_THOR_ANNOTATIONS_PATH]
                                            )

        self.objathor_retriever = ObjathorRetriever.from_assets(
            self.assets,
            clip_encoder=self.clip_encoder,
            sbert_encoder=self.sbert_encoder,
            sources=[
                {"features_dir": OBJATHOR_FEATURES_DIR},
                {"features_dir": HOLODECK_THOR_FEATURES_DIR},
            ],
            items=list(self.annotations.keys())
        )

    def _init_selectors(self):
        self.material_selector = MaterialSelector(self.material_retriever, self.color_retriever)

        self.object_selector = ObjectSelector(self.objathor_retriever, self.llm,
                                              self.annotations,
                                              similarity_threshold_floor=15,
                                              similarity_threshold_wall=15,
                                              )

    def _init_planners(self):
        logger.debug("Initing planners...")
        self.floor_planner = FloorPlanner(self.material_selector, self.llm, self.assets)

        self.wall_planner = WallPlanner(self.llm)

        self.door_planner = DoorPlanner(self.door_retriever, self.door_data, self.llm)

        self.window_planner = WindowPlanner(self.window_data, self.llm)

        self.floor_object_planner = FloorObjectPlanner(self.llm, self.assets, self.annotations)

        self.wall_object_planner = WallObjectPlanner(self.llm, self.assets, self.annotations)

        self.ceiling_planner = CeilingPlanner(self.llm, self.assets, self.objathor_retriever, self.annotations)

        self.object_controller = AI2thorObjectController(self.assets)
        self.small_object_planner = SmallObjectPlanner(self.llm, self.assets, self.objathor_retriever, self.annotations, self.object_controller)

    def _init_editors(self):
        self.editor = SceneEditor(self.llm, 
                                  self.material_selector, 
                                  self.objathor_retriever, 
                                  self.annotations, 
                                  max_steps=4
                                  )


    def _default_procedural_parameters(self) -> dict:
        base = compress_json.load(
            os.path.join(ABS_ROOT_PATH, "agents/empty_house.json")
        )
        params = base.get("proceduralParameters", {})
        params["lights"] = []
        return params

    def save_scene(self, scene, query, save_dir, add_time=True):
        query_name = query.replace(" ", "_").replace("'", "")[50].rstrip("_")

        if add_time:
            create_time = (
                str(NOW())
                .replace(" ", "-")
                .replace(":", "-")
                .replace(".", "-")
            )
            folder_name = f"{query_name}-{create_time}"
        else:
            folder_name = query_name

        save_dir = os.path.abspath(os.path.join(save_dir, folder_name))
        os.makedirs(save_dir, exist_ok=True)
        compress_json.dump(
            scene,
            os.path.join(save_dir, f"{query_name}.json"),
            json_kwargs=dict(indent=4),
        )

    def _plan_stages(
        self,
        scene_plan: ScenePlan,
        raw_scene_plan: RawScenePlan,
        used_assets: list,
        add_ceiling: bool,
        use_constraint: bool,
    ) -> Generator[StageResult, None, None]:
        self.floor_planner.used_assets = used_assets
        floor_plan, raw_scene_plan.raw_floor_plan = self.floor_planner.plan(
            scene_plan,
            raw=raw_scene_plan.raw_floor_plan,
            additional_requirements=self.additional_requirements_room,
        )
        scene_plan.rooms = floor_plan.rooms
        yield StageResult(stage="floor", scene_plan=scene_plan, raw_scene_plan=raw_scene_plan)

        wall_plan, raw_scene_plan.raw_wall_plan = self.wall_planner.plan(
            scene_plan,
            raw=raw_scene_plan.raw_wall_plan,
            additional_requirements="The wall height should be between 2.0 and 4.5m",
        )
        scene_plan.wall_height = wall_plan.wall_height
        scene_plan.walls = wall_plan.walls
        yield StageResult(stage="walls", scene_plan=scene_plan, raw_scene_plan=raw_scene_plan)

        door_plan, raw_scene_plan.raw_door_plan = self.door_planner.plan(
            scene_plan,
            raw=raw_scene_plan.raw_door_plan,
            additional_requirements="Bedrooms and bathrooms should not have open walls, all doors should be doorways"
        )
        scene_plan.doors = door_plan.doors
        scene_plan.room_pairs = door_plan.room_pairs
        scene_plan.open_room_pairs = door_plan.open_room_pairs
        updated_wall_plan, open_walls = self.wall_planner.update_walls(
            wall_plan,
            scene_plan.open_room_pairs,
        )
        scene_plan.walls = updated_wall_plan.walls
        scene_plan.open_walls = open_walls
        yield StageResult(stage="doors", scene_plan=scene_plan, raw_scene_plan=raw_scene_plan)

        window_plan, raw_scene_plan.raw_window_plan = self.window_planner.plan(
            scene_plan,
            raw=raw_scene_plan.raw_window_plan,
            additional_requirements="Only one wall of each room should have windows. If room has open wall with another bigger room, it can have no windows. Bathrooms shouldn'thave windows",
        )
        scene_plan.windows = window_plan.windows
        scene_plan.walls = window_plan.walls
        yield StageResult(stage="windows", scene_plan=scene_plan, raw_scene_plan=raw_scene_plan)

        self.object_selector.used_assets = used_assets
        object_selection_plan, selected_objects = self.object_selector.select(
            scene_plan,
            raw=raw_scene_plan.raw_object_selection,
        )
        scene_plan.object_selection_plan = object_selection_plan
        scene_plan.selected_objects = selected_objects
        raw_scene_plan.raw_object_selection = object_selection_plan
        yield StageResult(stage="object_selection", scene_plan=scene_plan, raw_scene_plan=raw_scene_plan)

        floor_objects, raw_scene_plan.raw_floor_object_constraints = self.floor_object_planner.plan(
            scene_plan,
            raw=raw_scene_plan.raw_floor_object_constraints,
            use_constraint=use_constraint,
        )
        scene_plan.floor_objects = floor_objects
        yield StageResult(stage="floor_objects", scene_plan=scene_plan, raw_scene_plan=raw_scene_plan)

        wall_object_plan, raw_scene_plan.raw_wall_object_constraints = self.wall_object_planner.plan(
            scene_plan,
            raw=raw_scene_plan.raw_wall_object_constraints,
            use_constraint=use_constraint,
        )
        scene_plan.wall_objects = wall_object_plan.wall_objects
        yield StageResult(stage="wall_objects", scene_plan=scene_plan, raw_scene_plan=raw_scene_plan)

        receptacle_ids = self.object_controller.start(scene_plan)
        small_object_plan = self.small_object_planner.plan(scene_plan, receptacle_ids)
        scene_plan.small_objects = small_object_plan.small_objects
        scene_plan.receptacle2small_objects = small_object_plan.receptacle2small_objects
        yield StageResult(stage="small_objects", scene_plan=scene_plan, raw_scene_plan=raw_scene_plan)

        if add_ceiling:
            ceiling_plan, raw_scene_plan.raw_ceiling_plan = self.ceiling_planner.plan(
                scene_plan,
                raw=raw_scene_plan.raw_ceiling_plan,
            )
            scene_plan.ceiling_objects = ceiling_plan.ceiling_objects
            yield StageResult(stage="ceiling", scene_plan=scene_plan, raw_scene_plan=raw_scene_plan)

    async def generate_scene(
        self,
        query: str,
        save_dir: str,
        used_assets=[],
        add_ceiling=False,
        generate_image=True,
        generate_video=False,
        add_time=True,
        use_constraint=True,
        random_selection=False,
        use_milp=False,
        callback: Optional[EventCallback] = None,
        async_callback: Optional[AsyncEventCallback] = None,
    ) -> Tuple[Dict[str, Any], str]:
        query = query.replace("_", " ")

        scene_plan = ScenePlan(
            query=query,
            procedural_parameters=self._default_procedural_parameters(),
        )
        raw_scene_plan = RawScenePlan()

        total_steps = 9 if add_ceiling else 8
        stages = self._plan_stages(scene_plan, raw_scene_plan, used_assets, add_ceiling, use_constraint)

        for step_num, result in enumerate(stages, start=1):
            if callback or async_callback:
                event = StageEvent(
                    stage=result.stage,
                    completed=step_num,
                    total=total_steps,
                    scene_plan=result.scene_plan,
                    raw_scene_plan=result.raw_scene_plan,
                )
                if callback:
                    callback.on_stage(event)
                if async_callback:
                    await async_callback.on_stage(event)

        final_scene = scene_plan.to_json()

        if callback or async_callback:
            event = StageEvent(
                stage="completed",
                completed=total_steps,
                total=total_steps,
                scene_plan=scene_plan,
                raw_scene_plan=raw_scene_plan,
            )
            if callback:
                callback.on_complete(event)
            if async_callback:
                await async_callback.on_complete(event)

        return final_scene, save_dir

    def edit_scene(self, 
                   query: str, 
                   session_id: str, 
                   scene_plan: ScenePlan,
                   callback: Optional[EventCallback] = None,
                #    async_callback: Optional[AsyncEventCallback] = None,
                   ):
        updated_scene_plan = self.editor.edit(scene_plan, query)

        if callback:
            event = StageEvent(
                stage="edit_completed",
                completed=1,
                total=1,
                scene_plan=updated_scene_plan,
                raw_scene_plan=None,
            )
            if callback:
                callback.on_complete(event)
            # if async_callback:
            #     await async_callback.on_complete(event)

        

