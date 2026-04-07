from pathlib import Path

from obllomov.storage.assets import BaseAssets
from obllomov.schemas.domain.annotations import Annotation, AnnotationDict
from typing import Dict


NORMALIZED_PATH = Path("annotations_normalized.json.gz")


def load_annotations(assets: BaseAssets, sources: list[str]) -> AnnotationDict:
    annotations: AnnotationDict = {}

    for src in sources:
        raw_data = assets.read_json(src)

        for uid, entry in raw_data.items():
            annotations[uid] = _get_annotation(uid, entry)

    return annotations


def _get_annotation(uid: str, raw: dict) -> Annotation:
    bb = raw["thor_metadata"]["assetMetadata"]["boundingBox"]
    return Annotation(
        uid=uid,
        category=raw["category"],
        onFloor= bool(raw.get("onFloor")),
        onObject= bool(raw.get("onObject")),
        onWall= bool(raw.get("onWall")),
        onCeiling= bool(raw.get("onCeiling")),
        bbox= {
            "x": bb["max"]["x"] - bb["min"]["x"],
            "y": bb["max"]["y"] - bb["min"]["y"],
            "z": bb["max"]["z"] - bb["min"]["z"],
        },
        secondary_properties= raw["thor_metadata"]["assetMetadata"].get("secondaryProperties", []),
    )

