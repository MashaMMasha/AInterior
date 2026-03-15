from typing import Any, List, Optional

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult

import obllomov.agents.prompts as prompts

from .base import format_chat_result

PROMPT_SIGNATURES: dict[str, str] = {
    "floor_plan":              "crafting a floor plan",
    "wall_height":             "decide the wall height in meters",
    "doorway":                 "connections between rooms",
    "window":                  "guide me in designing the windows",
    "object_selection":        "large, floor-based objects to furnish",
    "object_constraints":      "assigning constraints to each object",
    "wall_object_selection":   "selecting wall-based objects",
    "wall_object_constraints": "arrange wall objects in the room",
    "ceiling_selection":       "selecting ceiling objects",
    "small_object_selection":  "placing more *small* objects",
    "object_selection_new":    "selecting large *floor*/*wall* objects",
    "floor_baseline":          "you operate in a 2d space",
}

MOCK_RESPONSES: dict[str, str] = {
    "floor_plan": (
        "living room | oak hardwood, matte | light grey drywall, smooth | [(0, 0), (0, 8), (6, 8), (6, 0)]\n"
        "bedroom | walnut laminate, warm | pale blue paint, smooth | [(6, 2), (6, 6), (9, 6), (9, 2)]\n"
        "kitchen | white hex tile, glossy | light grey drywall, smooth | [(6, 0), (6, 2), (9, 2), (9, 0)]"
    ),

    "wall_height": "3.0",

    "doorway": (
        "exterior | living room | doorway | single | wooden door with white frames\n"
        "living room | bedroom | open | N/A | N/A\n"
        "living room | kitchen | doorway | single | wooden door with white frames"
    ),

    "window": (
        "living room | west | fixed | (150, 120) | 2 | 90\n"
        "bedroom | east | hung | (96, 91) | 1 | 80\n"
        "kitchen | south | slider | (120, 91) | 1 | 90"
    ),

    "object_selection": (
        "living room | sofa | modern sectional, light grey sofa | 1\n"
        "living room | coffee table | rectangular wooden coffee table | 1\n"
        "living room | floor lamp | black tripod floor lamp | 2\n"
        "living room | tv stand | modern white tv stand | 1\n"
        "living room | armchair | beige fabric armchair | 2\n"
        "bedroom | bed | queen size bed, white frame | 1\n"
        "bedroom | wardrobe | white sliding door wardrobe | 1\n"
        "bedroom | nightstand | wooden nightstand | 2\n"
        "bedroom | desk | white study desk | 1\n"
        "bedroom | desk chair | ergonomic office chair | 1\n"
        "kitchen | fridge | stainless steel refrigerator | 1\n"
        "kitchen | dining table | round wooden dining table | 1\n"
        "kitchen | dining chair | wooden dining chair | 4"
    ),

    "object_constraints": (
        "sofa-0 | edge\n"
        "coffee table-0 | middle | near, sofa-0 | in front of, sofa-0 | center aligned, sofa-0 | face to, sofa-0\n"
        "tv stand-0 | edge | far, sofa-0 | center aligned, sofa-0 | face to, coffee table-0\n"
        "floor lamp-0 | edge | near, sofa-0 | side of, sofa-0\n"
        "floor lamp-1 | edge | near, tv stand-0 | side of, tv stand-0\n"
        "armchair-0 | middle | around, coffee table-0 | near, coffee table-0 | face to, coffee table-0\n"
        "armchair-1 | middle | around, coffee table-0 | near, coffee table-0 | face to, coffee table-0"
    ),

    "wall_object_selection": (
        "living room | painting | abstract landscape painting | 2\n"
        "living room | clock | round modern wall clock | 1\n"
        "bedroom | mirror | rectangular frameless wall mirror | 1\n"
        "bedroom | painting | calm nature painting | 1\n"
        "kitchen | cabinet | white shaker-style wall cabinet | 2"
    ),

    "wall_object_constraints": (
        "painting-0 | above, sofa-0 | 160\n"
        "painting-1 | above, tv stand-0 | 160\n"
        "clock-0 | N/A | 150\n"
        "mirror-0 | N/A | 120\n"
        "cabinet-0 | N/A | 140\n"
        "cabinet-1 | N/A | 140"
    ),

    "ceiling_selection": (
        "living room | modern 3-light semi-flush mount ceiling light\n"
        "bedroom | minimalist flush mount ceiling light\n"
        "kitchen | industrial style pendant ceiling light"
    ),

    "small_object_selection": (
        "sofa-0 (living room) | decorative pillow, 3, varied | remote control, 1, same\n"
        "coffee table-0 (living room) | coffee mug, 2, varied | book, 3, varied | small plant, 1, same\n"
        "tv stand-0 (living room) | 55 inch TV, 1, same | speaker, 2, same\n"
        "nightstand-0 (bedroom) | alarm clock, 1, same | table lamp, 1, same | book, 1, varied\n"
        "desk-0 (bedroom) | laptop, 1, same | desk lamp, 1, same | notebook, 2, varied"
    ),

    "object_selection_new": """\
Here is my high-level design strategy: place large anchor pieces first, then accent objects.

{
    "sofa": {
        "description": "modern sectional light grey sofa",
        "location": "floor",
        "size": [220, 90, 80],
        "quantity": 1,
        "variance_type": "same",
        "objects_on_top": [
            {"object_name": "decorative pillow", "quantity": 3, "variance_type": "varied"},
            {"object_name": "remote control", "quantity": 1, "variance_type": "same"}
        ]
    },
    "coffee table": {
        "description": "rectangular glass top coffee table",
        "location": "floor",
        "size": [120, 60, 45],
        "quantity": 1,
        "variance_type": "same",
        "objects_on_top": [
            {"object_name": "coffee mug", "quantity": 2, "variance_type": "varied"},
            {"object_name": "book", "quantity": 2, "variance_type": "varied"}
        ]
    },
    "tv stand": {
        "description": "modern white tv stand with shelves",
        "location": "floor",
        "size": [180, 45, 50],
        "quantity": 1,
        "variance_type": "same",
        "objects_on_top": [
            {"object_name": "55 inch tv", "quantity": 1, "variance_type": "same"},
            {"object_name": "speaker", "quantity": 2, "variance_type": "same"}
        ]
    },
    "floor lamp": {
        "description": "black tripod floor lamp with white shade",
        "location": "floor",
        "size": [40, 40, 160],
        "quantity": 2,
        "variance_type": "same",
        "objects_on_top": []
    },
    "armchair": {
        "description": "beige fabric armchair",
        "location": "floor",
        "size": [85, 85, 90],
        "quantity": 2,
        "variance_type": "same",
        "objects_on_top": []
    },
    "painting": {
        "description": "abstract colorful painting",
        "location": "wall",
        "size": [100, 5, 80],
        "quantity": 2,
        "variance_type": "varied",
        "objects_on_top": []
    },
    "wall clock": {
        "description": "round minimalist wall clock",
        "location": "wall",
        "size": [40, 5, 40],
        "quantity": 1,
        "variance_type": "same",
        "objects_on_top": []
    }
}""",

    "floor_baseline": """\
```json
[
    {"object_name": "sofa-0",        "position": {"X": 300, "Y": 100}, "rotation": 0},
    {"object_name": "coffee table-0","position": {"X": 300, "Y": 220}, "rotation": 0},
    {"object_name": "tv stand-0",    "position": {"X": 300, "Y": 500}, "rotation": 180},
    {"object_name": "floor lamp-0",  "position": {"X": 100, "Y": 100}, "rotation": 0},
    {"object_name": "floor lamp-1",  "position": {"X": 500, "Y": 100}, "rotation": 0},
    {"object_name": "armchair-0",    "position": {"X": 100, "Y": 260}, "rotation": 90},
    {"object_name": "armchair-1",    "position": {"X": 500, "Y": 260}, "rotation": 270}
]
```""",
}


class ChatMock(BaseChatModel):
    def _detect_prompt_type(self, content: str) -> str:
        content_lower = content.lower()
        for prompt_type, signature in PROMPT_SIGNATURES.items():
            if signature.lower() in content_lower:
                return prompt_type
        return "floor_plan"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        full_content = " ".join(msg.content for msg in messages)
        prompt_type = self._detect_prompt_type(full_content)
        return format_chat_result(MOCK_RESPONSES[prompt_type])

    @property
    def _llm_type(self) -> str:
        return "mock_chat"
