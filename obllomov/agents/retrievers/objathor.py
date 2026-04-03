from pathlib import Path

import numpy as np
import torch

from obllomov.agents.encoders import TextEncoder
from obllomov.storage.assets import BaseAssets

from .base import BaseRetriever
from .item import ItemRetriever
from .object import ObjectRetriever


class ObjathorRetriever(BaseRetriever):
    def __init__(
        self,
        clip_retriever: ObjectRetriever,
        sbert_retriever: ItemRetriever,
        database: dict | None = None,
        retrieval_threshold: float = 28.0,
        clip_weight: float = 1.0,
        sbert_weight: float = 1.0,
    ):
        self.clip_retriever = clip_retriever
        self.sbert_retriever = sbert_retriever
        self.database = database or {}
        self.retrieval_threshold = retrieval_threshold
        self.clip_weight = clip_weight
        self.sbert_weight = sbert_weight

        assert self.clip_retriever.items == self.sbert_retriever.items, \
            "CLIP and SBERT retrievers must have the same items"

    @classmethod
    def from_assets(
        cls,
        assets: BaseAssets,
        clip_encoder: TextEncoder,
        sbert_encoder: TextEncoder,
        sources: list[dict],
        **kwargs,
    ) -> "ObjathorRetriever":
        """Load features from multiple sources and build a combined retriever.

        Each source dict should have:
            - annotations_path: path to annotations json
            - features_dir: path to directory with clip_features.pkl and sbert_features.pkl
        """
        all_uids = []
        all_clip_features = []
        all_sbert_features = []
        database = {}

        for src in sources:
            annotations = assets.read_json(src["annotations_path"])
            database.update(annotations)

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
            database=database,
            **kwargs,
        )

    @property
    def items(self) -> list:
        return self.clip_retriever.items

    def retrieve(
        self,
        queries: list[str],
        topk: int = 5,
        retrieval_threshold: float | None = None,
    ) -> tuple[list[list[str]], torch.Tensor]:
        threshold = retrieval_threshold or self.retrieval_threshold

        clip_features = self.clip_retriever.encoder.encode_text(queries)
        sbert_features = self.sbert_retriever.encoder.encode_text(queries)

        clip_scores = self.clip_retriever.score(clip_features)
        sbert_scores = self.sbert_retriever.score(sbert_features)

        combined = self.clip_weight * clip_scores + self.sbert_weight * sbert_scores
        clip_mask = clip_scores > threshold

        return self.get_top_k(combined, self.items, topk, clip_mask)
