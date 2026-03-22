from datetime import datetime
import hashlib
import trimesh
from ml_api.schema.dto import FurnitureItem
from ml_api.services.s3_service import get_s3_service

from ml_api.agents.chat_assistant import AIAssistant, assistant
from ml_api.agents.generator import FurnitureGenerator, furniture_generator
from ml_api.agents.planner import LayoutPlanner, layout_planner

import numpy as np
import tempfile
import os


class AgentsService:
    def __init__(self):
        self.assistant = AIAssistant()
        self.furniture_generator = FurnitureGenerator()
        self.layout_planner = LayoutPlanner()
        self.s3 = get_s3_service()

    def parse_request(self, query):
        return self.assistant.parse_request(query)

    def generate_from_text(self, query: str):
        request = self.parse_request(query)
        result = self.furniture_generator.generate_from_request(request)

        with tempfile.NamedTemporaryFile(suffix='.glb', delete=False) as tmp:
            tmp_path = tmp.name
            result["mesh"].export(tmp_path)

        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            furniture_type = result.get('furniture_type', 'unknown')
            s3_key = f"models/{furniture_type}_{timestamp}.glb"

            metadata = {
                "furniture_type": furniture_type,
                "generated_at": datetime.now().isoformat(),
                "query": query[:100]
            }

            self.s3.upload_file(tmp_path, s3_key, metadata=metadata, content_type='model/gltf-binary')
            download_url = self.s3.get_presigned_url(s3_key, expiration=3600)

            result["s3_key"] = s3_key
            result["download_url"] = download_url
            result["storage"] = "s3"

            return result
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def auto_arrange_furniture(self, query):
        request = self.parse_request(query)

        placements = self.layout_planner.calculate_optimal_placement(
            room_dims=request.get("dimensions", [5.0, 4.0, 2.7]),
            furniture_types=request["furniture"],
            style=request["style"],
            constraints=request.get("constraints", {})
        )

        scene = self._create_complete_scene(
            request.get("dimensions", [5.0, 4.0, 2.7]),
            placements
        )

        with tempfile.NamedTemporaryFile(suffix='.glb', delete=False) as tmp:
            tmp_path = tmp.name
            scene.export(tmp_path)

        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            scene_hash = hashlib.md5(query.encode()).hexdigest()[:8]
            s3_key = f"scenes/scene_{scene_hash}_{timestamp}.glb"

            metadata = {
                "scene_type": "auto_arranged",
                "style": request["style"],
                "furniture_count": str(len(placements)),
                "generated_at": datetime.now().isoformat()
            }

            self.s3.upload_file(tmp_path, s3_key, metadata=metadata, content_type='model/gltf-binary')
            download_url = self.s3.get_presigned_url(s3_key, expiration=3600)

            return {
                "scene": scene,
                "s3_key": s3_key,
                "download_url": download_url,
                "placements": placements,
                "storage": "s3"
            }
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
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

