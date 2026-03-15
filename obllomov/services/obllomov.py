import os
from typing import *

import compress_json
import numpy as np
import open_clip
import trimesh
from langchain_core.language_models import LLM, BaseChatModel
from sentence_transformers import SentenceTransformer

from obllomov.agents.planners import FloorPlanner, WallPlanner
from obllomov.shared.log import logger
from obllomov.shared.path import ABS_ROOT_PATH
from obllomov.shared.time import NOW
from obllomov.storage.assets import BaseAssets


class ObLLoMov:
    def __init__(self, llm: BaseChatModel, assets: BaseAssets):
        self.llm = llm
        self.assets = assets

        self.sbert_model = SentenceTransformer("all-mpnet-base-v2", device="cpu")

        (
            self.clip_model,
            _,
            self.clip_preprocess,
        ) = open_clip.create_model_and_transforms(
            "ViT-L-14", pretrained="laion2b_s32b_b82k"
        )

        self.clip_tokenizer = open_clip.get_tokenizer("ViT-L-14")
    

        self.floor_planner = FloorPlanner(
            self.clip_model, self.clip_preprocess, self.clip_tokenizer, 
            self.llm, self.assets
        )

        self.wall_planner = WallPlanner(self.llm)

        self.additional_requirements_room = "N/A"

    def get_empty_scene(self):
        # return self.assets.read_json("agents/empty_house.json")
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
    
    
    def plan_floor(self, scene, additional_requirements_room, used_assets=[]):
        self.floor_planner.used_assets = used_assets
        rooms = self.floor_planner.plan(scene, additional_requirements_room)
        scene["rooms"] = rooms
        return scene
    
    def plan_walls(self, scene):
        wall_height, walls = self.wall_planner.plan(scene)
        scene["wall_height"] = wall_height
        scene["walls"] = walls
        return scene
    

    def save_scene(self, scene, query, save_dir, add_time=True):
        query_name = query.replace(" ", "_").replace("'", "")[:30]
        create_time = (
            str(NOW())
            .replace(" ", "-")
            .replace(":", "-")
            .replace(".", "-")
        )

        if add_time:
            folder_name = f"{query_name}-{create_time}"  # query name + time
        else:
            folder_name = query_name  # query name only

        save_dir = os.path.abspath(os.path.join(save_dir, folder_name))
        os.makedirs(save_dir, exist_ok=True)
        compress_json.dump(
            scene,
            os.path.join(save_dir, f"{query_name}.json"),
            json_kwargs=dict(indent=4),
        )
    
    def generate_scene(
        self,
        scene,
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
        # initialize scene
        query = query.replace("_", " ")
        scene["query"] = query

        # empty house
        scene = self.empty_house(scene)


        scene = self.plan_floor(scene,
            additional_requirements_room=self.additional_requirements_room,
            used_assets=used_assets)
    
        scene = self.plan_walls(scene) 
        
        self.save_scene(scene, query, save_dir, add_time)
