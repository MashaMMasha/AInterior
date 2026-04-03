from abc import ABC, abstractmethod
from typing import Any

from obllomov.schemas.domain.entries import ScenePlan

Candidate = tuple[str, float]


class Constraint(ABC):
    @abstractmethod
    def apply(self, candidates: list[Candidate]) -> list[Candidate]:
        raise NotImplementedError


class FloorAnnotationConstraint(Constraint):
    def __init__(self, selector: Any):
        self._selector = selector

    def apply(self, candidates: list[Candidate]) -> list[Candidate]:
        return self._selector._filter_floor_annotations(candidates)


class WallAnnotationConstraint(Constraint):
    def __init__(self, selector: Any):
        self._selector = selector

    def apply(self, candidates: list[Candidate]) -> list[Candidate]:
        return self._selector._filter_wall_annotations(candidates)


class ObjectSizeConstraint(Constraint):
    def __init__(self, selector: Any, room_size: tuple):
        self._selector = selector
        self._room_size = room_size

    def apply(self, candidates: list[Candidate]) -> list[Candidate]:
        return self._selector._check_object_size(candidates, self._room_size)


class ThinConstraint(Constraint):
    def __init__(self, selector: Any):
        self._selector = selector

    def apply(self, candidates: list[Candidate]) -> list[Candidate]:
        return self._selector._check_thin_object(candidates)


class FloorPlacementConstraint(Constraint):
    def __init__(
        self,
        selector: Any,
        room_vertices: list,
        scene_plan: ScenePlan,
        *,
        max_candidates: int = 20,
    ):
        self._selector = selector
        self._room_vertices = room_vertices
        self._scene_plan = scene_plan
        self._max_candidates = max_candidates

    def apply(self, candidates: list[Candidate]) -> list[Candidate]:
        return self._selector._check_floor_placement(
            candidates[: self._max_candidates],
            self._room_vertices,
            self._scene_plan,
        )


class WallPlacementConstraint(Constraint):
    def __init__(
        self,
        selector: Any,
        room_vertices: list,
        scene_plan: ScenePlan,
        *,
        max_candidates: int = 20,
    ):
        self._selector = selector
        self._room_vertices = room_vertices
        self._scene_plan = scene_plan
        self._max_candidates = max_candidates

    def apply(self, candidates: list[Candidate]) -> list[Candidate]:
        return self._selector._check_wall_placement(
            candidates[: self._max_candidates],
            self._room_vertices,
            self._scene_plan,
        )


class UsedAssetsConstraint(Constraint):
    def __init__(self, selector: Any):
        self._selector = selector

    def apply(self, candidates: list[Candidate]) -> list[Candidate]:
        if not candidates:
            return []
        return self._selector._filter_used_assets(candidates)


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
