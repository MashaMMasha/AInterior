# obllomov/agents/planners/base.py

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import BasePromptTemplate

from obllomov.storage.assets.base import BaseAssets
from obllomov.shared.log import logger


class BasePlanner(ABC):
    def __init__(self, llm: BaseChatModel, assets: BaseAssets) -> None:
        self.llm         = llm
        self.assets      = assets
        self.used_assets: list[str] = []

    @abstractmethod
    def plan(self, scene: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        pass

    def _raw_plan(
        self,
        prompt: BasePromptTemplate,
        variables: Optional[Dict[str, Any]] = None,
        system: Optional[str] = None,
    ) -> str:
        
        chain = prompt | self.llm
        response = chain.invoke(input=variables)
        result   = response.content

        logger.debug(f"{self.__class__.__name__} response:\n{result}")

        return result
    

    def reset_used_assets(self) -> None:
        self.used_assets = []
