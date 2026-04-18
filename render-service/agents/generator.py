from render_service.db.furniture_db import FURNITURE_DB
from render_service.agents.chat_assistant import assistant

from typing import List, Dict, Any
import trimesh
import numpy as np
from pathlib import Path
from datetime import datetime

class FurnitureGenerator:
    
    def create_mesh(furniture_type: str, 
                   scale: List[float] = None,
                   color: List[float] = None) -> trimesh.Trimesh:
        
        if furniture_type not in FURNITURE_DB:
            raise ValueError(f"Неизвестный тип мебели: {furniture_type}")
        
        data = FURNITURE_DB[furniture_type]
        size = np.array(data["size"])
        
        if scale:
            size *= np.array(scale)
        
        if furniture_type == "sofa":
            base = trimesh.creation.box(extents=size)
            back = trimesh.creation.box(extents=[size[0], 0.2, size[2]*0.6])
            back.apply_translation([0, size[1]/2 - 0.1, size[2]*0.3])
            base = base.union(back)
        elif furniture_type == "bed":
            base = trimesh.creation.box(extents=size)
            headboard = trimesh.creation.box(extents=[size[0], 0.1, size[2]*0.5])
            headboard.apply_translation([0, size[1]/2 - 0.05, size[2]*0.25])
            base = base.union(headboard)
        else:
            base = trimesh.creation.box(extents=size)
        
        if color is None:
            color = data["default_color"]
        
        base.visual.vertex_colors = np.tile(color, (len(base.vertices), 1))
        
        return base
    
    def generate_from_request(request) -> Dict[str, Any]:
        furniture_type = request["furniture"][0]

        mesh = FurnitureGenerator.create_mesh(
            furniture_type,
            color=request["color"]
        )
        
        
        return {
            "type": furniture_type,
            "style": request["style"],
            "vertices": len(mesh.vertices),
            "faces": len(mesh.faces),
            "mesh": mesh
        }

    @staticmethod
    def generate_from_text(text: str, output_dir: Path) -> Dict[str, Any]:
        parsed = assistant.parse_request(text)
        furniture_type = parsed["furniture"][0]
        
        mesh = FurnitureGenerator.create_mesh(
            furniture_type,
            color=parsed.get("color")
        )
        
        output_dir.mkdir(exist_ok=True)
        model_path = output_dir / f"{furniture_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.glb"
        mesh.export(str(model_path))
        
        return {
            "type": furniture_type,
            "path": str(model_path),
            "style": parsed["style"],
            "vertices": len(mesh.vertices),
            "faces": len(mesh.faces)
        }


furniture_generator = FurnitureGenerator()
