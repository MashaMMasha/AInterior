from typing import ClassVar, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from obllomov.shared.geometry import Polygon2D, Segment2D, Vertex2D, Vertex3D





class RoomPlan(BaseModel):
    room_type: str
    floor_design: str
    wall_design: str
    vertices: List[Vertex2D]

    id: str
    floor_polygon: List[Vertex3D]
    full_vertices: List[Vertex2D]
    floor_material: dict
    wall_material: dict


class FloorPlan(BaseModel):
    rooms: List[RoomPlan]


class WallConnection(BaseModel):
    room_id: Optional[str] = None
    wall_id: Optional[str] = None
    intersection: List[Vertex3D]
    line0: List[Vertex3D]
    line1: List[Vertex3D]

class WallEntry(BaseModel):
    id: str
    room_id: str
    material: dict
    polygon: List[Vertex3D]
    connected_rooms: List[WallConnection]
    width: float
    height: float
    direction: Optional[str]
    segment: Segment2D

class OpenWalls(BaseModel):
    segments: list[Segment2D]
    boxes: list

class WallPlan(BaseModel):
    wall_height: float
    walls: List[WallEntry]


class DoorEntry(BaseModel):
    asset_id: str
    id: str
    openable: bool
    openness: int
    room0: str
    room1: str
    wall0: str
    wall1: str
    hole_polygon: List[Vertex3D]
    asset_position: Vertex3D
    door_boxes: list
    door_segment: Segment2D


class DoorPlan(BaseModel):
    doors: List[DoorEntry]
    room_pairs: list
    open_room_pairs: List[Tuple[str, str]]

class WindowEntry(BaseModel):
    asset_id: str
    id: str
    room0: str
    room1: str
    wall0: str
    wall1: str
    room_id: str
    hole_polygon: List[Vertex3D]
    asset_position: Vertex3D
    window_segment: Segment2D
    window_boxes: list


class WindowPlan(BaseModel):
    windows: List[WindowEntry]
    walls: list[WallEntry]


class WallObjectEntry(BaseModel):
    asset_id: str
    id: str
    kinematic: bool = True
    position: Vertex3D
    rotation: Vertex3D
    material: Optional[str] = None
    room_id: str
    vertices: list
    object_name: str


class WallObjectPlan(BaseModel):
    wall_objects: List[WallObjectEntry]

class SmallObjectEntry(BaseModel):
    asset_id: str
    id: str
    kinematic: bool
    position: Vertex3D
    rotation: Vertex3D
    material: Optional[str] = None
    room_id: str


class SmallObjectPlan(BaseModel):
    small_objects: List[SmallObjectEntry]
    receptacle2small_objects: dict

class CeilingObjectEntry(BaseModel):
    asset_id: str
    id: str
    kinematic: bool = True
    position: Vertex3D
    rotation: Vertex3D
    material: Optional[str] = None
    room_id: str
    object_name: str


class CeilingPlan(BaseModel):
    ceiling_objects: List[CeilingObjectEntry]
