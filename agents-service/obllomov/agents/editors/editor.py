from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from obllomov.agents.editors.tools import EditorToolkit
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
        toolkit: EditorToolkit,
        max_steps: int = 10,
    ):
        self.llm = llm
        self.toolkit = toolkit
        self.max_steps = max_steps

    def edit(self, scene_plan: ScenePlan, user_request: str) -> ScenePlan:
        tools = self.toolkit.build(scene_plan)
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
