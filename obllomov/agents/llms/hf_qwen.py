# from obllomov.db.furniture_db import FURNITURE_DB
from typing import *

import torch
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage, BaseMessage, HumanMessage,SystemMessage
    )
from langchain_core.outputs import ChatGeneration, ChatResult

from openai import OpenAI

# from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint

# from langchain_core.prompts import ChatPromptTemplate
from pydantic import Field, model_validator
from transformers import AutoModelForCausalLM, AutoTokenizer
import os

from obllomov.shared.log import logger

from .base import *



class ChatHFQwen(BaseChatModel):
    model_path: str
    tokenizer: AutoModelForCausalLM = Field(default=None, exclude=True)
    model: AutoTokenizer = Field(default=None, exclude=True)
    max_new_tokens: int = MAX_NEW_TOKENS

    @model_validator(mode='after')
    def initialize_model(self):
        if self.tokenizer is None or self.model is None:
            self._init_model()
        return self
    
    def _init_model(self):
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_path,
            # hf_token=HF_TOKEN
        )

        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_path,
            dtype=torch.float16,
            device_map="auto",
            attn_implementation="sdpa",
            # hf_token=HF_TOKEN
        )
        self.model.to("mps")
    
    def _generate(
            self,
            messages: List[BaseMessage],
            stop: Optional[List[str]] = None,
            run_manager: Optional[CallbackManagerForLLMRun] = None,
            **kwargs: Any,
        ) -> ChatResult:

        formatted_messages = format_messages(messages)
        
        prompt = self.tokenizer.apply_chat_template(
            formatted_messages,
            tokenize=False,
            add_generation_prompt=False
        )

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)

        generation_params = {
            "cache_implementation":"static",
            "max_new_tokens":self.max_new_tokens,
        }

        with torch.no_grad():
            outputs = self.model.generate(**inputs, **generation_params)

        content = self.tokenizer.decode(
            outputs[0][inputs['input_ids'].shape[1]:], 
            skip_special_tokens=True
        )

        return format_chat_result(content)
    
    @property
    def _llm_type(self) -> str:
        return "qwen"
