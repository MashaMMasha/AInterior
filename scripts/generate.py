import argparse
import os

import compress_json
import open_clip
from langchain_openai import ChatOpenAI

from obllomov.agents.llms import (ChatMock, get_chat_yandex_model, MAX_NEW_TOKENS)
from obllomov.services.obllomov import ObLLoMov
from obllomov.shared.env import env
from obllomov.shared.log import logger
from obllomov.shared.path import ABS_ROOT_PATH, OBJATHOR_ANNOTATIONS_PATH
from obllomov.storage.assets import LocalAssets, S3Assets
from obllomov.services.chat import ChatService
from obllomov.storage.db.repository import SessionRepository
from obllomov.storage.db.engine import create_db_engine


from pydantic import BaseModel

# class ThorMetadata(BaseModel):

# class Annotation(BaseModel):
#     uid: str
#     description: str
#     description_auto: str
#     scale: str
#     category: str
#     category_max_scale: float
#     category_min_scale: float

logger.info("Parsing args")

parser = argparse.ArgumentParser()
parser.add_argument("--query", type=str, required=True)
parser.add_argument("--save-dir", type=str, required=True, dest="save_dir")
parser.add_argument("--mock", action='store_true')
parser.add_argument("--session-id", type=str, default=None, dest="session_id")
args = parser.parse_args()


logger.info("Init model")

if args.mock:
    logger.info("Mocking llm model")
    llm = ChatMock()
else:
    llm = get_chat_yandex_model(
        temperature=0.3,
        max_completion_tokens=MAX_NEW_TOKENS
        )

# llm = ChatMock()


assets = LocalAssets()

model = ObLLoMov(llm, assets)
engine = create_db_engine()
chat = ChatService(SessionRepository(engine))

session_id = args.session_id
if session_id:
    logger.info(f"Using existing session: {session_id}")
else:
    session = chat.start_session(user_id="terbium")
    session_id = session.id
    logger.info(f"Created new session: {session_id}")

model.generate_scene(args.query, args.save_dir,
                     chat=chat,
                     session_id=session_id,
                     add_time=False
                     )
