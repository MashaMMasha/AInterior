from ml_api.db.furniture_db import FURNITURE_DB

from typing import Dict, Any

class AIAssistant:
    """Mock-реализация ИИ-ассистента. В продакшене заменить на LLM."""
    
    def __init__(self):
        self.style_keywords = {
            "modern": ["современный", "minimal", "чистый", "геометричный"],
            "classic": ["классический", "дерево", "элегантный", "baroque"],
            "scandinavian": ["скандинавский", "светлый", "дуб", "простой"],
            "industrial": ["индустриальный", "металл", "грубый", "loft"]
        }
        
        self.room_furniture_map = {
            "living_room": ["sofa", "coffee_table", "tv_stand", "armchair"],
            "bedroom": ["bed", "wardrobe", "armchair"],
            "kitchen": ["dining_table"],
            "office": ["desk", "office_chair", "bookshelf"]
        }
    
    def parse_request(self, text: str, room_type: str = "living_room") -> Dict[str, Any]:
        text_lower = text.lower()
        result = {
            "furniture": [],
            "style": "modern",
            "action": "add",
            "constraints": {}
        }

        for style, keywords in self.style_keywords.items():
            if any(kw in text_lower for kw in keywords):
                result["style"] = style
                break

        for furniture_type in FURNITURE_DB.keys():
            if furniture_type.replace("_", " ") in text_lower:
                result["furniture"].append(furniture_type)

        if not result["furniture"]:
            result["furniture"] = self.room_furniture_map.get(room_type, ["sofa", "coffee_table"])

        if "у окна" in text_lower:
            result["constraints"]["near_window"] = True
        if "у стены" in text_lower:
            result["constraints"]["near_wall"] = True

        return result

assistant = AIAssistant()
