from typing import Any, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from obllomov.agents.retrievers import ObjathorRetriever
from obllomov.agents.selectors import MaterialSelector
from obllomov.schemas.domain.annotations import AnnotationDict
from obllomov.schemas.domain.scene import ScenePlan
from obllomov.shared.log import logger


EDITOR_SYSTEM_PROMPT = """You are a scene editor for an interior design tool.
You have access to tools to inspect and modify a 3D room scene.
Use tools to understand the current scene state before making changes.
Always call get_room_details first to understand what you're working with.
When done editing, respond with a final summary of changes made."""


class SceneEditor:
    def __init__(
        self,
        llm: BaseChatModel,
        material_selector: MaterialSelector,
        object_retriever: ObjathorRetriever,
        annotations: AnnotationDict,
        max_steps: int = 10,
    ):
        self.llm = llm
        self.material_selector = material_selector
        self.object_retriever = object_retriever
        self.annotations = annotations
        self.max_steps = max_steps

    def edit(self, scene_plan: ScenePlan, user_request: str) -> ScenePlan:
        tools = self._build_tools(scene_plan)
        tool_map = {t.name: t for t in tools}
        llm_with_tools = self.llm.bind_tools(tools)

        messages = [
            SystemMessage(content=EDITOR_SYSTEM_PROMPT),
            HumanMessage(content=user_request),
        ]

        for step in range(self.max_steps):
            response: AIMessage = llm_with_tools.invoke(messages)
            messages.append(response)

            if not response.tool_calls:
                logger.info(f"Editor finished: {response.content}")
                break

            for call in response.tool_calls:
                logger.info(f"Editor tool call: {call['name']}({call['args']})")
                result = tool_map[call["name"]].invoke(call["args"])
                messages.append(
                    ToolMessage(content=str(result), tool_call_id=call["id"])
                )

        return scene_plan

    def _build_tools(self, scene_plan: ScenePlan) -> list:
        material_selector = self.material_selector
        object_retriever = self.object_retriever
        annotations = self.annotations

        @tool
        def get_room_details(room_id: str) -> str:
            """Get detailed information about a room: dimensions, materials, objects, doors, windows."""
            room = next((r for r in scene_plan.rooms if r.id == room_id), None)
            if room is None:
                available = [r.id for r in scene_plan.rooms]
                return f"Room '{room_id}' not found. Available rooms: {available}"

            from obllomov.shared.geometry import Polygon2D
            poly = Polygon2D(vertices=room.vertices)
            w, d = poly.bbox_size()

            desr = [
                f"Room: {room.room_type} ({room.id})",
                f"Size: {w:.1f}m x {d:.1f}m, wall height: {scene_plan.wall_height}m",
                f"Floor: material={room.floor_material.get('name', '?')}, design='{room.floor_design}'",
                f"Walls: material={room.wall_material.get('name', '?')}, design='{room.wall_design}'",
            ]

            room_objects = [
                obj for obj in scene_plan.floor_objects
                if obj.get("roomId") == room_id or obj.get("room_id") == room_id
            ]
            if room_objects:
                desr.append("Floor objects:")
                for obj in room_objects:
                    name = obj.get("object_name", obj.get("id", "?"))
                    pos = obj.get("position", {})
                    desr.append(f"  - {name} at ({pos.get('x', 0):.1f}, {pos.get('z', 0):.1f})")

            wall_objs = [
                obj for obj in scene_plan.wall_objects
                if obj.room_id == room_id
            ]
            if wall_objs:
                desr.append("Wall objects:")
                for obj in wall_objs:
                    desr.append(f"  - {obj.object_name} at height {obj.position.y:.1f}m")

            doors = [d for d in scene_plan.doors if d.room0 == room_id or d.room1 == room_id]
            if doors:
                desr.append("Doors:")
                for d in doors:
                    other = d.room1 if d.room0 == room_id else d.room0
                    desr.append(f"  - {d.asset_id} connecting to {other}")

            windows = [w for w in scene_plan.windows if w.room_id == room_id]
            if windows:
                desr.append("Windows:")
                for w in windows:
                    desr.append(f"  - {w.asset_id} on wall {w.wall0}")

            return "\n".join(desr)

        @tool
        def change_material(room_id: str, surface: str, description: str) -> str:
            """Change floor or wall material for a room.

            Args:
                room_id: The room to modify.
                surface: Either 'floor' or 'wall'.
                description: Natural language description of desired material, e.g. 'dark oak parquet' or 'beige matte wallpaper'.
            """
            room = next((r for r in scene_plan.rooms if r.id == room_id), None)
            if room is None:
                return f"Room '{room_id}' not found."
            if surface not in ("floor", "wall"):
                return "Surface must be 'floor' or 'wall'."

            material_selector.used_assets = []
            new_material = material_selector.select_single_material(description, topk=5)

            if surface == "floor":
                old = room.floor_material.get("name", "N/A")
                room.floor_material = new_material
                room.floor_design = description
            else:
                old = room.wall_material.get("name", "N/A")
                room.wall_material = new_material
                room.wall_design = description
                for wall in scene_plan.walls:
                    if wall.room_id == room_id and "exterior" not in wall.id:
                        wall.material = new_material

            return f"Changed {surface} material in {room_id}: '{old}' -> '{new_material['name']}' (query: '{description}')"

        @tool
        def find_object(description: str, top_k: int = 5) -> str:
            """Search for 3D objects by description. Returns top matching asset IDs with scores.

            Args:
                description: What to search for, e.g. 'modern floor lamp', 'wooden bookshelf'.
                top_k: Number of results to return.
            """
            uids, scores = object_retriever.retrieve_single(
                f"a 3D model of {description}",
                threshold=15,
                topk=top_k,
            )
            if not uids:
                return f"No objects found for '{description}'."

            answer = [f"Results for '{description}':"]
            for uid, score in zip(uids, scores):
                ann = annotations.get(uid)
                if ann:
                    bbox = ann.bbox
                    answer.append(
                        f"  - {uid} (score={score:.1f}, "
                        f"size={bbox.x:.2f}x{bbox.y:.2f}x{bbox.z:.2f}m)"
                    )
                else:
                    answer.append(f"  - {uid} (score={score:.1f})")
            return "\n".join(answer)

        return [get_room_details, change_material, find_object]
