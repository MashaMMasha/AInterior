import argparse
import os

import compress_json
import open_clip
from langchain_openai import ChatOpenAI

from obllomov.agents.llms import (ChatMock, ChatYandexQwen,
                                  get_chat_yandex_model, MAX_NEW_TOKENS)
from obllomov.services.obllomov import ObLLoMov
from obllomov.shared.env import env
from obllomov.shared.log import logger
from obllomov.shared.path import ABS_ROOT_PATH, OBJATHOR_ANNOTATIONS_PATH
from obllomov.storage.assets import LocalAssets, S3Assets

logger.info("Parsing args")

parser = argparse.ArgumentParser()
parser.add_argument("--query", type=str, required=True)
parser.add_argument("--save-dir", type=str, required=True, dest="save_dir")
parser.add_argument("--mock", action='store_true')
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

scene = model.get_empty_scene()

# logger.info("Start generating")
model.generate_scene(scene, args.query, args.save_dir, add_time=False)
