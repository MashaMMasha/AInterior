
import torch

from .base import BaseEncoder, TextEncoder


class SBERTEncoder(TextEncoder):
    def __init__(self, sbert_model):
        self.sbert_model = sbert_model

    @torch.no_grad()
    def encode(self, texts: list[str], normalize=True) -> torch.Tensor:
        features =  self.sbert_model.encode(texts, convert_to_tensor=True, show_progress_bar=False)

        if normalize:
            return self._normalize(features)
        return features
