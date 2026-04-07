from pydantic import BaseModel

from obllomov.shared.geometry import BBox3D
from typing import Dict


class Annotation(BaseModel):
    uid: str
    category: str
    onFloor: bool
    onObject: bool
    onWall: bool
    onCeiling: bool
    bbox: BBox3D
    secondary_properties: list[str]

AnnotationDict = Dict[str, Annotation]
