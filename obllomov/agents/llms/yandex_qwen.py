# from obllomov.db.furniture_db import FURNITURE_DB
from typing import *

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage, BaseMessage, HumanMessage,SystemMessage
    )
from langchain_core.outputs import ChatGeneration, ChatResult

from openai import OpenAI

from pydantic import Field, model_validator

from .base import *

class ChatYandexQwen(BaseChatModel):
    api_key: str
    base_url: str
    project: str
    model_name: str

    max_new_tokens: int = MAX_NEW_TOKENS
    temperature: float = 0.3

    client: OpenAI = None
    
    @model_validator(mode='after')
    def initialize_model(self):
        if self.client is None:
            self._init_model()
        return self
    
    def _init_model(self):
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            project=self.project
        )
    
    def _generate(
            self,
            messages: List[BaseMessage],
            stop: Optional[List[str]] = None,
            run_manager: Optional[CallbackManagerForLLMRun] = None,
            **kwargs: Any,
        ) -> ChatResult:
        

        formatted_messages = format_messages(messages)

        response = self.client.chat.completions.create(
            model=f"gpt://{self.project}/{self.model_name}",
            messages=formatted_messages,
            max_tokens=self.max_new_tokens,
            temperature=self.temperature,
            stream=False,
        )

        return format_chat_result(response.choices[0].message.content)
    
    @property
    def _llm_type(self) -> str:
        return "yandex_qwen"
