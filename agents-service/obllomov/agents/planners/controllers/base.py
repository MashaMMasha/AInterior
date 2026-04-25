from abc import ABC, abstractmethod
from typing import List, Optional

from obllomov.schemas.domain.scene import ScenePlan


class BaseObjectController(ABC):
    @abstractmethod
    def start(self, scene_plan: ScenePlan) -> List[str]:
        pass

    @abstractmethod
    def place_object(self, asset_id: str, receptacle_id: str, rotation: list) -> Optional[dict]:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass
