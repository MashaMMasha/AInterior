import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import numpy as np
import trimesh

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import LLM, BaseChatModel
from langchain_core.messages import (AIMessage, BaseMessage, HumanMessage,
                                     SystemMessage)
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.prompts import ChatPromptTemplate

from obllomov.agents.generator import FurnitureGenerator, furniture_generator
from obllomov.agents.llm import llm
from obllomov.agents.planner import LayoutPlanner, layout_planner
from obllomov.db.furniture_db import FURNITURE_DB
from obllomov.schema.dto import FurnitureItem
from obllomov.shared.log import logger


class ObLLoMov:
    def __init__(self):
        self.llm: BaseChatModel = llm
        self.furniture_generator = FurnitureGenerator()
        self.layout_planner = LayoutPlanner()

    def parse_request(self, request):
        prompt = ChatPromptTemplate.from_messages([
            # SystemMessage("Ты профессиональный дизайнер интерьеров. Отвечай на вопросы кратко и по делу"),
            ("system", "Ты профессиональный дизайнер интерьеров. Отвечай на вопросы кратко и по делу"),
            # HumanMessage("{question}")
            ("user", "{question}")
        ])

        chain = prompt | llm

        response = chain.invoke({
            "question": request,
        })

        logger.debug(response)

        return response

    
    def auto_arrange_furniture(self, query):
        request = self.parse_request(query)

        placements =self.planner.calculate_optimal_placement(
            room_dims=request.dimensions,
            furniture_types=request["furniture"],
            style=request["style"],
            constraints=request.get("constraints", {})
        )
        
        scene = self._create_complete_scene(request.dimensions, placements)

        return scene
    
    def edit_furniture(item, modifications):
        mesh = furniture_generator.create_mesh(item.type, item.scale, item.color)
        
        if "new_color" in modifications:
            mesh.visual.vertex_colors = np.tile(modifications["new_color"], (len(mesh.vertices), 1))
        
        if "resize" in modifications:
            scale = np.array(modifications["resize"])
            mesh.apply_scale(scale)

        return mesh
        

    def _create_complete_scene(self, room_dims, placements):
        scene = trimesh.Scene()
    
        floor = trimesh.creation.box(extents=[room_dims[0], room_dims[1], 0.05])
        floor.apply_translation([room_dims[0]/2, room_dims[1]/2, -0.025])
        floor.visual.vertex_colors = [0.9, 0.9, 0.9, 1.0]
        scene.add_geometry(floor, node_name="floor")
        
        wall_thickness = 0.1
        wall_height = room_dims[2]
        
        walls = [
            {"name": "wall_front", "pos": [room_dims[0]/2, 0, wall_height/2], "size": [room_dims[0], wall_thickness, wall_height]},
            {"name": "wall_back", "pos": [room_dims[0]/2, room_dims[1], wall_height/2], "size": [room_dims[0], wall_thickness, wall_height]},
            {"name": "wall_left", "pos": [0, room_dims[1]/2, wall_height/2], "size": [wall_thickness, room_dims[1], wall_height]},
            {"name": "wall_right", "pos": [room_dims[0], room_dims[1]/2, wall_height/2], "size": [wall_thickness, room_dims[1], wall_height]},
        ]
        
        for wall in walls:
            wall_mesh = trimesh.creation.box(extents=wall["size"])
            wall_mesh.apply_translation(wall["pos"])
            wall_mesh.visual.vertex_colors = [0.95, 0.95, 0.9, 1.0]
            scene.add_geometry(wall_mesh, node_name=wall["name"])
        
        for i, item in enumerate(placements):
            mesh = furniture_generator.create_mesh(
                item.type,
                item.scale,
                item.color
            )
            
            transform = trimesh.transformations.compose_matrix(
                translate=item.position,
                angles=item.rotation
            )
            mesh.apply_transform(transform)
            
            scene.add_geometry(mesh, node_name=f"{item.type}_{i:02d}")
        
        return scene

