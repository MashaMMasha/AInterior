import io
from pathlib import Path
from typing import Any, Dict

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from tqdm import tqdm

from obllomov.storage.assets.base import BaseAssets

from .base import BaseRetriever


class CLIPRetriever(BaseRetriever):

    def __init__(
        self,
        clip_model,
        clip_tokenizer,
        clip_preprocess,
        asset_ids: list[str],
        features: torch.Tensor,
        assets: BaseAssets,
        similarity_scale: float = 100.0,
    ):
        self.clip_model = clip_model
        self.clip_tokenizer = clip_tokenizer
        self.clip_preprocess = clip_preprocess
        self.asset_ids = asset_ids
        self.features = F.normalize(features.float(), p=2, dim=-1)
        self.assets = assets
        self.similarity_scale = similarity_scale

    @classmethod
    def from_images(
        cls,
        clip_model,
        clip_tokenizer,
        clip_preprocess,
        asset_ids: list[str],
        image_dir: Path,
        assets: BaseAssets,
        cache_path: Path | str | None = None,
        similarity_scale: float = 100.0,
    ) -> "CLIPRetriever":
        if cache_path is not None and assets.exists(cache_path):
            features = assets.read_pickle(cache_path)
            return 
        else:
            features = cls._precompute_image_features(
                clip_model, clip_preprocess, asset_ids, image_dir, assets
            )
            if cache_path is not None:
                assets.write_pickle(cache_path, features)

        return cls(
            clip_model, clip_tokenizer, clip_preprocess,
            asset_ids, features, assets, similarity_scale,
        )

    @classmethod
    def from_texts(
        cls,
        clip_model,
        clip_tokenizer,
        clip_preprocess,
        labels: list[str],
        assets: BaseAssets,
        cache_path: Path | str | None = None,
        similarity_scale: float = 100.0,
    ) -> "CLIPRetriever":
        if cache_path is not None and assets.exists(cache_path):
            features = assets.read_pickle(cache_path)
        else:
            features = cls._precompute_text_features(clip_model, clip_tokenizer, labels)
            if cache_path is not None:
                assets.write_pickle(cache_path, features)

        return cls(
            clip_model, clip_tokenizer, clip_preprocess,
            labels, features, assets, similarity_scale,
        )

    def load_features(self, assets: BaseAssets, features_path: Path | str, features_key=None, append=True):
        raw = assets.read_pickle(features_path)

        match raw:
            case torch.Tensor():
                features = raw
            case np.array():
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

    


    @classmethod
    def from_pkl(
        cls,
        clip_model,
        clip_tokenizer,
        clip_preprocess,
        asset_ids: list[str],
        features_path: Path | str,
        assets: BaseAssets,
        similarity_scale: float = 100.0,
    ) -> "CLIPRetriever":
        raw = assets.read_pickle(features_path)

        if isinstance(raw, dict):
            features = torch.from_numpy(raw["img_features"].astype("float32"))
        else:
            features = raw

        return cls(
            clip_model, clip_tokenizer, clip_preprocess,
            asset_ids, features, assets, similarity_scale,
        )

    def retrieve(
        self,
        queries: list[str],
        threshold: float | None = None,
        k: int | None = None,
    ) -> list[list[tuple[str, float]]]:
        query_scores = self.score(queries)

        return [
            self._rank(score, threshold, k)
            for score in query_scores
        ]


    def retrieve_by_image(
        self,
        images: list[Image.Image],
        threshold: float | None = None,
        k: int | None = None,
    ) -> list[list[tuple[str, float]]]:
        image_scores = self._encode_images(images)
        
        return [
            self._rank(score, threshold, k)
            for score in image_scores
        ]
    
    def score(self, queries: list[str]) -> torch.Tensor:
        query_features = self._encode_text(queries)
        return self._score(query_features)
    
    def score_by_image(self, images: list[Image.Image]) -> torch.Tensor:
        image_features = self._encode_images(images)
        return self._score(image_features)
    
    def _score(self, featrues: torch.Tensor) -> torch.Tensor:
        return self.similarity_scale * (featrues @ self.features.T)


    def _encode_text(self, queries: list[str]) -> torch.Tensor:
        with torch.no_grad():
            features = self.clip_model.encode_text(self.clip_tokenizer(queries))
        return F.normalize(features.float(), p=2, dim=-1)

    def _encode_images(self, images: list[Image.Image]) -> torch.Tensor:
        batch = torch.stack([self.clip_preprocess(img) for img in images])
        with torch.no_grad():
            features = self.clip_model.encode_image(batch)
        return F.normalize(features.float(), p=2, dim=-1)
    
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


    @staticmethod
    def _precompute_image_features(
        clip_model,
        clip_preprocess,
        asset_ids: list[str],
        image_dir: Path,
        assets: BaseAssets,
    ) -> torch.Tensor:
        feature_list = []
        for asset_id in tqdm(asset_ids, desc="Precomputing image features"):
            img_path = image_dir / f"{asset_id}.png"
            img_bytes = assets.read_bytes(img_path)
            image = clip_preprocess(
                Image.open(io.BytesIO(img_bytes))
            ).unsqueeze(0)
            with torch.no_grad():
                feat = clip_model.encode_image(image)
                feat = F.normalize(feat.float(), p=2, dim=-1)
            feature_list.append(feat)
        return torch.vstack(feature_list)

    @staticmethod
    def _precompute_text_features(
        clip_model,
        clip_tokenizer,
        labels: list[str],
    ) -> torch.Tensor:
        with torch.no_grad():
            features = clip_model.encode_text(clip_tokenizer(labels))
        return F.normalize(features.float(), p=2, dim=-1)
    


