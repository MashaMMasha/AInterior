import argparse
import os

import compress_json
import open_clip

from obllomov.agents.llms import ChatMock, ChatYandexQwen

from langchain_openai import ChatOpenAI
from obllomov.services.obllomov import ObLLoMov
from obllomov.shared.env import env
from obllomov.shared.log import logger
from obllomov.shared.path import ABS_ROOT_PATH
from obllomov.storage.assets import LocalAssets, S3Assets


from obllomov.agents.llms import get_chat_yandex_model
logger.info("Parsing args")

parser = argparse.ArgumentParser()
parser.add_argument("--query", type=str, required=True)
parser.add_argument("--save-dir", type=str, required=True, dest="save_dir")
args = parser.parse_args()


logger.info("Init model")

llm = get_chat_yandex_model(
    temperature=0.3,
    max_completion_tokens=2048
    )


assets = LocalAssets()

model = ObLLoMov(llm, assets)

scene = model.get_empty_scene()

logger.info("Start generating")
model.generate_scene(scene, args.query, args.save_dir, add_time=False)
