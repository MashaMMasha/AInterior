from abc import ABC, abstractmethod


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
