from abc import ABC, abstractmethod


class BaseSelector(ABC):

    def __init__(self):
        self.used_assets: list[str] = []

    # @abstractmethod
    # def select(self, queries: list[str], **kwargs) -> list[str]:
    #     ...

    def reset_used_assets(self) -> None:
        self.used_assets = []
