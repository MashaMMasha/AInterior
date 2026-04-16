import os
from typing import *

import compress_json
import matplotlib.colors as mcolors
import numpy as np
import open_clip
from langchain_core.language_models import BaseChatModel
from sentence_transformers import SentenceTransformer

from obllomov.agents.encoders import CLIPEncoder, SBERTEncoder
from obllomov.agents.planners import (CeilingPlanner, DoorPlanner,
                                      FloorObjectPlanner, FloorPlanner,
                                      SmallObjectPlanner, WallObjectPlanner,
                                      WallPlanner, WindowPlanner)
from obllomov.agents.retrievers import (BaseRetriever, ItemRetriever,
                                        ObjathorRetriever, ObjectRetriever)
from obllomov.agents.selectors import MaterialSelector, ObjectSelector

from obllomov.schemas.domain.annotations import Annotation, AnnotationDict
from obllomov.schemas.domain.entries import ScenePlan
from obllomov.schemas.domain.raw import RawScenePlan

from obllomov.shared.log import logger
from obllomov.shared.path import (ABS_ROOT_PATH, HOLODECK_BASE_DATA_DIR,
                                  HOLODECK_MATERIALS_DIR, HOLODECK_THOR_ANNOTATIONS_PATH,
                                  HOLODECK_THOR_FEATURES_DIR, OBJATHOR_ANNOTATIONS_PATH,
                                  OBJATHOR_FEATURES_DIR)

from obllomov.shared.time import NOW

from obllomov.storage.assets import BaseAssets
from obllomov.storage.annotations import load_annotations


class ObLLoMov:
    def __init__(self, llm: BaseChatModel, assets: BaseAssets):
        self.llm = llm
        self.assets = assets

        self._init_encoders()

        self._init_retrievers()

        self._init_selectors()

        self._init_planners()

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

        self.small_object_planner = SmallObjectPlanner(self.llm, self.assets, self.objathor_retriever, self.annotations)


    def get_empty_scene(self):
        return compress_json.load(
            os.path.join(ABS_ROOT_PATH, "agents/empty_house.json")
        )

    def empty_house(self, scene):
        scene["rooms"] = []
        scene["walls"] = []
        scene["doors"] = []
        scene["windows"] = []
        scene["objects"] = []
        scene["proceduralParameters"]["lights"] = []
        return scene

    def save_scene(self, scene, query, save_dir, add_time=True):
        query_name = query.replace(" ", "_").replace("'", "")[:30].rstrip("_")

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

    def generate_scene(
        self,
        base_scene,
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
    ) -> Tuple[Dict[str, Any], str]:
        query = query.replace("_", " ")
        base_scene = self.empty_house(base_scene)

        scene_plan = ScenePlan(query=query)
        raw_scene_plan = RawScenePlan()

        floor_plan, raw_scene_plan.raw_floor_plan = self.floor_planner.plan(
            scene_plan,
            raw=raw_scene_plan.raw_floor_plan,
            additional_requirements=self.additional_requirements_room,
        )
        self.floor_planner.used_assets = used_assets
        scene_plan.rooms = floor_plan.rooms

        wall_plan, raw_scene_plan.raw_wall_plan = self.wall_planner.plan(
            scene_plan,
            raw=raw_scene_plan.raw_wall_plan,
            additional_requirements="The wall height should be between 2.0 and 4.5m",
        )
        scene_plan.wall_height = wall_plan.wall_height
        scene_plan.walls = wall_plan.walls

        door_plan, raw_scene_plan.raw_door_plan = self.door_planner.plan(
            scene_plan,
            raw=raw_scene_plan.raw_door_plan,
        )
        scene_plan.doors = door_plan.doors
        scene_plan.room_pairs = door_plan.room_pairs
        scene_plan.open_room_pairs = door_plan.open_room_pairs

        updated_wall_plan, open_walls = self.wall_planner.update_walls(
            # WallPlan(wall_height=scene_plan.wall_height, walls=scene_plan.walls),
            wall_plan,
            scene_plan.open_room_pairs,
        )
        scene_plan.walls = updated_wall_plan.walls
        scene_plan.open_walls = open_walls

        window_plan, raw_scene_plan.raw_window_plan = self.window_planner.plan(
            scene_plan,
            raw=raw_scene_plan.raw_window_plan,
            additional_requirements="Only one wall of each room should have windows",
        )
        scene_plan.windows = window_plan.windows
        scene_plan.walls = window_plan.walls

        self.object_selector.used_assets = used_assets
        object_selection_plan, selected_objects = self.object_selector.select(
            scene_plan,
            raw=raw_scene_plan.raw_object_selection,
        )
        scene_plan.object_selection_plan = object_selection_plan
        scene_plan.selected_objects = selected_objects
        raw_scene_plan.raw_object_selection = object_selection_plan

        floor_objects, raw_scene_plan.raw_floor_object_constraints = self.floor_object_planner.plan(
            scene_plan,
            raw=raw_scene_plan.raw_floor_object_constraints,
            use_constraint=use_constraint,
        )
        scene_plan.floor_objects = floor_objects

        wall_object_plan, raw_scene_plan.raw_wall_object_constraints = self.wall_object_planner.plan(
            scene_plan,
            raw=raw_scene_plan.raw_wall_object_constraints,
            use_constraint=use_constraint,
        )
        scene_plan.wall_objects = wall_object_plan.wall_objects

        thor_scene = scene_plan.to_thor_scene(base_scene)
        import json
        with open("/tmp/thor_scene_debug.json", "w") as f:
            json.dump(thor_scene, f, indent=2, default=str)
        logger.debug(f"thor_scene objects count: {len(thor_scene.get('objects', []))}")
        logger.debug(f"thor_scene object ids: {[o.get('id') for o in thor_scene.get('objects', [])]}")
        controller = self.small_object_planner.start_controller(thor_scene)
        event = controller.reset()
        logger.debug(f"thor reset success: {event.metadata.get('lastActionSuccess')}, error: {event.metadata.get('errorMessage')}")
        thor_object_ids = [obj["objectId"] for obj in event.metadata["objects"]]
        logger.debug(f"thor_object_ids: {thor_object_ids}")
        scene_object_ids = {obj["id"] for obj in scene_plan.floor_objects}
        logger.debug(f"scene_object_ids: {scene_object_ids}")
        receptacle_ids = [
            obj["objectId"]
            for obj in event.metadata["objects"]
            if obj["objectId"] in scene_object_ids and "___" not in obj["objectId"]
        ]
        small_object_plan = self.small_object_planner.plan(scene_plan, controller, receptacle_ids)

        # logger.debug(f"small_object_plan: {small_object_plan}")
        scene_plan.small_objects = small_object_plan.small_objects
        scene_plan.receptacle2small_objects = small_object_plan.receptacle2small_objects

        if add_ceiling:
            ceiling_plan, raw_scene_plan.raw_ceiling_plan = self.ceiling_planner.plan(
                scene_plan,
                raw=raw_scene_plan.raw_ceiling_plan,
            )
            scene_plan.ceiling_objects = ceiling_plan.ceiling_objects

        final_scene = scene_plan.to_scene(base_scene)
        self.save_scene(final_scene, query, save_dir, add_time)

        return final_scene, save_dir
