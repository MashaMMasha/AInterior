from obllomov.services.obllomov import ObLLoMov
from obllomov.shared.log import logger
from obllomov.agents.llms import ChatYandexQwen

from os import getenv


logger.info("Init model")

llm = ChatYandexQwen(
    api_key=getenv("YANDEX_CLOUD_API_KEY"),
    base_url="https://ai.api.cloud.yandex.net/v1",
    project=getenv("YANDEX_CLOUD_FOLDER"),
    model_name=getenv("YANDEX_CLOUD_MODEL")
)

model = ObLLoMov(llm)

scene = model.get_empty_scene()


logger.info("Start generating")
model.generate_scene(scene, "A lightful living room, small bedroom and tiny kitchen", "/Users/terbium/VSCodeProjects/AInterior/AInterior/scenes")
