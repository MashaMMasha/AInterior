# obllomov/agents/planners/base.py

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union

from colorama import Fore
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import BasePromptTemplate, PromptTemplate

from obllomov.shared.log import logger
from obllomov.storage.assets.base import BaseAssets


class BasePlanner(ABC):
    def __init__(self, llm: BaseChatModel, assets: BaseAssets = None):
        self.llm = llm

        if assets:
            self.assets = assets

        self.used_assets: list[str] = []

    @abstractmethod
    def plan(self, scene: Dict[str, Any], **kwargs) -> Any:
        pass

    def _raw_plan(
        self,
        scene: dict,
        prompt_template: str,
        cache_key: str | None = None,
        input_variables: Optional[Dict[str, Any]] = None,
        # system: Optional[str] = None,
        
        **kwargs
    ) -> str:
        prompt = PromptTemplate.from_template(prompt_template)

        if cache_key and cache_key in scene:
            response = scene[cache_key]
        else:
            chain = prompt | self.llm | StrOutputParser()
            response = chain.invoke(input_variables)
            
            if cache_key:
                scene[cache_key] = response
        
        self._log(response)
        # logger.info(f"{Fore.GREEN}{self.__class__.__name__} response:\n{response}{Fore.RESET}")


        return response
    

    def reset_used_assets(self) -> None:
        self.used_assets = []

    def _log(self, response, prefix: str | None = None):
        if prefix is None:
            # prefix = f"{self.__class__.__name__} response:"
            prefix = f"AI:"
        
        logger.info(f"{Fore.GREEN}{prefix}\n{response}{Fore.RESET}")
