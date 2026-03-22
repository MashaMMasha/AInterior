from abc import ABC, abstractmethod

import torch
from PIL import Image


class BaseRetriever(ABC):

    @abstractmethod
    def retrieve(
        self,
        queries: list[str],
        threshold: float | None = None,
        k: int | None = None,
    ) -> list[list[tuple[str, float]]]:
        ...

    def retrieve_single(
        self,
        query: str,
        threshold: float | None = None,
        k: int | None = None,
    ) -> list[tuple[str, float]]:
        return self.retrieve([query], threshold=threshold, k=k)[0]

    def retrieve_by_image(
        self,
        images: list[Image.Image],
        threshold: float | None = None,
        k: int | None = None,
    ) -> list[list[tuple[str, float]]]:
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support image queries"
        )

    def retrieve_by_image_single(
        self,
        image: Image.Image,
        threshold: float | None = None,
        k: int | None = None,
    ) -> list[tuple[str, float]]:
        return self.retrieve_by_image([image], threshold=threshold, k=k)[0]
    
    def score(
        self,
        queries: list[str],
    ) -> torch.Tensor:
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement score()"
        )
