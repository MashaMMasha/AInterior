# from obllomov.db.furniture_db import FURNITURE_DB
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import LLM, BaseChatModel
from langchain_core.messages import (
    AIMessage, BaseMessage, HumanMessage,SystemMessage
    )
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate

from pydantic import Field, model_validator

from typing import *

from obllomov.shared.log import logger

# MODEL_PATH="obllomov/models/qwen-7b-instruct"

MAX_NEW_TOKENS=2048


class ChatQwen(BaseChatModel):
    model_path: str
    tokenizer: AutoModelForCausalLM = Field(default=None, exclude=True)
    model: AutoTokenizer = Field(default=None, exclude=True)

    @model_validator(mode='after')
    def initialize_model(self):
        if self.tokenizer is None or self.model is None:
            self._init_model()
        return self
    
    def _init_model(self):
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_path
        )

        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_path,
            dtype=torch.float16,
            device_map="auto",
            attn_implementation="sdpa"
        )

    def _convert_messages_to_prompt(self, messages: List[BaseMessage]) -> str:
        formatted_messages = []
        
        for message in messages:
            logger.debug(message.type)

            if isinstance(message, SystemMessage):
                role = "system"
            elif isinstance(message, HumanMessage):
                role = "user"
            elif isinstance(message, AIMessage):
                role = "assistant"
            else:
                role = "user"
            
            formatted_messages.append({"role": role, "content": message.content})    

        prompt = self.tokenizer.apply_chat_template(
                formatted_messages,
                tokenize=False,
                add_generation_prompt=True
            )
        
        return prompt
    
    def _generate(
            self,
            messages: List[BaseMessage],
            stop: Optional[List[str]] = None,
            run_manager: Optional[CallbackManagerForLLMRun] = None,
            **kwargs: Any,
        ) -> ChatResult:
        
        prompt = self._convert_messages_to_prompt(messages)

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)

        generation_params = {
            "cache_implementation":"static",
            "max_new_tokens":MAX_NEW_TOKENS,
        }

        with torch.no_grad():
            outputs = self.model.generate(**inputs, **generation_params)

        text = self.tokenizer.decode(
            outputs[0][inputs['input_ids'].shape[1]:], 
            skip_special_tokens=True
        )
        
        message = AIMessage(content=text.strip())
        generation = ChatGeneration(message=message)

        return ChatResult(generations=[generation])
    
    # def parse_request()
    
    @property
    def _llm_type(self) -> str:
        return "qwen"


# llm = ChatQwen(model_path=MODEL_PATH)

# messages = [
#     SystemMessage(content="Ты полезный ассистент."),
#     HumanMessage(content="Кратко представься.")
# ]

# prompt = ChatPromptTemplate.from_messages([
#     ("system", "Ты эксперт по программированию."),
#     ("user", "{question}")
# ])

# chain = prompt | llm


# response = chain.invoke({
#     "question": "Кратко представься.",
# })

# logger.debug(response)
# print(response.content)
