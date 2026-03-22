from pathlib import Path

import torch

from obllomov.storage.assets.base import BaseAssets

from .base import BaseRetriever
from .clip import CLIPRetriever
from .sbert import SBERTRetriever


class ObjathorRetriever(BaseRetriever):

    def __init__(
        self,
        clip_retriever: CLIPRetriever,
        sbert_retriever: SBERTRetriever,
        annotations: dict,
        retrieval_threshold: float = 28.0,
        clip_weight: float = 1.0,
        sbert_weight: float = 1.0,
    ):
        self.clip_retriever = clip_retriever
        self.sbert_retriever = sbert_retriever
        self.annotations = annotations
        self.retrieval_threshold = retrieval_threshold
        self.clip_weight = clip_weight
        self.sbert_weight = sbert_weight


        assert self.clip_retriever.asset_ids == self.sbert_retriever.asset_ids, \
            "CLIP and SBERT assets must have the same asset_ids"

        self.asset_ids = self.clip_retriever.asset_ids

    def retrieve(
        self,
        queries: list[str],
        threshold: float | None = None,
        k: int | None = None,
    ) -> list[list[tuple[str, float]]]:
        threshold = threshold if threshold is not None else self.retrieval_threshold

        clip_scores   = self.clip_retriever.score(queries)    # [Q, N]
        sbert_scores  = self.sbert_retriever.score(queries)   # [Q, N]

        combined  = self.clip_weight * clip_scores + self.sbert_weight * sbert_scores
        clip_mask = clip_scores > threshold                   

        results = []
        for q_idx in range(len(queries)):
            valid_indices = clip_mask[q_idx].nonzero(as_tuple=True)[0]

            if len(valid_indices) == 0:
                results.append([])
                continue

            scores = combined[q_idx][valid_indices]
            order  = torch.argsort(scores, descending=True)
            sorted_indices = valid_indices[order]

            if k is not None:
                sorted_indices = sorted_indices[:k]

            results.append([
                (self.asset_ids[idx.item()], combined[q_idx][idx].item())
                for idx in sorted_indices
            ])

        return results
