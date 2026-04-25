import argparse
import asyncio
from time import sleep

from obllomov.agents.llms import (ChatMock, get_chat_yandex_model, MAX_NEW_TOKENS)
from obllomov.services.obllomov import ObLLoMov
from obllomov.agents.editors import SceneEditor
from obllomov.shared.env import env
from obllomov.shared.log import logger
from obllomov.shared.path import ABS_ROOT_PATH, OBJATHOR_ANNOTATIONS_PATH
from obllomov.storage.assets import LocalAssets, S3Assets
from obllomov.services.chat import ChatService
from obllomov.services.events import ChatEventCallback, LogEventCallback, CompositeEventCallback, RabbitMQEventCallback
from obllomov.storage.db.repository import SessionRepository
from obllomov.storage.db.engine import create_db_engine
from obllomov.schemas.domain.scene import ScenePlan


from pydantic import BaseModel


logger.info("Parsing args")

parser = argparse.ArgumentParser()
parser.add_argument("--query", type=str, required=True)
parser.add_argument("--session-id", type=str, default=None, dest="session_id")
args = parser.parse_args()

session_id = args.session_id

engine = create_db_engine()
chat = ChatService(SessionRepository(engine))
scene_plan_json = chat.get_last_scene_json(session_id)
scene_plan = ScenePlan.from_json(scene_plan_json)

interaction = chat.start_interaction(session_id, f"Edit request: {args.query}")

llm = get_chat_yandex_model()

assets = LocalAssets()

callback = ChatEventCallback(chat, interaction.id)

model = ObLLoMov(llm, assets)

model.edit_scene(args.query, session_id, scene_plan, callback)

