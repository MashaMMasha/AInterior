from typing import Any, Dict, List, Optional, Type
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from pydantic import BaseModel
import json


_mock_responses = {
    "RawRoomPlan": {
        "room_type": "living_room",
        "floor_design": "light_oak_parquet",
        "wall_design": "white_eggshell_paint",
        "vertices": [[0.0, 0.0], [8.0, 0.0], [8.0, 6.0], [0.0, 6.0]]
    },
    "RawFloorPlan": {
        
  "rooms": [
    {
      "room_type": "living_room",
      "floor_design": "light_oak_parquet",
      "wall_design": "white_eggshell_paint",
      "vertices": [
        {
          "x": 0.0,
          "z": 0.0
        },
        {
          "x": 6.0,
          "z": 0.0
        },
        {
          "x": 6.0,
          "z": 5.0
        },
        {
          "x": 0.0,
          "z": 5.0
        }
      ]
    },
    {
      "room_type": "bedroom",
      "floor_design": "warm_gray_laminate",
      "wall_design": "soft_blue_matte_paint",
      "vertices": [
        {
          "x": 6.0,
          "z": 1.0
        },
        {
          "x": 8.0,
          "z": 1.0
        },
        {
          "x": 8.0,
          "z": 4.0
        },
        {
          "x": 6.0,
          "z": 4.0
        }
      ]
    },
    {
      "room_type": "kitchen",
      "floor_design": "white_ceramic_tile",
      "wall_design": "light_gray_subway_tile",
      "vertices": [
        {
          "x": 0.0,
          "z": 5.0
        },
        {
          "x": 3.0,
          "z": 5.0
        },
        {
          "x": 3.0,
          "z": 7.0
        },
        {
          "x": 0.0,
          "z": 7.0
        }
      ]
    }
  ]

    },
    "RawWallPlan": {
        "wall_height": 2.7
    },
    "RawDoorPlan": {
        "doors": [
            {
            "room_type0": "exterior",
            "room_type1": "living_room",
            "connection_type": "doorway",
            "size": "double",
            "style": "dark brown wooden door"
            },
            {
            "room_type0": "living_room",
            "room_type1": "kitchen",
            "connection_type": "open",
            "size": "N/A",
            "style": "N/A"
            },
            {
            "room_type0": "living_room",
            "room_type1": "bedroom",
            "connection_type": "doorway",
            "size": "single",
            "style": "white wooden door"
            }
        ]
    },
    "RawWindowPlan":
    {
  "windows": [
    {
      "room_id": "living_room",
      "wall_direction": "south",
      "window_type": "fixed",
      "window_size": [
        240.0,
        180.0
      ],
      "quantity": 2,
      "window_height": 50.0
    },
    {
      "room_id": "bedroom",
      "wall_direction": "south",
      "window_type": "hung",
      "window_size": [
        120.0,
        160.0
      ],
      "quantity": 1,
      "window_height": 90.0
    },
    {
      "room_id": "kitchen",
      "wall_direction": "west",
      "window_type": "slider",
      "window_size": [
        150.0,
        120.0
      ],
      "quantity": 1,
      "window_height": 100.0
    }
  ]
}
}

class ChatMock(BaseChatModel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._current_schema = None

    def with_structured_output(self, schema: Type[BaseModel]) -> 'ChatMock':
        """Store the schema for later use."""
        self._current_schema = schema
        return self
    
    def invoke(self, input_data: Any, config, **kwargs) -> BaseModel:
        """
        Override invoke to return Pydantic model instead of AIMessage.
        This is what gets called when using chain.invoke().
        """
        if self._current_schema is None:
            raise ValueError("No schema set. Call with_structured_output first.")
        
        schema_name = self._current_schema.__name__
        if schema_name not in _mock_responses:
            raise ValueError(f"No mock response defined for schema: {schema_name}")
        
        # Возвращаем Pydantic модель, а не строку
        return self._current_schema.model_validate(_mock_responses[schema_name])
    
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager = None,
        **kwargs,
    ) -> ChatResult:
        """Fallback for when invoke is not used directly."""
        if self._current_schema is None:
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=""))])
        
        schema_name = self._current_schema.__name__
        if schema_name not in self._mock_responses:
            raise ValueError(f"No mock response defined for schema: {schema_name}")
        
        mock_data = self._mock_responses[schema_name]
        json_content = json.dumps(mock_data, indent=2, ensure_ascii=False)
        
        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(content=json_content)
                )
            ]
        )
    
    @property
    def _llm_type(self) -> str:
        return "mock_chat"
