from pathlib import Path

import numpy as np
import torch

from obllomov.agents.encoders import TextEncoder
from obllomov.schemas.domain.annotations import Annotation
from obllomov.shared.path import NORMALIZED_ANNOTATIONS_PATH
from obllomov.shared.log import logger
from obllomov.storage.assets import BaseAssets

from .base import BaseRetriever
from .item import ItemRetriever
from .object import ObjectRetriever



class ObjathorRetriever(BaseRetriever):
    def __init__(
        self,
        clip_retriever: ObjectRetriever,
        sbert_retriever: ItemRetriever,
        items: list[str],
        retrieval_threshold: float = 28.0,
        clip_weight: float = 1.0,
        sbert_weight: float = 1.0,
    ):
        self.clip_retriever = clip_retriever
        self.sbert_retriever = sbert_retriever
        self.items = items
        self.retrieval_threshold = retrieval_threshold
        self.clip_weight = clip_weight
        self.sbert_weight = sbert_weight

        assert self.clip_retriever.items == self.sbert_retriever.items == self.items, \
            "CLIP and SBERT retrievers must have the same items"

    #TODO: better items flow handling perchance
    @classmethod
    def from_assets(
        cls,
        assets: BaseAssets,
        clip_encoder: TextEncoder,
        sbert_encoder: TextEncoder,
        sources: list[dict],
        items: list[str],
        **kwargs,
    ) -> "ObjathorRetriever":
        all_uids = []
        all_clip_features = []
        all_sbert_features = []

        for src in sources:
            clip_data = assets.read_pickle(Path(src["features_dir"]) / "clip_features.pkl")
            sbert_data = assets.read_pickle(Path(src["features_dir"]) / "sbert_features.pkl")
            assert clip_data["uids"] == sbert_data["uids"], \
                f"UID mismatch in {src['features_dir']}"

            all_uids.extend(clip_data["uids"])
            all_clip_features.append(clip_data["img_features"].astype(np.float32))
            all_sbert_features.append(sbert_data["text_features"].astype(np.float32))

        clip_features = torch.from_numpy(np.concatenate(all_clip_features))
        sbert_features = torch.from_numpy(np.concatenate(all_sbert_features))

        clip_retriever = ObjectRetriever(
            encoder=clip_encoder, features=clip_features, items=all_uids,
        )
        sbert_retriever = ItemRetriever(
            encoder=sbert_encoder, features=sbert_features, items=all_uids,
        )

        return cls(
            clip_retriever=clip_retriever,
            sbert_retriever=sbert_retriever,
            items=items,
            **kwargs,
        )

    # @property
    # def items(self) -> list:
    #     return self.clip_retriever.items

    def retrieve(
        self,
        queries: list[str],
        topk: int = 5,
        threshold: float | None = None,
    ) -> tuple[list[list[str]], torch.Tensor]:
        retrieval_threshold = threshold or self.retrieval_threshold

        clip_features = self.clip_retriever.encoder.encode_text(queries)
        sbert_features = self.sbert_retriever.encoder.encode_text(queries)

        clip_scores = self.clip_retriever.score(clip_features)
        sbert_scores = self.sbert_retriever.score(sbert_features)

        combined = self.clip_weight * clip_scores + self.sbert_weight * sbert_scores
        clip_mask = clip_scores > retrieval_threshold

        logger.debug(f"combined: {combined}")

        return self.get_top_k(combined, self.items, topk, clip_mask)
