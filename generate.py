from obllomov.services.obllomov import ObLLoMov
from obllomov.shared.log import logger
from obllomov.shared.env import env
from obllomov.agents.llms import ChatYandexQwen
import argparse

logger.info("Parsing args")

parser = argparse.ArgumentParser()
parser.add_argument("--query", type=str, required=True)
parser.add_argument("--save-dir", type=str, required=True, dest="save_dir")
args = parser.parse_args()


logger.info("Init model")

llm = ChatYandexQwen(
    api_key=env.YANDEX_CLOUD_API_KEY,
    base_url="https://ai.api.cloud.yandex.net/v1",
    project=env.YANDEX_CLOUD_FOLDER,
    model_name=env.YANDEX_CLOUD_MODEL
)

model = ObLLoMov(llm)

scene = model.get_empty_scene()

logger.info("Start generating")
model.generate_scene(scene, args.query, args.save_dir, add_time=False)
