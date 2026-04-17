import json
from typing import *

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableSerializable
from langchain_core.runnables.config import RunnableConfig
from openai import OpenAI
from pydantic import BaseModel, model_validator

from .base import *


class StructuredOutputRunnable(RunnableSerializable):
    llm: "ChatYandexQwen"
    _schema: Any

    model_config = {"arbitrary_types_allowed": True}

    def invoke(self, input: Any, config: Optional[RunnableConfig] = None, **kwargs) -> BaseModel:
        result: AIMessage = self.llm.invoke(input, config=config, **kwargs)
        return self._schema.model_validate_json(result.content)


class ChatYandexQwen(BaseChatModel):
    api_key: str
    base_url: str
    project: str
    model_name: str

    max_new_tokens: int = MAX_NEW_TOKENS
    temperature: float = 0.3

    client: Optional[Any] = None
    _structured_output_schema: Optional[type] = None

    model_config = {"arbitrary_types_allowed": True}

    @model_validator(mode='after')
    def initialize_model(self):
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            project=self.project,
        )
        return self

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
            response_format={"type": "json_object"} if self._structured_output_schema else None,
        )

        return format_chat_result(response.choices[0].message.content)

    def with_structured_output(self, schema: type[BaseModel], **kwargs: Any) -> StructuredOutputRunnable:
        clone = self.model_copy()
        clone._structured_output_schema = schema
        return StructuredOutputRunnable(llm=clone, _schema=schema)

    @property
    def _llm_type(self) -> str:
        return "yandex_qwen"
