import re
from typing import Any, Dict, List, Optional, Type

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import BaseModel

_mock_responses = {
    "RawFloorPlan": {
        "rooms": [
            {
                "room_type": "living_room",
                "floor_design": "light_oak_parquet",
                "wall_design": "white_eggshell_paint",
                "vertices": [
                    {"x": 0.0, "z": 0.0},
                    {"x": 6.0, "z": 0.0},
                    {"x": 6.0, "z": 5.0},
                    {"x": 0.0, "z": 5.0},
                ],
            },
            {
                "room_type": "bedroom",
                "floor_design": "warm_gray_laminate",
                "wall_design": "soft_blue_matte_paint",
                "vertices": [
                    {"x": 6.0, "z": 1.5},
                    {"x": 8.0, "z": 1.5},
                    {"x": 8.0, "z": 4.5},
                    {"x": 6.0, "z": 4.5},
                ],
            },
            {
                "room_type": "kitchen",
                "floor_design": "white_ceramic_tile",
                "wall_design": "light_gray_subway_tile",
                "vertices": [
                    {"x": 0.0, "z": -2.0},
                    {"x": 4.0, "z": -2.0},
                    {"x": 4.0, "z": 0.0},
                    {"x": 0.0, "z": 0.0},
                ],
            },
        ]
    },
    "RawWallPlan": {"wall_height": 2.7},
    "RawDoorPlan": {
        "doors": [
            {
                "room_type0": "living_room",
                "room_type1": "bedroom",
                "connection_type": "doorway",
                "size": "single",
                "style": "modern minimalist",
            },
            {
                "room_type0": "living_room",
                "room_type1": "kitchen",
                "connection_type": "open",
                "size": "double",
                "style": "N/A",
            },
            {
                "room_type0": "living_room",
                "room_type1": "exterior",
                "connection_type": "doorway",
                "size": "double",
                "style": "contemporary glass-pane",
            },
        ]
    },
    "RawWindowPlan": {
        "windows": [
            {
                "room_id": "living_room",
                "wall_direction": "north",
                "window_type": "fixed",
                "window_size": [240.0, 180.0],
                "quantity": 2,
                "window_height": 180.0,
            },
            {
                "room_id": "bedroom",
                "wall_direction": "east",
                "window_type": "hung",
                "window_size": [130.0, 130.0],
                "quantity": 2,
                "window_height": 130.0,
            },
            {
                "room_id": "kitchen",
                "wall_direction": "south",
                "window_type": "slider",
                "window_size": [150.0, 120.0],
                "quantity": 2,
                "window_height": 120.0,
            },
        ]
    },
    "RawCeilingPlan": {
        "ceiling_objects": [
            {"room_type": "living_room", "object_description": "modern LED panel light"},
            {"room_type": "bedroom", "object_description": "flush mount ceiling light"},
            {"room_type": "kitchen", "object_description": "recessed LED downlight"},
        ]
    },
}

_room_object_responses = {
    "bedroom": {
        "objects": [
            {
                "object_name": "queen-sized platform bed",
                "description": "A minimalist wooden platform bed with a light oak finish and clean lines.",
                "location": "floor",
                "size": [160, 200, 40],
                "quantity": 1,
                "variance_type": "same",
                "objects_on_top": [
                    {"object_name": "bed pillow", "quantity": 3, "variance_type": "varied"},
                    {"object_name": "throw blanket", "quantity": 1, "variance_type": "same"},
                ],
            },
            {
                "object_name": "tall wooden wardrobe",
                "description": "A narrow wardrobe with two doors, made of light birch laminate.",
                "location": "wall",
                "size": [60, 180, 50],
                "quantity": 1,
                "variance_type": "same",
                "objects_on_top": [],
            },
            {
                "object_name": "floating nightstand",
                "description": "A wall-mounted nightstand with a single drawer, white laminate.",
                "location": "wall",
                "size": [40, 50, 30],
                "quantity": 1,
                "variance_type": "same",
                "objects_on_top": [
                    {"object_name": "table lamp", "quantity": 1, "variance_type": "same"},
                ],
            },
            {
                "object_name": "full-length mirror",
                "description": "A slim vertical mirror with a thin black metal frame.",
                "location": "wall",
                "size": [40, 170, 3],
                "quantity": 1,
                "variance_type": "same",
                "objects_on_top": [],
            },
            {
                "object_name": "freestanding clothes rack",
                "description": "A slim curved metal clothes rack in matte black.",
                "location": "floor",
                "size": [100, 40, 160],
                "quantity": 1,
                "variance_type": "same",
                "objects_on_top": [],
            },
        ]
    },
    "kitchen": {
        "objects": [
            {
                "object_name": "kitchen cabinet",
                "description": "White glossy kitchen cabinets with modern handle-less design.",
                "location": "floor",
                "size": [400, 60, 90],
                "quantity": 1,
                "variance_type": "same",
                "objects_on_top": [
                    {"object_name": "small potted herb plant", "quantity": 2, "variance_type": "varied"},
                ],
            },
            {
                "object_name": "refrigerator",
                "description": "Slim stainless steel refrigerator, counter-depth design.",
                "location": "floor",
                "size": [70, 70, 180],
                "quantity": 1,
                "variance_type": "same",
                "objects_on_top": [],
            },
            {
                "object_name": "microwave oven",
                "description": "Countertop microwave oven in stainless steel.",
                "location": "floor",
                "size": [50, 35, 30],
                "quantity": 1,
                "variance_type": "same",
                "objects_on_top": [],
            },
            {
                "object_name": "wall-mounted exhaust hood",
                "description": "Modern stainless steel range hood with LED lighting.",
                "location": "wall",
                "size": [60, 50, 60],
                "quantity": 1,
                "variance_type": "same",
                "objects_on_top": [],
            },
        ]
    },
    "living_room": {
        "objects": [
            {
                "object_name": "three-seater sofa",
                "description": "A light gray fabric three-seater sofa with clean modern lines.",
                "location": "floor",
                "size": [220, 90, 80],
                "quantity": 1,
                "variance_type": "same",
                "objects_on_top": [
                    {"object_name": "throw pillow", "quantity": 3, "variance_type": "varied"},
                ],
            },
            {
                "object_name": "armchair",
                "description": "A mid-century modern armchair in beige boucle fabric.",
                "location": "floor",
                "size": [75, 80, 75],
                "quantity": 2,
                "variance_type": "varied",
                "objects_on_top": [],
            },
            {
                "object_name": "coffee table",
                "description": "A rectangular wooden coffee table with light oak finish.",
                "location": "floor",
                "size": [120, 60, 45],
                "quantity": 1,
                "variance_type": "same",
                "objects_on_top": [
                    {"object_name": "small ceramic vase", "quantity": 1, "variance_type": "same"},
                ],
            },
            {
                "object_name": "media console",
                "description": "A low-profile media console in white matte finish.",
                "location": "floor",
                "size": [180, 45, 50],
                "quantity": 1,
                "variance_type": "same",
                "objects_on_top": [],
            },
            {
                "object_name": "floor lamp",
                "description": "An adjustable arc floor lamp with brushed brass finish.",
                "location": "floor",
                "size": [180, 180, 170],
                "quantity": 1,
                "variance_type": "same",
                "objects_on_top": [],
            },
            {
                "object_name": "bookshelf",
                "description": "A tall narrow bookshelf in natural wood finish with five shelves.",
                "location": "wall",
                "size": [40, 30, 180],
                "quantity": 1,
                "variance_type": "same",
                "objects_on_top": [
                    {"object_name": "hardcover book", "quantity": 8, "variance_type": "varied"},
                ],
            },
            {
                "object_name": "wall art",
                "description": "Minimalist framed prints in black and white with abstract patterns.",
                "location": "wall",
                "size": [60, 40, 3],
                "quantity": 3,
                "variance_type": "varied",
                "objects_on_top": [],
            },
            {
                "object_name": "side table",
                "description": "A round side table with marble top and gold metal base.",
                "location": "floor",
                "size": [50, 50, 55],
                "quantity": 2,
                "variance_type": "same",
                "objects_on_top": [
                    {"object_name": "table lamp", "quantity": 2, "variance_type": "same"},
                ],
            },
        ]
    },
}

_room_floor_constraints = {
    "living_room": {
        "entries": [
            {"object_name": "media console-0", "constraints": [
                {"type": "global", "constraint": "edge", "target": None},
            ]},
            {"object_name": "three-seater sofa-0", "constraints": [
                {"type": "global", "constraint": "edge", "target": None},
                {"type": "direction", "constraint": "face to", "target": "media console-0"},
                {"type": "distance", "constraint": "near", "target": "media console-0"},
                {"type": "alignment", "constraint": "center aligned", "target": "media console-0"},
            ]},
            {"object_name": "armchair-0", "constraints": [
                {"type": "global", "constraint": "edge", "target": None},
                {"type": "relative", "constraint": "side of", "target": "three-seater sofa-0"},
                {"type": "distance", "constraint": "near", "target": "three-seater sofa-0"},
            ]},
            {"object_name": "armchair-1", "constraints": [
                {"type": "global", "constraint": "edge", "target": None},
                {"type": "relative", "constraint": "side of", "target": "three-seater sofa-0"},
                {"type": "distance", "constraint": "near", "target": "three-seater sofa-0"},
            ]},
            {"object_name": "coffee table-0", "constraints": [
                {"type": "global", "constraint": "middle", "target": None},
                {"type": "relative", "constraint": "in front of", "target": "three-seater sofa-0"},
                {"type": "distance", "constraint": "near", "target": "three-seater sofa-0"},
                {"type": "alignment", "constraint": "center aligned", "target": "three-seater sofa-0"},
            ]},
            {"object_name": "side table-0", "constraints": [
                {"type": "global", "constraint": "edge", "target": None},
                {"type": "relative", "constraint": "side of", "target": "three-seater sofa-0"},
                {"type": "distance", "constraint": "near", "target": "three-seater sofa-0"},
            ]},
            {"object_name": "side table-1", "constraints": [
                {"type": "global", "constraint": "edge", "target": None},
                {"type": "relative", "constraint": "side of", "target": "three-seater sofa-0"},
                {"type": "distance", "constraint": "near", "target": "three-seater sofa-0"},
            ]},
            {"object_name": "floor lamp-0", "constraints": [
                {"type": "global", "constraint": "edge", "target": None},
                {"type": "relative", "constraint": "side of", "target": "three-seater sofa-0"},
                {"type": "distance", "constraint": "near", "target": "three-seater sofa-0"},
            ]},
        ]
    },
    "bedroom": {
        "entries": [
            {"object_name": "queen-sized platform bed-0", "constraints": [
                {"type": "global", "constraint": "edge", "target": None},
            ]},
            {"object_name": "freestanding clothes rack-0", "constraints": [
                {"type": "global", "constraint": "edge", "target": None},
                {"type": "distance", "constraint": "far", "target": "queen-sized platform bed-0"},
            ]},
        ]
    },
    "kitchen": {
        "entries": [
            {"object_name": "kitchen cabinet-0", "constraints": [
                {"type": "global", "constraint": "edge", "target": None},
            ]},
            {"object_name": "microwave oven-0", "constraints": [
                {"type": "global", "constraint": "edge", "target": None},
                {"type": "relative", "constraint": "side of", "target": "kitchen cabinet-0"},
                {"type": "distance", "constraint": "near", "target": "kitchen cabinet-0"},
            ]},
        ]
    },
}

_room_wall_constraints = {
    "living_room": {
        "constraints": [
            {"object_name": "wall art-0", "near_floor_object": "media console-0", "height": 120},
            {"object_name": "wall art-1", "near_floor_object": "three-seater sofa-0", "height": 120},
            {"object_name": "wall art-2", "near_floor_object": None, "height": 120},
        ]
    },
    "bedroom": {
        "constraints": [
            {"object_name": "full-length mirror-0", "near_floor_object": "queen-sized platform bed-0", "height": 15},
        ]
    },
    "kitchen": {
        "constraints": []
    },
}

_DEFAULT_ROOM = "living_room"


def _extract_room_type(text: str) -> str:
    m = re.search(r"working on the \*(\w+)\*", text)
    if m:
        return m.group(1)
    for room in _room_object_responses:
        if room in text:
            return room
    return _DEFAULT_ROOM


class ChatMock(BaseChatModel):
    _current_schema: Optional[Type[BaseModel]] = None
    _call_counts: Dict[str, int] = {}

    def with_structured_output(self, schema: Type[BaseModel]) -> "ChatMock":
        self._current_schema = schema
        return self

    def invoke(self, input_data: Any, config=None, **kwargs) -> BaseModel:
        if self._current_schema is None:
            raise ValueError("No schema set. Call with_structured_output first.")

        schema_name = self._current_schema.__name__

        if schema_name == "RawRoomObjects":
            prompt_text = str(input_data)
            room_type = _extract_room_type(prompt_text)
            data = _room_object_responses.get(room_type, _room_object_responses[_DEFAULT_ROOM])
            return self._current_schema.model_validate(data)

        if schema_name == "RawFloorObjectConstraints":
            prompt_text = str(input_data)
            room_type = _extract_room_type(prompt_text)
            data = _room_floor_constraints.get(room_type, _room_floor_constraints[_DEFAULT_ROOM])
            return self._current_schema.model_validate(data)

        if schema_name == "RawWallObjectConstraints":
            prompt_text = str(input_data)
            room_type = _extract_room_type(prompt_text)
            data = _room_wall_constraints.get(room_type, _room_wall_constraints[_DEFAULT_ROOM])
            return self._current_schema.model_validate(data)

        if schema_name not in _mock_responses:
            raise ValueError(f"No mock response defined for schema: {schema_name}")

        return self._current_schema.model_validate(_mock_responses[schema_name])

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager=None,
        **kwargs,
    ) -> ChatResult:
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=""))]
        )

    @property
    def _llm_type(self) -> str:
        return "mock_chat"
