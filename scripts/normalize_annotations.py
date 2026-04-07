import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from obllomov.shared.path import (
    OBJATHOR_ANNOTATIONS_PATH,
    HOLODECK_THOR_ANNOTATIONS_PATH,
)
from obllomov.storage.assets import LocalAssets, BaseAssets
from obllomov.schemas.domain.annotations import Annotation
from typing import Dict


NORMALIZED_PATH = Path("annotations_normalized.json.gz")


def load_annotations(assets: BaseAssets, sources: list[str]) -> Dict[str, Annotation]:
    annotations = {}

    for src in sources:
        raw_data = assets.read_json(src)
        print(f"{src}: {len(raw_data)} entries")
        for uid, entry in raw_data.items():
            annotations[uid] = normalize_entry(uid, entry)


def normalize_entry(uid: str, raw: dict) -> dict:
    bb = raw["thor_metadata"]["assetMetadata"]["boundingBox"]
    return {
        "uid": uid,
        "category": raw["category"],
        "onFloor": bool(raw.get("onFloor")),
        "onObject": bool(raw.get("onObject")),
        "onWall": bool(raw.get("onWall")),
        "onCeiling": bool(raw.get("onCeiling")),
        "bbox": {
            "x": bb["max"]["x"] - bb["min"]["x"],
            "y": bb["max"]["y"] - bb["min"]["y"],
            "z": bb["max"]["z"] - bb["min"]["z"],
        },
        "secondary_properties": raw["thor_metadata"]["assetMetadata"].get("secondaryProperties", []),
    }


def main():
    assets = LocalAssets()

    sources = [OBJATHOR_ANNOTATIONS_PATH, HOLODECK_THOR_ANNOTATIONS_PATH]
    normalized = {}

    for src in sources:
        raw_data = assets.read_json(src)
        print(f"{src}: {len(raw_data)} entries")
        for uid, entry in raw_data.items():
            normalized[uid] = normalize_entry(uid, entry)

    print(f"Total: {len(normalized)} entries")

    assets.write_json(NORMALIZED_PATH, normalized)
    print(f"Written to {NORMALIZED_PATH}")


if __name__ == "__main__":
    main()
