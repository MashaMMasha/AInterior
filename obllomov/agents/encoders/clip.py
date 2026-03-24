
import torch
from PIL import Image

from .base import BaseEncoder, ImageEncoder, TextEncoder


class CLIPTextEncoder(TextEncoder):
    def __init__(self, clip_model, clip_tokenizer):
        self.clip_model = clip_model
        self.clip_tokenizer = clip_tokenizer

    @torch.no_grad()
    def encode(self, texts: list[str], normalize=True) -> torch.Tensor:
        tokens = self.clip_tokenizer(texts)
        features = self.clip_model.encode_text(tokens)

        if normalize:
            return self._normalize(features)
        return features


class CLIPImageEncoder(ImageEncoder):
    def __init__(self, clip_model, clip_preprocess):
        self.clip_model = clip_model
        self.clip_preprocess = clip_preprocess

    @torch.no_grad()
    def encode(self, images: list[Image.Image], normalize=True) -> torch.Tensor:
        processed = torch.stack([self.clip_preprocess(img) for img in images])
        features = self.clip_model.encode_image(processed)

        if normalize:
            return self._normalize(features)
        return features
