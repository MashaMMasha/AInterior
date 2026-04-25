from obllomov.agents.llms import ChatMock, get_chat_yandex_model
from obllomov.agents.selectors.materials import MaterialSelector
from obllomov.schemas.domain.raw import RawWindowEntry 
from obllomov.agents.base import BaseAgent
from obllomov.agents.editors import SceneEditor, EditorToolkit
from obllomov.shared.path import HOLODECK_THOR_ANNOTATIONS_PATH, OBJATHOR_ANNOTATIONS_PATH
from obllomov.storage.annotations import load_annotations
from obllomov.storage.assets.local import LocalAssets

from pydantic_mermaid import MermaidGenerator

from  obllomov.schemas.domain.scene import ScenePlan

import objsize

from langchain.agents import create_agent

scene_plan= ScenePlan()

# ms = MaterialSelector()
# toolkit = EditorToolkit(None, None, None)

tools = toolkit.build(scene_plan)



generator = MermaidGenerator(raw)

chart = generator.generate_chart()

print(chart)

with open("raw_scene_plan.md", "w") as f:
    f.write(chart)
