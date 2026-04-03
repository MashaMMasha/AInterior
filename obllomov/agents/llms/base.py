from abc import ABC, abstractmethod
from typing import *

from colorama import Fore
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (AIMessage, BaseMessage, HumanMessage,
                                     SystemMessage)
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import BaseModel

from obllomov.shared.log import logger
from obllomov.storage.assets.base import BaseAssets

MAX_NEW_TOKENS=1024

FROM_LANGCHAIN_MSG_TYPE = {
    "ai": "assistant",
    "human": "user",
    "system":"system",
}


def format_messages(messages: List[BaseMessage]) -> List[Dict]:
    formatted_messages = []
    
    for message in messages:
        formatted_messages.append({
            "role": FROM_LANGCHAIN_MSG_TYPE.get(message.type, "user"), 
            "content": message.content
        })
    
    return formatted_messages


def format_chat_result(content: str):
    message = AIMessage(content=content)
    generation = ChatGeneration(message=message)

    logger.debug(generation.message.content)

    return ChatResult(generations=[generation])
