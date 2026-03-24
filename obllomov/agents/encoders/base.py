from abc import ABC, abstractmethod
from typing import *

import torch
import torch.nn.functional as F
from PIL import Image


class BaseEncoder(ABC):
    @abstractmethod
    @torch.no_grad()
    def encode(self, items: list[Any], normalize=True) -> torch.Tensor:
        ...

    @abstractmethod
    def precompute_features(self, items: list[Any], normalize=True) -> torch.Tensor:
        ...

    def _normalize(self, features:  torch.Tensor) -> torch.Tensor:
        return F.normalize(features.float(), p=2, dim=-1)
    


class TextEncoder(BaseEncoder):
    @abstractmethod
    @torch.no_grad()
    def encode(self, texts: list[str], normalize=True) -> torch.Tensor:
        ...

    @abstractmethod
    def precompute_features(self, texts: list[str]) -> torch.Tensor:
        ...


class ImageEncoder(BaseEncoder):
    @abstractmethod
    @torch.no_grad()
    def encode(self, images: list[Image.Image], normalize=True) -> torch.Tensor:
        ...

    @abstractmethod
    def precompute_features(self, images: list[Image.Image]) -> torch.Tensor:
        ...
