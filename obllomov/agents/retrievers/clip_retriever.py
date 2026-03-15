import torch
import torch.nn.functional as F
import compress_pickle

from .base import BaseRetriever


class CLIPRetriever(BaseRetriever):
    def __init__(
        self,
        clip_model,
        clip_tokenizer,
        asset_ids: list[str],
        features: torch.Tensor,
        similarity_scale: float = 1.0,
    ):
        self.clip_model = clip_model
        self.clip_tokenizer = clip_tokenizer
        self.asset_ids = asset_ids
        # нормализуем один раз при инициализации
        self.features = F.normalize(features.float(), p=2, dim=-1)
        self.similarity_scale = similarity_scale

    @classmethod
    def from_pkl(
        cls,
        clip_model,
        clip_tokenizer,
        asset_ids: list[str],
        features_path: str,
        similarity_scale: float = 1.0,
    ) -> "CLIPRetriever":
        raw = compress_pickle.load(features_path)
        if isinstance(raw, dict):
            features = torch.from_numpy(raw["img_features"])
        else:
            features = raw
        return cls(clip_model, clip_tokenizer, asset_ids, features, similarity_scale)

    def _encode_queries(self, queries: list[str]) -> torch.Tensor:
        with torch.no_grad():
            features = self.clip_model.encode_text(self.clip_tokenizer(queries))
        return F.normalize(features.float(), p=2, dim=-1)

    def retrieve(
        self,
        queries: list[str],
        threshold: float | None = None,
        k: int | None = None,
    ) -> list[list[tuple[str, float]]]:
        query_features = self._encode_queries(queries)
        # [Q, N]
        similarities = self.similarity_scale * (query_features @ self.features.T)

        results = []
        for sim_row in similarities:
            pairs = self._rank(sim_row, threshold=threshold, k=k)
            results.append(pairs)
        return results

    def _rank(
        self,
        sim_row: torch.Tensor,
        threshold: float | None,
        k: int | None,
    ) -> list[tuple[str, float]]:
        if threshold is not None:
            indices = (sim_row > threshold).nonzero(as_tuple=True)[0]
        else:
            indices = torch.arange(len(sim_row))

        if len(indices) == 0:
            return []

        sorted_order = torch.argsort(sim_row[indices], descending=True)
        sorted_indices = indices[sorted_order]

        if k is not None:
            sorted_indices = sorted_indices[:k]

        return [
            (self.asset_ids[idx], sim_row[idx].item())
            for idx in sorted_indices
        ]
