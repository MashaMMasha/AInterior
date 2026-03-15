import argparse

from obllomov.agents.llms import ChatMock, ChatYandexQwen
from obllomov.services.obllomov import ObLLoMov
from obllomov.shared.env import env
from obllomov.shared.log import logger
from obllomov.storage.assets import LocalAssets, S3Assets

logger.info("Parsing args")

parser = argparse.ArgumentParser()
parser.add_argument("--query", type=str, required=True)
parser.add_argument("--save-dir", type=str, required=True, dest="save_dir")
args = parser.parse_args()


logger.info("Init model")

# llm = ChatYandexQwen(
#     api_key=env.YANDEX_CLOUD_API_KEY,
#     base_url="https://ai.api.cloud.yandex.net/v1",
#     project=env.YANDEX_CLOUD_FOLDER,
#     model_name=env.YANDEX_CLOUD_MODEL
# )

llm = ChatMock()

assets = S3Assets()

model = ObLLoMov(llm, assets)

scene = model.get_empty_scene()

logger.info("Start generating")
model.generate_scene(scene, args.query, args.save_dir, add_time=False)
