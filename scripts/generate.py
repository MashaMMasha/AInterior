import argparse
import asyncio
from time import sleep

from obllomov.agents.llms import (ChatMock, get_chat_yandex_model, MAX_NEW_TOKENS)
from obllomov.services.obllomov import ObLLoMov
from obllomov.shared.env import env
from obllomov.shared.log import logger
from obllomov.shared.path import ABS_ROOT_PATH, OBJATHOR_ANNOTATIONS_PATH
from obllomov.storage.assets import LocalAssets, S3Assets
from obllomov.services.chat import ChatService
from obllomov.services.events import ChatEventCallback, LogEventCallback, CompositeEventCallback, RabbitMQEventCallback
from obllomov.storage.db.repository import SessionRepository
from obllomov.storage.db.engine import create_db_engine


from pydantic import BaseModel


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


assets = S3Assets(
    bucket_name=env.S3_BUCKET_NAME,
    key_prefix=env.S3_KEY_PREFIX,
    aws_access_key_id=env.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=env.AWS_SECRET_ACCESS_KEY,
    endpoint_url=env.S3_ENDPOINT_URL,
    region_name=env.AWS_DEFAULT_REGION,
)

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

interaction = chat.start_interaction(session_id, args.query)
callback = CompositeEventCallback([
    # LogEventCallback(),
    ChatEventCallback(chat, interaction.id),
])

generation_id = f"{session_id}-{interaction.id}"


# logger.info(f"generation_id: {generation_id}")
# sleep(5)
# async_callback = RabbitMQEventCallback(env.RABBITMQ_URL, generation_id)

asyncio.run(model.generate_scene(args.query, args.save_dir,
                                 callback=callback,
                                #  async_callback=async_callback,
                                 add_time=False
                                 ))


logger.info(f"generation_id: {generation_id}")
