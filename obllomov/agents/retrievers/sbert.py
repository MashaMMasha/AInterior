from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from obllomov.storage.assets.base import BaseAssets

from .base import BaseRetriever


class SBERTRetriever(BaseRetriever):

    def __init__(
        self,
        sbert_model,
        asset_ids: list[str],
        features: torch.Tensor | None = None,
        # assets: BaseAssets,
    ):
        self.sbert_model = sbert_model
        self.asset_ids = asset_ids

        self.features = features.float()
        # self.assets = assets

    # @classmethod
    # def from_pkl(
    #     cls,
    #     sbert_model,
    #     asset_ids: list[str],
    #     features_path: Path | str,
    #     assets: BaseAssets,
    # ) -> "SBERTRetriever":
    #     raw = assets.read_pickle(features_path)
    #     if isinstance(raw, dict):
    #         features = torch.from_numpy(raw["text_features"].astype("float32"))
    #     else:
    #         features = raw

    #     return cls(sbert_model, asset_ids, features, assets)
    
    def load_features(self, assets: BaseAssets, features_path: Path | str, 
                      features_key=None, 
                      features_id="uids",
                      append=True):
        raw = assets.read_pickle(features_path)

        match raw:
            case torch.Tensor():
                features = raw
            case np.ndarray():
                features =  torch.from_numpy(raw.astype("float32"))
            case dict() if features_key is not None:
                features =  torch.from_numpy(raw[features_key].astype("float32"))
            case _:
                raise TypeError()
        
        if self.features is None or not append:
            self.features = features
        else:
            self.features = torch.cat(
                [self.features, features],
                axis=0
            )

        self.features_id = ...

    def retrieve(
        self,
        queries: list[str],
        threshold: float | None = None,
        k: int | None = None,
    ) -> list[list[tuple[str, float]]]:
        query_scores = self.score(queries)

        return [
            self._rank(score_row, threshold, k)
            for score_row in query_scores
        ]
    
    def score(self, queries: list[str]) -> torch.Tensor:
        query_features = self.encode(queries)

        self.features = self._normalize(self.features)

        return query_features @ self.features.T  # [Q, N]
    
    def _normalize(self, features: torch.Tensor):
        return F.normalize(features.float(), p=2, dim=-1)

    @torch.inference_mode()
    def encode(self, queries: list[str], normalize=True) -> torch.Tensor:
        features = self.sbert_model.encode(
            queries,
            convert_to_tensor=True,
            show_progress_bar=False,
        )

        if normalize:
            return self._normalize(features)

        return features

    def _rank(
        self,
        score_row: torch.Tensor,
        threshold: float | None,
        k: int | None,
    ) -> list[tuple[str, float]]:
        if threshold is not None:
            indices = (score_row > threshold).nonzero(as_tuple=True)[0]
        else:
            indices = torch.arange(len(score_row), device=score_row.device)

        if len(indices) == 0:
            return []

        order = torch.argsort(score_row[indices], descending=True)
        sorted_indices = indices[order]

        if k is not None:
            sorted_indices = sorted_indices[:k]

        return [
            (self.asset_ids[idx.item()], score_row[idx].item())
            for idx in sorted_indices
        ]
    

