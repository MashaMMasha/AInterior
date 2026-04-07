from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import numpy as np
import torch

from obllomov.agents.encoders import TextEncoder
from obllomov.storage.assets import BaseAssets
from obllomov.shared.log import logger


def load_features(assets: BaseAssets, feature_path: Path | str, feature_key: str | None = None) -> torch.Tensor:
    raw = assets.read_pickle(feature_path)

    match raw:
        case torch.Tensor():
            return raw
        case np.ndarray():
            return torch.from_numpy(raw.astype(np.float32))
        case dict() if feature_key is not None:
            return torch.from_numpy(raw[feature_key].astype(np.float32))
        case _:
            raise TypeError(f"Unsupported feature format: {type(raw)}")



class BaseRetriever(ABC):
    @abstractmethod
    def retrieve(self, queries: list[str], topk: int = 5, threshold: float | None = None) -> tuple[list[list[Any]], torch.Tensor]:
        ...

    def retrieve_single(self, query: str, topk: int = 5, threshold: float | None = None) -> tuple[list[Any], torch.Tensor]:
        items, scores = self.retrieve([query], topk, threshold)
        return items[0], scores[0]
    
    @staticmethod
    def get_top_k(
        scores: torch.Tensor,
        items: list,
        topk: int = 5,
        mask: torch.Tensor | None = None,
    ) -> tuple[list[list[Any]], torch.Tensor]:
        if mask is not None:
            masked_scores = scores.masked_fill(~mask, -1.0)
            top_scores, indices = masked_scores.topk(topk)
            # indices &= mask
            # top_scores = top_scores[indices]
        else:
            top_scores, indices = scores.topk(topk)

        logger.debug(f"indices: {indices} dim {indices.dim()}")
        # if indices.dim() < 2:
        #     indices = indices.unsqueeze(0)
        #     logger.debug(f"indices.unsqueeze: {indices} dim {indices.dim()}")
        top_items = [[items[i] for i in ind] for ind in indices]
        return top_items, top_scores



