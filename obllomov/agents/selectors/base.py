from abc import ABC, abstractmethod
from typing import *

import torch
import torch.functional as F
from colorama import Fore
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from pydantic import BaseModel

from obllomov.agents.base import BaseAgent
from obllomov.shared.log import logger
from obllomov.storage.assets.base import BaseAssets


class BaseSelector:
    def __init__(self):
        self.used_assets: list[str] = []

    @staticmethod
    def random_select(candidates):
        scores = torch.Tensor([c[1] for c in candidates])
        probas = F.softmax(scores, dim=0)
        idx = torch.multinomial(probas, 1).item()
        return candidates[idx]

    def reset_used_assets(self) -> None:
        self.used_assets = []
