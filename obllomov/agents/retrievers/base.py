from abc import ABC, abstractmethod

import torch
from PIL import Image

from obllomov.agents.encoders import BaseEncoder


class BaseRetriever:
    def __init__(self, encoder: BaseEncoder, features: torch.Tensor, items: list[str], scale: float = 100.0):
        self.encoder = encoder
        self.features = features
        self.items = items
        self.scale = scale

    # encoder: BaseEncoder
    # features: torch.Tensor
    # items: list

    # scale: float = 100.0


    def _get_top_k(self, features_score, topk=5):
        results, scores = [], []
        for score in features_score:
            indices = torch.argsort(score, descending=True)[:topk]

            results.append([self.items[ind] for ind in indices])
            scores.append([score[ind].item() for ind in indices])

        return results, scores


    def retrieve(self, queries: list[str], topk: int = 5) -> tuple[list[list[str]], list[list[float]]]:
        features = self.encoder.encode(queries)
        scores = self.score(features)

        return self._get_top_k(scores, self.items, topk)

    def score(self, featrues: torch.Tensor) -> torch.Tensor:
        return self.scale * (featrues @ self.features.T)


# class DenseRetriever(BaseRetriever):
#     def __init__(self, encoder: BaseEncoder, features: torch.Tensor, items: list[str], score_scale: float = 100.0):
#         super().__init__(encoder, features, items, score_scale)


#     def score(self, featrues: torch.Tensor) -> torch.Tensor:
#         return self.scale * (featrues @ self.features.T)
    

class ObjectRetriever(BaseRetriever):
    def __init__(self, encoder: BaseEncoder, features: torch.Tensor, items: list[str], score_scale: float = 100.0):
        super().__init__(encoder, features, items, score_scale)

    def score(self, featrues: torch.Tensor) -> torch.Tensor:
        scores = self.scale * torch.einsum("ij, lkj -> ilk", featrues, self.features)
        return torch.max(scores, dim=-1).values  # Возвращает [N, M]
    


    

    
    


    
# class BaseRetriever(ABC):
#     @abstractmethod
#     def retrieve(
#         self,
#         queries: list[str],
#         threshold: float | None = None,
#         k: int | None = None,
#     ) -> list[list[tuple[str, float]]]:
#         ...

#     def retrieve_single(
#         self,
#         query: str,
#         threshold: float | None = None,
#         k: int | None = None,
#     ) -> list[tuple[str, float]]:
#         return self.retrieve([query], threshold=threshold, k=k)[0]

#     def retrieve_by_image(
#         self,
#         images: list[Image.Image],
#         threshold: float | None = None,
#         k: int | None = None,
#     ) -> list[list[tuple[str, float]]]:
#         raise NotImplementedError(
#             f"{self.__class__.__name__} does not support image queries"
#         )

#     def retrieve_by_image_single(
#         self,
#         image: Image.Image,
#         threshold: float | None = None,
#         k: int | None = None,
#     ) -> list[tuple[str, float]]:
#         return self.retrieve_by_image([image], threshold=threshold, k=k)[0]
    
#     def score(
#         self,
#         queries: list[str],
#     ) -> torch.Tensor:
#         raise NotImplementedError(
#             f"{self.__class__.__name__} does not implement score()"
#         )
