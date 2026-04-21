
import torch
from PIL import Image

from .base import BaseEncoder, ImageEncoder, TextEncoder


class CLIPEncoder(TextEncoder, ImageEncoder):
    def __init__(self, clip_model, clip_tokenizer, clip_preprocess):
        self.clip_model = clip_model
        self.clip_tokenizer = clip_tokenizer
        self.clip_preprocess = clip_preprocess

    @torch.no_grad()
    def encode_text(self, texts: list[str], normalize: bool =True) -> torch.Tensor:
        tokens = self.clip_tokenizer(texts)
        features = self.clip_model.encode_text(tokens)

        return self._conditionally_normalize(features, normalize)


    @torch.no_grad()
    def encode_images(self, images: list[Image.Image], normalize=True) -> torch.Tensor:
        processed = torch.stack([self.clip_preprocess(img) for img in images])
        features = self.clip_model.encode_image(processed)

        return self._conditionally_normalize(features, normalize)
