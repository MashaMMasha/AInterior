from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field

from obllomov.shared.geometry import Polygon2D, Vertex2D, Vertex3D


class RawRoomPlan(BaseModel):
    room_type: str = Field(
        description="Type of the room, e.g. 'living room', 'bedroom'"
    )
    floor_design: str = Field(
        description="Floor material/design description, e.g. 'oak wood'"
    )
    wall_design: str = Field(
        description="Wall material/design description, e.g. 'white paint'"
    )
    vertices: List[Vertex2D] = Field(
        description=(
            "List of 2D vertices with x and z coordinates in meters defining the room polygon. "
            "Must be in clockwise order and form a rectilinear (all angles >= 90°) shape."
        )
    )

class RawFloorPlan(BaseModel):
    rooms: List[RawRoomPlan] = Field(description="List of rooms in the floor plan")


class RawWallPlan(BaseModel):
    wall_height: float = Field(description="Height of the walls in meters, between 2.0 and 4.5", ge=2.0, le=4.5)

class RawDoorEntry(BaseModel):
    room_type0: str = Field(description="First room type")
    room_type1: str = Field(description="Second room type, use 'exterior' for outside")
    connection_type: str = Field(description="One of: doorway, doorframe, open")
    size: str = Field(description="One of: single, double")
    style: str = Field(description="Style description, e.g. 'modern wooden'")


class RawDoorPlan(BaseModel):
    doors: List[RawDoorEntry] = Field(description="List of door connections between rooms")


class RawWindowEntry(BaseModel):
    room_id: str = Field(description="Room type id")
    wall_direction: str = Field(description="One of: north, south, east, west")
    window_type: str = Field(description="One of: fixed, hung, and slider")
    window_size: List[float] = Field(description="[width, height] in meters")
    quantity: int = Field(description="Number of windows on this wall")
    window_height: float = Field(description="Height from floor to bottom of window in cm")


class RawWindowPlan(BaseModel):
    windows: List[RawWindowEntry] = Field(description="List of windows per room wall")


class RawTopObjectEntry(BaseModel):
    object_name: str
    quantity: int = Field(default=1, ge=1)
    variance_type: Literal["same", "varied"] = "same"


class RawObjectEntry(BaseModel):
    description: str
    location: Literal["floor", "wall"] = "floor"
    size: Optional[List[int]] = Field(default=None, description="[x, y, z] in cm")
    quantity: int = Field(default=1, ge=1)
    variance_type: Literal["same", "varied"] = "same"
    objects_on_top: List[RawTopObjectEntry] = Field(default_factory=list)


class RawRoomObjects(BaseModel):
    objects: Dict[str, RawObjectEntry] = Field(
        description="Map of object name to object info. object name can be something like: 'sofa', 'floor lamp', 'fridge', etc. So keys in dictionary should be names of objects"
    )

class RawWallObjectConstraintEntry(BaseModel):
    object_name: str = Field(description="Wall object name")
    near_floor_object: Optional[str] = Field(
        description="Floor object it should be near, or null"
    )
    height: int = Field(description="Height from floor in cm")


class RawWallObjectConstraints(BaseModel):
    constraints: List[RawWallObjectConstraintEntry]


class RawCeilingEntry(BaseModel):
    room_type: str = Field(description="Room type")
    object_description: str = Field(
        description="Description of the ceiling object, e.g. 'modern LED panel light'"
    )


class RawCeilingPlan(BaseModel):
    ceiling_objects: List[RawCeilingEntry] = Field(
        description="List of ceiling objects per room"
    )


class RawFloorConstraint(BaseModel):
    type: str = Field(description="Constraint type: global, relative, direction, alignment, or distance")
    constraint: str = Field(description="Constraint name: edge, middle, near, far, in front of, behind, left of, right of, side of, around, face to, center aligned")
    target: Optional[str] = Field(default=None, description="Target object name for non-global constraints")


class RawFloorObjectConstraintEntry(BaseModel):
    object_name: str = Field(description="Object name, e.g. 'sofa-0'")
    constraints: List[RawFloorConstraint]


class RawFloorObjectConstraints(BaseModel):
    entries: List[RawFloorObjectConstraintEntry]


class RawScenePlan(BaseModel):
    raw_floor_plan: Optional[RawFloorPlan] = None
    raw_wall_plan: Optional[RawWallPlan] = None
    raw_door_plan: Optional[RawDoorPlan] = None
    raw_window_plan: Optional[RawWindowPlan] = None
    raw_ceiling_plan: Optional[RawCeilingPlan] = None
    raw_object_selection: Optional[Dict[str, RawRoomObjects]] = None
    raw_floor_object_constraints: Optional[Dict[str, RawFloorObjectConstraints]] = None
    raw_wall_object_constraints: Optional[Dict[str, RawWallObjectConstraints]] = None
