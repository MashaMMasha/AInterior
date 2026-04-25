from abc import ABC, abstractmethod

from obllomov.schemas.domain.annotations import Annotation
from obllomov.agents.selectors.placement import DFS_Solver_Floor, DFS_Solver_Wall, FloorPlacement, WallPlacement
from obllomov.shared.geometry import Polygon2D, Vertex2D
from obllomov.shared.log import logger

Candidate = tuple[str, float]


class Constraint(ABC):
    @abstractmethod
    def apply(self, candidates: list[Candidate]) -> list[Candidate]:
        ...


class FloorAnnotationConstraint(Constraint):
    def __init__(self, annotations: dict[str, Annotation]):
        self._annotations = annotations

    def apply(self, candidates: list[Candidate]) -> list[Candidate]:
        # logger.debug(f"Floor annotations: {[self._annotations[c[0]] for c in candidates]}")
        return [
            c for c in candidates
            if self._annotations[c[0]].onFloor
        ]


class WallAnnotationConstraint(Constraint):
    def __init__(self, annotations: dict[str, Annotation]):
        self._annotations = annotations

    def apply(self, candidates: list[Candidate]) -> list[Candidate]:
        # logger.debug(f"Wall annotations: {[self._annotations[c[0]] for c in candidates]}")
        return [
            c for c in candidates
            if self._annotations[c[0]].onWall
        ]


class ObjectSizeConstraint(Constraint):
    def __init__(self, annotations: dict[str, Annotation], room_size: tuple, tolerance: float = 0.8):
        self._annotations = annotations
        self._room_size = room_size
        self._tolerance = tolerance

    def apply(self, candidates: list[Candidate]) -> list[Candidate]:
        max_x = self._room_size[0] * self._tolerance
        max_z = self._room_size[1] * self._tolerance
        max_y = self._room_size[2] * self._tolerance
        result = []
        # logger.debug(f"Bbox: {[self._annotations[c[0]].bbox for c in candidates]}")
        for c in candidates:
            dim = self._annotations[c[0]].bbox
            # logger.debug(f"{dim=}")
            obj_x, obj_z = max(dim.x, dim.z), min(dim.x, dim.z)
            obj_y = dim.y
            if obj_x <= max_x and obj_z <= max_z and obj_y <= max_y:
                result.append(c)
        return result


class ThinConstraint(Constraint):
    def __init__(self, annotations: dict[str, Annotation], thin_threshold: float = 3.0):
        self._annotations = annotations
        self._thin_threshold = thin_threshold

    def apply(self, candidates: list[Candidate]) -> list[Candidate]:
        result = []
        for c in candidates:
            dim = self._annotations[c[0]].bbox.convert_m_to_cm()
            min_dim = min(dim.x, dim.z)
            if min_dim <= self._thin_threshold:
                result.append(c)
        return result


class FloorPlacementConstraint(Constraint):
    def __init__(
        self,
        annotations: dict[str, Annotation],
        room_vertices: list,
        initial_state: dict,
        size_buffer: int = 10,
        *,
        max_candidates: int = 20,
    ):
        self._annotations = annotations
        self._room_vertices = room_vertices
        self._initial_state = initial_state
        self._size_buffer = size_buffer
        self._max_candidates = max_candidates

    def apply(self, candidates: list[Candidate]) -> list[Candidate]:
        candidates = candidates[:self._max_candidates]
        room_x = max(v[0] for v in self._room_vertices) - min(v[0] for v in self._room_vertices)
        room_z = max(v[1] for v in self._room_vertices) - min(v[1] for v in self._room_vertices)
        grid_size = int(max(room_x // 20, room_z // 20))

        solver = DFS_Solver_Floor(grid_size=grid_size)
        initial_state = solver._convert_initial_state(self._initial_state)
        room_poly = Polygon2D(
            vertices=[Vertex2D(x=v[0], z=v[1]) for v in self._room_vertices]
        )

        grid_points = solver.create_grids(room_poly)
        grid_points = solver.remove_points(grid_points, initial_state)

        valid = []
        for c in candidates:
            dim = self._annotations[c[0]].bbox.convert_m_to_cm()
            object_dim = (
                dim.x + self._size_buffer,
                dim.z + self._size_buffer,
            )
            solutions = solver.get_all_solutions(room_poly, grid_points, object_dim)
            solutions = solver.filter_collision(initial_state, solutions)
            solutions = solver.place_edge(room_poly, solutions, object_dim)
            if solutions:
                valid.append(c)
            # else:
                # logger.debug(f"Floor Object {c[0]} (size: {object_dim}) cannot be placed in room")
        return valid


class WallPlacementConstraint(Constraint):
    def __init__(
        self,
        annotations: dict[str, Annotation],
        room_vertices: list,
        initial_state: dict,
        *,
        max_candidates: int = 20,
    ):
        self._annotations = annotations
        self._room_vertices = room_vertices
        self._initial_state = initial_state
        self._max_candidates = max_candidates

    def apply(self, candidates: list[Candidate]) -> list[Candidate]:
        candidates = candidates[:self._max_candidates]
        room_x = max(v[0] for v in self._room_vertices) - min(v[0] for v in self._room_vertices)
        room_z = max(v[1] for v in self._room_vertices) - min(v[1] for v in self._room_vertices)
        grid_size = int(max(room_x // 20, room_z // 20))

        solver = DFS_Solver_Wall(grid_size=grid_size)
        initial_state = solver._convert_initial_state(self._initial_state)
        room_poly = Polygon2D(
            vertices=[Vertex2D(x=v[0], z=v[1]) for v in self._room_vertices]
        )

        grid_points = solver.create_grids(room_poly)

        valid = []
        for c in candidates:
            dim = self._annotations[c[0]].bbox.convert_m_to_cm()
            object_dim = (dim.x, dim.y, dim.z)
            solutions = solver.get_all_solutions(room_poly, grid_points, object_dim, height=0)
            solutions = solver.filter_collision(initial_state, solutions)
            if solutions:
                valid.append(c)
            # else:
            #     logger.debug(f"Wall Object {c[0]} (size: {object_dim}) cannot be placed in room")
        return valid


class UsedAssetsConstraint(Constraint):
    def __init__(self, used_assets: list[str]):
        self._used_assets = used_assets

    def apply(self, candidates: list[Candidate]) -> list[Candidate]:
        if not candidates:
            return []
        return [c for c in candidates if c[0] not in self._used_assets]


__all__ = [
    "Constraint",
    "FloorAnnotationConstraint",
    "WallAnnotationConstraint",
    "ObjectSizeConstraint",
    "ThinConstraint",
    "FloorPlacementConstraint",
    "WallPlacementConstraint",
    "UsedAssetsConstraint",
]
