from ml_service.db.furniture_db import FURNITURE_DB
from ml_service.schema.dto import FurnitureItem

from typing import List, Dict
import numpy as np



class LayoutPlanner:
    @staticmethod
    def calculate_optimal_placement(room_dims: List[float],
                                   furniture_types: List[str],
                                   style: str = "modern",
                                   constraints: Dict = None) -> List[FurnitureItem]:
        
        if constraints is None:
            constraints = {}
        
        length, width, height = room_dims
        placements = []
        
        zones = {
            "center": [length/2, width/2],
            "window": [length/2, width - 1.0],
            "wall_left": [1.0, width/2],
            "wall_right": [length - 1.0, width/2],
            "corner": [1.5, 1.5]
        }
        
        for i, furniture_type in enumerate(furniture_types):
            if furniture_type not in FURNITURE_DB:
                continue
            
            size = FURNITURE_DB[furniture_type]["size"]
            
            if furniture_type in ["sofa", "tv_stand"]:
                zone = zones["window"]
                rotation = [0, 0, 0]
            elif furniture_type in ["coffee_table", "dining_table"]:
                zone = zones["center"]
                rotation = [0, 0, 0]
            elif furniture_type in ["wardrobe"]:
                zone = zones["wall_left"]
                rotation = [0, 0, np.pi/2]
            elif furniture_type in ["bed"]:
                zone = zones["wall_right"]
                rotation = [0, 0, np.pi/2]
            else:
                angle = (2 * np.pi * i) / len(furniture_types)
                radius = min(length, width) / 3
                zone = [length/2 + radius * np.cos(angle), width/2 + radius * np.sin(angle)]
                rotation = [0, 0, angle]
            
            x = max(size[0]/2, min(zone[0], length - size[0]/2))
            y = max(size[1]/2, min(zone[1], width - size[1]/2))
            z = size[2]/2
            
            placement = FurnitureItem(
                type=furniture_type,
                position=[x, y, z],
                rotation=rotation,
                scale=[1.0, 1.0, 1.0],
                color=FURNITURE_DB[furniture_type]["default_color"]
            )
            placements.append(placement)
        
        return placements
    

layout_planner = LayoutPlanner()
