from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import numpy as np
import torch

from obllomov.agents.encoders import TextEncoder
from obllomov.storage.assets import BaseAssets

from .base import BaseRetriever, load_features


class ObjectRetriever(BaseRetriever):
    def __init__(self, encoder: TextEncoder, features: torch.Tensor, items: list[str], scale: float = 100.0):
        self.encoder = encoder
        self.features = features
        self.items = items
        self.scale = scale

    @classmethod
    def from_assets(
        cls,
        assets: BaseAssets,
        feature_path: Path | str,
        feature_key: str | None = None,
        **kwargs,
    ) -> "ObjectRetriever":
        features = load_features(assets, feature_path, feature_key)
        return cls(features=features, **kwargs)

    def score(self, features: torch.Tensor) -> torch.Tensor:
        scores = self.scale * torch.einsum("ij, lkj -> ilk", features, self.features)
        return torch.max(scores, dim=-1).values

    def retrieve(self, queries: list[str], topk: int = 5) -> tuple[list[list[str]], torch.Tensor]:
        features = self.encoder.encode_text(queries)
        scores = self.score(features)
        return self.get_top_k(scores, self.items, topk)
