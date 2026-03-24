
from langchain_openai import ChatOpenAI

from obllomov.shared.env import env


def get_chat_yandex_model(**kwargs):
    model = f"gpt://{env.YANDEX_CLOUD_FOLDER}/{env.YANDEX_CLOUD_MODEL}"

    return ChatOpenAI(
        model=model,         
        api_key=env.YANDEX_CLOUD_API_KEY,
        base_url="https://ai.api.cloud.yandex.net/v1",
        **kwargs,
        # temperature=0.3,
        # max_completion_tokens=2048
    )
