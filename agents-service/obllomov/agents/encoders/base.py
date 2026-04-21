from abc import ABC, abstractmethod
from typing import *

import torch
import torch.nn.functional as F
from PIL import Image


class BaseEncoder(ABC):
    def _conditionally_normalize(self, raw_features: torch.Tensor, normalize: bool):
        if normalize:
            return self._normalize(raw_features)
        return raw_features
    
    def _normalize(self, features:  torch.Tensor) -> torch.Tensor:
        return F.normalize(features.float(), p=2, dim=-1)
    


class TextEncoder(BaseEncoder):
    @abstractmethod
    @torch.no_grad()
    def encode_text(self, texts: list[str], normalize=True) -> torch.Tensor:
        ...

class ImageEncoder(BaseEncoder):
    @abstractmethod
    @torch.no_grad()
    def encode_images(self, images: list[Image.Image], normalize=True) -> torch.Tensor:
        ...
