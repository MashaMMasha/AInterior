import math
from typing import Optional

import numpy as np
from pydantic import BaseModel
from shapely.geometry import LineString, Point
from shapely.geometry import Polygon as ShapelyPolygon
from .log import logger


class ScalableModel(BaseModel):
    def scaled(self, factor: float):
        return self.__class__(**{k: v * factor for k, v in self.model_dump().items()})

    def convert_m_to_cm(self):
        return self.scaled(100.0)

    def convert_cm_to_m(self):
        return self.scaled(0.01)


class Vertex2D(ScalableModel):
    x: float
    z: float

    def to_tuple(self) -> tuple[float, float]:
        return (self.x, self.z)

    def to_list(self) -> list[float]:
        return [self.x, self.z]

    def to_np(self) -> np.ndarray:
        return np.array([self.x, self.z])

    def __hash__(self):
        return hash((self.x, self.z))

    def __eq__(self, other: "Vertex2D"):
        return self.x == other.x and self.z == other.z


class Vertex3D(ScalableModel):
    x: float
    y: float
    z: float

    def to_2d(self) -> Vertex2D:
        return Vertex2D(x=self.x, z=self.z)

    def to_np(self) -> np.ndarray:
        return np.array([self.x, self.y, self.z])


class BBox3D(ScalableModel):
    x: float
    y: float
    z: float

    def size(self, scale: float = 1.0) -> list[float]:
        return [self.x * scale, self.y * scale, self.z * scale]


class Box3D(BaseModel):
    min_point: Vertex3D
    max_point: Vertex3D

    @classmethod
    def from_center_and_size(cls, center: Vertex3D, size: BBox3D) -> "Box3D":
        return cls(
            min_point=Vertex3D(
                x=center.x - size.x / 2,
                y=center.y - size.y / 2,
                z=center.z - size.z / 2,
            ),
            max_point=Vertex3D(
                x=center.x + size.x / 2,
                y=center.y + size.y / 2,
                z=center.z + size.z / 2,
            ),
        )

    def intersects(self, other: "Box3D") -> bool:
        return (
            self.max_point.x >= other.min_point.x
            and self.min_point.x <= other.max_point.x
            and self.max_point.y >= other.min_point.y
            and self.min_point.y <= other.max_point.y
            and self.max_point.z >= other.min_point.z
            and self.min_point.z <= other.max_point.z
        )


class Segment2D(BaseModel):
    v1: Vertex2D
    v2: Vertex2D

    def to_shapely(self) -> LineString:
        return LineString([self.v1.to_tuple(), self.v2.to_tuple()])

    @property
    def length(self) -> float:
        dx = self.v2.x - self.v1.x
        dz = self.v2.z - self.v1.z
        return math.sqrt(dx * dx + dz * dz)

    @property
    def direction_vector(self) -> np.ndarray:
        vec = np.array([self.v2.x - self.v1.x, self.v2.z - self.v1.z])
        length = np.linalg.norm(vec)
        if length == 0:
            return vec
        return vec / length

    @property
    def perpendicular_vector(self) -> np.ndarray:
        d = self.direction_vector
        perp = np.array([-d[1], d[0]])
        norm = np.linalg.norm(perp)
        if norm == 0:
            return perp
        return perp / norm

    def contains_point(self, point: Vertex2D) -> bool:
        return self.to_shapely().intersects(Point(point.x, point.z))

    def intersects(self, other: "Segment2D") -> bool:
        return self.to_shapely().intersects(other.to_shapely())

    def intersection(self, other: "Segment2D") -> Optional["Segment2D"]:
        result = self.to_shapely().intersection(other.to_shapely())
        if result.geom_type == "LineString":
            coords = list(result.coords)
            return Segment2D(
                v1=Vertex2D(x=coords[0][0], z=coords[0][1]),
                v2=Vertex2D(x=coords[1][0], z=coords[1][1]),
            )
        return None

    def reversed(self) -> "Segment2D":
        return Segment2D(v1=self.v2, v2=self.v1)

    def point_at(self, t: float) -> Vertex2D:
        d = self.direction_vector
        return Vertex2D(x=self.v1.x + d[0] * t, z=self.v1.z + d[1] * t)

    def midpoint(self) -> Vertex2D:
        return Vertex2D(
            x=(self.v1.x + self.v2.x) / 2,
            z=(self.v1.z + self.v2.z) / 2,
        )

    def to_vertex3d_list(self) -> list[Vertex3D]:
        return [
            Vertex3D(x=self.v1.x, y=0, z=self.v1.z),
            Vertex3D(x=self.v2.x, y=0, z=self.v2.z),
        ]


class Polygon2D(BaseModel):
    vertices: list[Vertex2D]

    def to_shapely(self) -> ShapelyPolygon:
        return ShapelyPolygon([v.to_tuple() for v in self.vertices])

    @property
    def area(self) -> float:
        return self.to_shapely().area

    @property
    def perimeter(self) -> float:
        return self.to_shapely().length

    @property
    def centroid(self) -> Vertex2D:
        c = self.to_shapely().centroid
        return Vertex2D(x=c.x, z=c.y)

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        return self.to_shapely().bounds

    def contains(self, point: Vertex2D) -> bool:
        return self.to_shapely().contains(Point(point.x, point.z))

    def contains_polygon(self, other: "Polygon2D") -> bool:
        return self.to_shapely().contains(other.to_shapely())

    def contains_point_of(self, other: "Polygon2D") -> bool:
        shapely_self = self.to_shapely()
        for v in other.vertices:
            if shapely_self.contains(Point(v.x, v.z)):
                return True
        return False

    def equals(self, other: "Polygon2D") -> bool:
        return self.to_shapely().equals(other.to_shapely())

    def intersection(self, other: "Polygon2D"):
        return self.to_shapely().intersection(other.to_shapely())

    def segments(self) -> list[Segment2D]:
        n = len(self.vertices)
        return [
            Segment2D(v1=self.vertices[i], v2=self.vertices[(i + 1) % n])
            for i in range(n)
        ]

    def bbox_size(self) -> tuple[float, float]:
        xs = [v.x for v in self.vertices]
        zs = [v.z for v in self.vertices]
        return round(max(xs) - min(xs), 2), round(max(zs) - min(zs), 2)

    def scaled(self, factor: float) -> "Polygon2D":
        return Polygon2D(
            vertices=[v.scaled(factor) for v in self.vertices]
        )


def sort_vertices_clockwise(vertices: list[Vertex2D]) -> list[Vertex2D]:
    n = len(vertices)
    if n == 0:
        return []
    cx = sum(v.x for v in vertices) / n
    cz = sum(v.z for v in vertices) / n
    clockwise = sorted(
        vertices,
        key=lambda v: (-math.atan2(v.z - cz, v.x - cx)) % (2 * math.pi),
    )
    min_vertex = min(clockwise, key=lambda v: v.x)
    idx = clockwise.index(min_vertex)
    return clockwise[idx:] + clockwise[:idx]


def get_full_vertices(
    original: list[Vertex2D], all_vertices: list[Vertex2D]
) -> list[Vertex2D]:
    n = len(original)
    segments = [
        Segment2D(v1=original[i], v2=original[(i + 1) % n])
        for i in range(n)
    ]
    full = []
    for vertex in all_vertices:
        for segment in segments:
            if segment.contains_point(vertex):
                full.append(vertex)
                break
    return full


def check_interior_angles(vertices: list[Vertex2D]) -> bool:
    n = len(vertices)
    for i in range(n):
        a = vertices[i]
        b = vertices[(i + 1) % n]
        c = vertices[(i + 2) % n]
        angle = abs(math.degrees(
            math.atan2(c.z - b.z, c.x - b.x)
            - math.atan2(a.z - b.z, a.x - b.x)
        ))
        if angle < 90 or angle > 270:
            return False
    return True


def generate_wall_polygon(
    p1: Vertex2D, p2: Vertex2D, height: float
) -> list[Vertex3D]:
    return [
        Vertex3D(x=p1.x, y=0, z=p1.z),
        Vertex3D(x=p1.x, y=height, z=p1.z),
        Vertex3D(x=p2.x, y=height, z=p2.z),
        Vertex3D(x=p2.x, y=0, z=p2.z),
    ]


def create_offset_rectangles(
    segment: Segment2D, offset: float
) -> tuple[list[list[float]], list[list[float]]]:
    pt1 = segment.v1.to_np()
    pt2 = segment.v2.to_np()
    perp = segment.perpendicular_vector * offset
    top = [list(pt1 + perp), list(pt2 + perp), list(pt2), list(pt1)]
    bottom = [list(pt1), list(pt2), list(pt2 - perp), list(pt1 - perp)]
    return top, bottom


def get_wall_direction(
    p1: Vertex2D, p2: Vertex2D, room_polygon: Polygon2D
) -> tuple[float, Optional[str]]:
    seg = Segment2D(v1=p1, v2=p2)
    wall_width = seg.length
    center = seg.midpoint()
    direction = None

    if p1.z == p2.z:
        if room_polygon.contains(Vertex2D(x=center.x, z=center.z + 0.01)):
            direction = "south"
        elif room_polygon.contains(Vertex2D(x=center.x, z=center.z - 0.01)):
            direction = "north"
    elif p1.x == p2.x:
        if room_polygon.contains(Vertex2D(x=center.x + 0.01, z=center.z)):
            direction = "west"
        elif room_polygon.contains(Vertex2D(x=center.x - 0.01, z=center.z)):
            direction = "east"

    return wall_width, direction
