import random
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Set

from ai2thor.controller import Controller
from ai2thor.hooks.procedural_asset_hook import ProceduralAssetHookRunner
from procthor.constants import FLOOR_Y
from procthor.utils.types import Vector3

from obllomov.schemas.domain.scene import ScenePlan
from obllomov.shared.log import logger
from obllomov.shared.path import OBJATHOR_ASSETS_DIR
from obllomov.shared.utils import THOR_COMMIT_ID
from obllomov.storage.assets import BaseAssets


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


def _collect_asset_ids(scene_plan: ScenePlan) -> Set[str]:
    asset_ids: Set[str] = set()

    for obj in scene_plan.objects:
        asset_ids.add(obj.asset_id)
    for entry in scene_plan.doors:
        asset_ids.add(entry.asset_id)
    for entry in scene_plan.windows:
        asset_ids.add(entry.asset_id)
    
    asset_ids.discard("")
    return asset_ids


class AI2thorObjectController(BaseObjectController):
    def __init__(self, assets: BaseAssets):
        self.assets = assets
        self.controller: Optional[Controller] = None
        self._tmp_dir: Optional[Path] = None

    def _ensure_asset(self, asset_id: str) -> bool:
        if self._tmp_dir is None:
            return False
        target = self._tmp_dir / asset_id
        if target.exists():
            return True
        try:
            local = self.assets.get_local_dir(OBJATHOR_ASSETS_DIR / asset_id)
        except (FileNotFoundError, Exception):
            logger.debug(f"Asset not found: {asset_id}")
            return False
        target.symlink_to(local)
        return True

    def start(self, scene_plan: ScenePlan) -> List[str]:
        thor_scene = scene_plan.to_thor_scene()
        logger.debug(f"thor_scene objects count: {len(thor_scene.get('objects', []))}")
        # logger.debug(f"thor_scene object ids: {[o.get('id') for o in thor_scene.get('objects', [])]}")

        asset_ids = _collect_asset_ids(scene_plan)
        logger.debug(f"Preparing {len(asset_ids)} scene assets")
        self._tmp_dir = self.assets.prepare_local_dir(OBJATHOR_ASSETS_DIR, asset_ids)

        self.controller = Controller(
            commit_id=THOR_COMMIT_ID,
            agentMode="default",
            makeAgentsVisible=False,
            visibilityDistance=1.5,
            scene=thor_scene,
            width=224,
            height=224,
            fieldOfView=40,
            action_hook_runner=ProceduralAssetHookRunner(
                asset_directory=str(self._tmp_dir),
                asset_symlink=True,
                verbose=True,
            ),
        )
        event = self.controller.reset()
        assert event.metadata.get('lastActionSuccess'), logger.debug(f"thor reset error: {event.metadata.get('errorMessage')}")

        scene_object_ids = {obj.id for obj in scene_plan.floor_objects}
        logger.debug(f"scene_object_ids: {scene_object_ids}")
        return [
            obj["objectId"]
            for obj in event.metadata["objects"]
            if obj["objectId"] in scene_object_ids and "___" not in obj["objectId"]
        ]

    def place_object(self, asset_id: str, receptacle_id: str, rotation: list) -> Optional[dict]:
        if not self._ensure_asset(asset_id):
            return None
        generated_id = f"small|{asset_id}"
        spawn_event = self.controller.step(
            action="SpawnAsset",
            assetId=asset_id,
            generatedId=generated_id,
            position=Vector3(x=0, y=FLOOR_Y - 20, z=0),
            rotation=Vector3(x=0, y=0, z=0),
            renderImage=False,
        )
        if not spawn_event.metadata.get("lastActionSuccess"):
            logger.debug(f"  SpawnAsset failed: {asset_id} -> {spawn_event.metadata.get('errorMessage')}")
            return None
        event = self.controller.step(
            action="InitialRandomSpawn",
            randomSeed=random.randint(0, 1_000_000_000),
            objectIds=[generated_id],
            receptacleObjectIds=[receptacle_id],
            forceVisible=False,
            allowFloor=False,
            renderImage=False,
            allowMoveable=True,
            numPlacementAttempts=10,
        )
        if not event.metadata.get("lastActionSuccess"):
            logger.debug(f"  InitialRandomSpawn failed: {asset_id} on {receptacle_id} -> {event.metadata.get('errorMessage')}")
        obj = next((o for o in event.metadata["objects"] if o["objectId"] == generated_id), None)
        if obj is None:
            logger.debug(f"  object not found: {generated_id}")
            return None
        center_y = obj["axisAlignedBoundingBox"]["center"]["y"]
        logger.debug(f"  {asset_id} center_y={center_y:.3f} FLOOR_Y={FLOOR_Y}")
        if event and center_y > FLOOR_Y:
            return obj
        self.controller.step(action="DisableObject", objectId=generated_id, renderImage=False)
        return None

    def stop(self) -> None:
        if self.controller:
            self.controller.stop()
            self.controller = None
        if self._tmp_dir and self._tmp_dir.exists():
            shutil.rmtree(self._tmp_dir, ignore_errors=True)
            self._tmp_dir = None
