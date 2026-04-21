from abc import ABC, abstractmethod
from typing import *

from langchain_core.language_models import BaseChatModel

from obllomov.agents.base import BaseAgent
from obllomov.storage.assets.base import BaseAssets


class BasePlanner(BaseAgent, ABC):
    def __init__(self, llm: BaseChatModel, assets: BaseAssets | None = None):
        super().__init__(llm)

        self.assets = assets
        self.used_assets: list[str] = []


    def reset_used_assets(self) -> None:
        self.used_assets = []
